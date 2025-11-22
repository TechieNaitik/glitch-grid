from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins='*')

# --- GAME CONSTANTS ---
GRID_SIZE = 30
TILE_SIZE = 20
MAX_TRAIL_LENGTH = 30
GAME_CONFIG = {'GRID_COUNT': GRID_SIZE, 'TILE_SIZE': TILE_SIZE}

# --- GAME STATE ---
game_state = {
    'players': {}, # No longer hardcoded! Empty by default.
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
    # 1. Check Walls
    if not (0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE):
        return True

    # 2. Check All Players
    for p_id, p in game_state['players'].items():
        if (x, y) in p['trail']:
            return True
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
            # Only check if there were at least 2 people to start with
            if total_players > 1 and players_alive <= 1:
                print("Round Over!")
                winner_id = "Unknown"
                # Find the last alive player
                for p_id, p in game_state['players'].items():
                    if not p['dead']:
                        winner_id = p_id
                        break
                
                game_state['game_active'] = False
                socketio.emit('game_over', {'winner': "LAST SURVIVOR"}) # Simplified for now
                socketio.sleep(3)
                reset_game()

        socketio.emit('state_update', game_state)
        socketio.sleep(0.04) # 25 FPS

# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html', config=GAME_CONFIG)

@socketio.on('connect')
def handle_connect():
    global thread
    sid = request.sid
    print(f'New Player Joined: {sid}')
    
    # Generate Random Props
    start_x, start_y = get_safe_spawn()
    color = generate_random_color()

    # Create Player Entry
    game_state['players'][sid] = {
        'x': start_x, 'y': start_y,
        'dx': 0, 'dy': 0, # Start stationary so they don't die instantly
        'color': color,
        'trail': [],
        'dead': False
    }
    
    emit('player_assignment', {'id': sid, 'color': color})

    if thread is None:
        thread = socketio.start_background_task(game_loop)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in game_state['players']:
        del game_state['players'][sid]
        print(f'Player {sid} disconnected')

@socketio.on('change_direction')
def handle_direction(data):
    sid = request.sid
    if sid in game_state['players']:
        p = game_state['players'][sid]
        if not p['dead'] and game_state['game_active']:
            new_dx, new_dy = data['dx'], data['dy']
            # Prevent 180 turn
            if p['dx'] + new_dx != 0 or p['dy'] + new_dy != 0:
                p['dx'] = new_dx
                p['dy'] = new_dy

if __name__ == '__main__':
    socketio.run(app, debug=True)