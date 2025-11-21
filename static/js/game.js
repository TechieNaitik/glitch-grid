const socket = io(); // Connect to server

const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

// --- CONFIGURATION ---
// These now come from the global variable defined in index.html
const TILE_SIZE = GAME_CONFIG.TILE_SIZE;
const GRID_COUNT = GAME_CONFIG.GRID_COUNT; 
const CANVAS_SIZE = TILE_SIZE * GRID_COUNT;

canvas.width = CANVAS_SIZE;
canvas.height = CANVAS_SIZE;

// Store the latest state sent by the server
let currentGameState = null;

// --- LISTEN FOR UPDATES ---
socket.on('state_update', (state) => {
    // Whenever Python sends new data, we update our local variable
    currentGameState = state;
    
    // Trigger a re-draw immediately upon receiving data
    render();
});

// --- DRAWING FUNCTIONS ---
function drawGrid() {
    // Current stroke style is retained, but you can update it here too (see below)
    ctx.lineWidth = 1;
    ctx.strokeStyle = '#444'; // Use a mid-dark grey color

    for (let i = 0; i <= GRID_COUNT; i++) {
        const offset = i * TILE_SIZE + 0.5; // <-- ADDING + 0.5 HERE!

        // Draw Vertical Lines
        ctx.beginPath();
        ctx.moveTo(offset, 0);
        ctx.lineTo(offset, CANVAS_SIZE);
        ctx.stroke();

        // Draw Horizontal Lines
        ctx.beginPath();
        ctx.moveTo(0, offset);
        ctx.lineTo(CANVAS_SIZE, offset);
        ctx.stroke();
    }
}

function drawSquare(x, y, color) {
    // x and y are Grid Coordinates (0-29), not pixels
    ctx.fillStyle = color;
    
    // We multiply by TILE_SIZE to convert grid coordinates to pixels
    // We add 1 pixel padding so the square sits inside the grid lines
    ctx.fillRect(
        (x * TILE_SIZE) + 1, 
        (y * TILE_SIZE) + 1, 
        TILE_SIZE - 2, 
        TILE_SIZE - 2
    );
    
    // Add a "glow" to the player
    ctx.shadowBlur = 10;
    ctx.shadowColor = color;
}

// --- RENDER LOOP ---
function render() {
    // 1. Clear Screen
    ctx.clearRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);
    
    // 2. Draw Background
    drawGrid();
    
    // 3. Draw Players (only if we have data)
    if (currentGameState && currentGameState.players) {
        const players = currentGameState.players;
        
        // Loop through all players in the dictionary
        for (let id in players) {
            const p = players[id];
            drawSquare(p.x, p.y, p.color);
        }
    }
}

document.addEventListener('keydown', (e) => {
    let direction = null;
    
    // Map key presses to direction vectors (dx, dy)
    // dy = -1 is Up; dy = 1 is Down
    // dx = -1 is Left; dx = 1 is Right
    switch (e.key) {
        case 'ArrowUp':
        case 'w':
            direction = { dx: 0, dy: -1 };
            break;
        case 'ArrowDown':
        case 's':
            direction = { dx: 0, dy: 1 };
            break;
        case 'ArrowLeft':
        case 'a':
            direction = { dx: -1, dy: 0 };
            break;
        case 'ArrowRight':
        case 'd':
            direction = { dx: 1, dy: 0 };
            break;
    }

    if (direction) {
        // Prevent the browser from scrolling when using arrow keys
        e.preventDefault(); 
        // Send the new direction to the server
        socket.emit('change_direction', direction);
    }
});

// Start the loop
render();