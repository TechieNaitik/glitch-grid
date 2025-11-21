from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins='*')

# --- GAME CONSTANTS ---
GRID_SIZE = 30
TILE_SIZE = 20 # Define this here! (20 pixels per tile)
# Combine constants into one dictionary
GAME_CONFIG = {
    'GRID_COUNT': 30,
    'TILE_SIZE': 20
}

# --- GAME STATE ---
game_state = {
    'players': {
        'p1': {'x': 5, 'y': 5, 'dx': 1, 'dy': 0, 'color': '#00ffcc'},
    }
}

# --- GLOBAL CONTROL ---
thread = None  # To track the background thread

# --- THE GAME ENGINE ---
def game_loop():
    print("--- GAME ENGINE STARTED ---")
    while True:
        # 1. UPDATE POSITIONS
        for player_id, p in game_state['players'].items():
            p['x'] += p['dx']
            p['y'] += p['dy']

            # Screen Wrapping
            p['x'] = p['x'] % GRID_SIZE 
            p['y'] = p['y'] % GRID_SIZE

        # 2. BROADCAST
        socketio.emit('state_update', game_state)
        
        # DEBUG: Print position to terminal so we know it's working
        # print(f"Tick: {game_state['players']['p1']['x']}") 

        # 3. SLEEP
        socketio.sleep(0.05)

# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html', config=GAME_CONFIG)

@socketio.on('connect')
def handle_connect():
    global thread
    print('Client connected')
    
    # START THE GAME LOOP ONLY IF IT ISN'T RUNNING
    if thread is None:
        thread = socketio.start_background_task(game_loop)

@socketio.on('change_direction')
def handle_direction_change(data):
    # For now, we only deal with our single player, 'p1'
    p = game_state['players']['p1']
    new_dx = data['dx']
    new_dy = data['dy']
    
    # 180-Degree Turn Prevention Logic:
    # If the sum of the current direction vector and the new vector is zero, 
    # the player is trying to reverse (e.g., current dx=1, new dx=-1 results in 0).
    is_not_reversing = p['dx'] + new_dx != 0 or p['dy'] + new_dy != 0

    if is_not_reversing:
        # Update the direction vectors
        p['dx'] = new_dx
        p['dy'] = new_dy
        # Optional: uncomment to see confirmation in terminal
        # print(f"p1 direction changed to: ({new_dx}, {new_dy})")
    else:
        # print("180-degree turn blocked.")
        pass # Ignore the input if it's a reverse move

# --- RUN ---
if __name__ == '__main__':
    socketio.run(app, debug=True)