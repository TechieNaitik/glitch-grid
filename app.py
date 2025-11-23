from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import random, time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins='*')

# --- GAME CONSTANTS ---
GRID_SIZE = 30
TILE_SIZE = 20
MAX_TRAIL_LENGTH = 20
GAME_CONFIG = {'GRID_COUNT': GRID_SIZE, 'TILE_SIZE': TILE_SIZE}

# --- GLOBAL STATE ---
player_scores = {} # Maps session_id -> integer score
player_colors_map = {} # Maps session_id -> color (PERSISTENT)
round_start_time = None # Tracks time in seconds since epoch

game_state = {
    'players': {}, # Stores all player entities
    'game_active': True
}
thread = None

# --- HELPER FUNCTIONS ---
def generate_random_color():
    """Generates a bright neon color using HSL."""
    hue = random.randint(0, 360)
    # 100% Saturation, 50% Lightness = Neon
    return f"hsl({hue}, 100%, 50%)"

def get_safe_spawn():
    """Finds a random coordinate that isn't occupied."""
    while True:
        x = random.randint(2, GRID_SIZE - 3) # Keep away from extreme edges
        y = random.randint(2, GRID_SIZE - 3)
        
        # Check collision with any existing player
        if not check_collision(x, y, None):
            return x, y

def check_collision(x, y, current_player_id):
    """Checks if the next (x, y) hits a wall, a trail, or another player's head."""
    # 1. Check World Bounds (Walls)
    if not (0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE):
        return True

    # 2. Check All Players for Trails/Heads
    for p_id, p in game_state['players'].items():
        # Check against the trail
        if (x, y) in p['trail']:
            return True
        
        # Check against the Head (if it's not me)
        if p_id != current_player_id and x == p['x'] and y == p['y']:
            return True
    return False

def reset_game():
    """Respawn everyone who is currently connected."""
    print("Resetting Round...")
    game_state['game_active'] = True
    
    for p_id, p in game_state['players'].items():
        new_x, new_y = get_safe_spawn()
        p['x'] = new_x
        p['y'] = new_y
        p['dx'] = 0 # Stop movement on reset
        p['dy'] = 0
        p['trail'] = []
        p['dead'] = False

    socketio.emit('state_update', game_state)

# --- GAME LOOP ---
def game_loop():
    print("--- DYNAMIC ENGINE STARTED ---")
    while True:
        players_alive = 0
        total_players = len(game_state['players'])
        
        # 1. MOVE PLAYERS
        if game_state['game_active'] and total_players > 0:
            for p_id, p in game_state['players'].items():
                if p['dead']: continue

                # Only move if they have a direction (dx/dy not 0)
                if p['dx'] == 0 and p['dy'] == 0:
                    players_alive += 1
                    continue

                next_x = p['x'] + p['dx']
                next_y = p['y'] + p['dy']

                if check_collision(next_x, next_y, p_id):
                    p['dead'] = True
                    socketio.emit('game_message', {'message': f"Player Died!"})
                else:
                    players_alive += 1
                    p['trail'].append((p['x'], p['y']))
                    if len(p['trail']) > MAX_TRAIL_LENGTH:
                        p['trail'].pop(0)
                    p['x'] = next_x
                    p['y'] = next_y

            # 2. CHECK WIN CONDITION (Last Man Standing)
            if total_players > 1 and players_alive <= 1:
                winner_id = None
                # Find the last survivor
                for p_id, p in game_state['players'].items():
                    if not p['dead']:
                        winner_id = p_id
                        break
                
                if winner_id:
                    print(f"Winner: {winner_id}")
                    
                    global round_start_time
                    duration_seconds = 0
                    if round_start_time:
                        duration_seconds = int(time.time() - round_start_time)
                        
                    # Award 1 bonus point for every 10 seconds survived
                    # Example: 10s = 1 point, 20s = 2 points, 59s = 5 points
                    time_bonus = duration_seconds // 10 
                    
                    # Ensure score is incremented before emitting game_over
                    total_score_increase = 1 + time_bonus # Winner always gets +1 base score

                    if winner_id in player_scores:
                        player_scores[winner_id] += 1 
                    else:
                        player_scores[winner_id] = 1

                    global player_colors_map
                    socketio.emit('game_over', {
                        'winner_id': winner_id,
                        'scores': player_scores,
                        'colors': player_colors_map,
                        'duration': duration_seconds,
                        'bonus': time_bonus
                    })
                else:
                    # Everyone died (Draw)
                    socketio.emit('game_over', {'winner_id': None, 'scores': player_scores})
                
                game_state['game_active'] = False
                socketio.sleep(3)
                reset_game()

        socketio.emit('state_update', game_state)
        socketio.sleep(0.04) # 25 FPS

# --- ROUTES & SOCKET HANDLERS ---
@app.route('/')
def index():
    return render_template('index.html', config=GAME_CONFIG)

@socketio.on('connect')
def handle_connect():
    global thread
    sid = request.sid
    print(f'New Player Joined: {sid}')


    # Generate color
    if sid not in player_colors_map:
        player_colors_map[sid] = generate_random_color()
    if sid not in player_scores:
        player_scores[sid] = 0

    color = player_colors_map[sid]

    # Spawn position
    start_x, start_y = get_safe_spawn()

    # Register player in official game state
    game_state['players'][sid] = {
        'x': start_x,
        'y': start_y,
        'dx': 0,
        'dy': 0,
        'color': color,
        'trail': [],
        'dead': False
    }

    emit('player_assignment', {'id': sid, 'color': color})

    # Start game loop thread
    global thread
    if thread is None:
        thread = socketio.start_background_task(game_loop)

@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid

    # Remove from game state safely
    if sid in game_state['players']:
        del game_state['players'][sid]

    print(f"Player Left: {sid}")

@socketio.on('change_direction')
def handle_direction(data):
    sid = request.sid
    if sid in game_state['players']:

        # Prevent movement before start
        if not game_state['game_active']:
            return

        p = game_state['players'][sid]
        if not p['dead']:
            new_dx, new_dy = data['dx'], data['dy']
            if p['dx'] + new_dx != 0 or p['dy'] + new_dy != 0:
                p['dx'] = new_dx
                p['dy'] = new_dy

if __name__ == '__main__':
    # host='0.0.0.0' opens the server to the local network
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)