from collections import defaultdict, deque
from aiohttp import web
import loggerric as lr
import socketio, json

from colors import ColorManager
import utils

# Initialize server
sio = socketio.AsyncServer()
app = web.Application()
sio.attach(app)

# Store connected clients colors and coords
player_colors:dict = {}
player_coords = defaultdict(lambda: deque(maxlen=10))

# Read the config
with open(utils.resource_path('config.json')) as file:
    CONFIG:dict = json.load(file)

# Bind client connect event
@sio.event
async def connect(sid:str, environ:dict, auth:dict):
    """
    Called when a client connects.

    *Parameters*:
    - `sid` (str): ID of the client.
    - `environ` (dict): Environment values passed.
    - `auth` (dict): Authentication values.
    """

    # Check password
    if not auth or auth.get('password') != CONFIG.get('server').get('pass'):
        lr.Log.warn('Rejected client, incorrect password:', sid)
        return False # Reject
    
    lr.Log.info('Client connected:', sid)

# Bind client disconnect event
@sio.event
async def disconnect(sid:str):
    """
    Called when a client disconnects.
    
    *Parameters*:
    - `sid` (str): ID of the client.
    """

    # Unassign colors and delete stored keys
    ColorManager.unassign(player_colors[sid])
    del player_colors[sid]
    del player_coords[sid]

    lr.Log.info('Client disconnected:', sid)

# Called when a player updates their position
@sio.on('update-position')
async def update_position(sid:str, coords:list):
    """
    Called when a client updates their position, then tells all clients to
    update their positions so it's synced.
    
    *Parameters*:
    - `sid` (str): ID of the client.
    - `coords` (list): X & Y coordinate.
    """

    # Append coord to player
    player_coords[sid].append(tuple(coords))

    # Get the plain strcuture format for json
    plain = { player_colors[k]: list(v) for k, v in player_coords.items() }

    # Broadcast positions to all clients
    await sio.emit('update-position', json.dumps(plain))

# Called when a client yells back that they are connected
@sio.on('client-connect')
async def client_connect(sid:str):
    """
    Called when a client is connected. Assigns a unique color for them.
    
    *Parameters*:
    - `sid` (str): ID of the client.
    """

    # Assign a color and return it
    color = ColorManager.occupy()
    player_colors[sid] = color
    await sio.emit('color-assignment', color, sid)

# Fire up the server to listen on all channels
web.run_app(app, host='0.0.0.0', port=CONFIG.get('server').get('port'))