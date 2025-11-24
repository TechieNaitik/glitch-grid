const socket = io(); // Connect to server

const canvas = document.getElementById('gameCanvas');
const scoreList = document.getElementById('score-list');
const winnerText = document.getElementById('winner-text');
const gameOverScreen = document.getElementById('game-over-screen');
const countdownScreen = document.getElementById('countdown-screen');
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

// Store the player ID assigned by the server (p1 or p2)
let myPlayerId = null;

// --- LISTEN FOR UPDATES ---
socket.on('state_update', (state) => {
    // Whenever Python sends new data, we update our local variable
    currentGameState = state;

    // Hide game over screen when a new round begins
    if (gameOverScreen.style.display === 'block') {
        gameOverScreen.style.display = 'none';
    }
    
    // Trigger a re-draw immediately upon receiving data
    render();
});

// Update the connection listener to store our player ID
socket.on('player_assignment', (data) => {
    myPlayerId = data.id;
    console.log("Joined Game!", data);
    
    // Update the UI to show the player their color
    const statusDiv = document.getElementById('status') || document.createElement('div');
    statusDiv.id = 'status';
    statusDiv.style.color = data.color;
    statusDiv.innerText = "YOU ARE THIS COLOR";
    document.body.appendChild(statusDiv);
});

socket.on('game_over', (data) => {
    // 1. HANDLE UI MESSAGE
    if (data.winner_id === myPlayerId) {
        winnerText.innerText = "VICTORY!";
        winnerText.style.color = "#00ffcc";
    } else if (data.winner_id === null) {
        winnerText.innerText = "DRAW - NO SURVIVORS";
        winnerText.style.color = "#fff";
    } else {
        winnerText.innerText = "ELIMINATED";
        winnerText.style.color = "#ff0055";
    }
    gameOverScreen.style.display = 'block';

    // 2. UPDATE LEADERBOARD
    // Clear current list
    scoreList.innerHTML = '';
    
    // Get scores and the colors dictionary directly from the event data
    const scores = data.scores;
    const colors = data.colors; //
    
    // Sort scores high to low
    // Object.entries converts {id: score} to [[id, score], ...]
    const sortedScores = Object.entries(data.scores).sort((a, b) => b[1] - a[1]);

    sortedScores.forEach(([pid, score]) => {
        // Check if the player is still connected (their color is in the map)
        if (colors[pid]) { 
            const li = document.createElement('li');
            const color = colors[pid]; // Use the reliable color data
            
            li.innerHTML = `
                <span class="color-dot" style="background-color: ${color}; color: ${color}"></span>
                ${score} Wins
            `;
            
            // Highlight MY score
            if (pid === myPlayerId) {
                li.style.fontWeight = 'bold';
                li.style.borderBottom = '1px solid #444';
            }
            scoreList.appendChild(li);
        }
    });
    // --- START COUNTDOWN AFTER 1 SECOND ---
    setTimeout(() => {
        let count = 3;
        countdownScreen.innerText = count;
        countdownScreen.style.display = 'block';

        const interval = setInterval(() => {
            count--;
            if (count <= 0) {
                clearInterval(interval);
                countdownScreen.style.display = 'none';
            } else {
                countdownScreen.innerText = count;
            }
        }, 1000);
    }, 1000);
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
    // Clear screen and draw grid...
    ctx.clearRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);
    drawGrid();

    if (currentGameState && currentGameState.players) {
        const players = currentGameState.players;
        
        for (let id in players) {
            const p = players[id];

            // Skip rendering if server deleted the player
            if (p.dead) continue;

            // Draw Trail
            if (p.trail) drawTrail(p.trail, p.color);

            // Draw Head
            drawSquare(p.x, p.y, p.color);
        }
    }
}

// New function to draw the trail (list of coordinates)
function drawTrail(trail_coords, color) {
    ctx.shadowBlur = 0; 
    ctx.fillStyle = color;
    
    const totalSegments = trail_coords.length;

    trail_coords.forEach(([x, y], index) => {
        // Calculate Opacity: 
        // Index 0 (Oldest) is nearly 0.1 opacity
        // Last Index (Newest) is 1.0 opacity
        const opacity = (index + 1) / totalSegments;
        
        // Apply opacity to the canvas context
        ctx.globalAlpha = opacity; 

        ctx.fillRect(
            (x * TILE_SIZE) + 1, 
            (y * TILE_SIZE) + 1, 
            TILE_SIZE - 2, 
            TILE_SIZE - 2
        );
    });

    // IMPORTANT: Reset opacity back to 1.0 so we don't fade the Player Head!
    ctx.globalAlpha = 1.0; 
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