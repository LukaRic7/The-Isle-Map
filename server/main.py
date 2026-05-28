import requests, socketio, json, threading, asyncio, time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from bs4 import BeautifulSoup
from aiohttp import web
#import loggerric as lr

from colors import ColorManager
from utils import get_exe_path, get_seconds_till_next_minute
from fetch import Observer

sio = socketio.AsyncServer()
app = web.Application()
sio.attach(app)

@dataclass
class PlayerInformation:
    je_cookie:str=None
    color:str=None
    coordinates:deque[dict]=field(default_factory=lambda: deque(maxlen=5)) # [{ 'utc_timestamp': 0, 'coordinates': '...' }, ...]
    species:str=None
    user_agent:str=None
    observer:Observer=None
    health:dict=field(default_factory=dict) # { 'percent': 0, 'deltarate': 0, 'eta_top': -0 }
    growth:dict=field(default_factory=dict) # { -||- }
    hunger:dict=field(default_factory=dict) # { -||- }
    thirst:dict=field(default_factory=dict) # { -||- }
    balance:int=None
    alias:str='No Username'

# Read the config file once
with open(get_exe_path('config.json'), 'r') as file:
    CONFIG:dict = json.load(file)

client_cache:dict[str, PlayerInformation] = {}

def serialize_player_information() -> dict:
    """
    **Converts the client cache into a dictionary.**
    
    *Returns*:
    - (dict): The serialized client cache.
    """
    player_list = {}
    for cid, player_information in client_cache.items():
        player_list[cid] = {
            'color': player_information.color,
            'alias': player_information.alias,
            'species': player_information.species,
            'health': player_information.health,
            'growth': player_information.growth,
            'hunger': player_information.hunger,
            'thirst': player_information.thirst,
            'balance': player_information.balance
        }
    
    return player_list

@sio.event
async def connect(client_id:str, environment_values:dict, authentication:dict):
    """
    **Called when a client is attempting to connect.**
    
    *Parameters*:
    - `client_id` (str): The ID of the connecting client.
    - `environment_values` (dict): Transport metadata.
    - `authentication` (dict): Authentication parameters, password & cookies.
    """
    # Log connection
    ip = environment_values.get('REMOTE_ADDR')
    #lr.Log.debug(f'Connection attempt recieved from: {ip}', highlight=ip)

    # Check password
    auth = authentication or {}
    if auth.get('password') != CONFIG.get('password'):
        #lr.Log.warn(f'Rejected client, incorrect password: {client_id}', highlight=client_id)
        raise ConnectionRefusedError('Incorrect password')

    # Assure non-duplicate
    if client_cache.get(client_id) != None:
        #lr.Log.warn(f'Rejected client, already connected: {client_id}', highlight=client_id)
        raise ConnectionRefusedError('Already connected')

    # Create player
    alias = auth.get('alias')
    color = ColorManager.occupy()
    obs = Observer(auth.get('je-cookie'), user_agent=auth.get('user-agent')) if auth.get('je-cookie') else None
    if not obs:
        pass
        print('New client did not provide an observer!')
        #lr.Log.warn('New client did not provide an observer!')

    client_cache[client_id] = PlayerInformation(
        je_cookie=auth.get('je-cookie'), user_agent=auth.get('user-agent'),
        color=color, alias=alias, observer=obs
    )

    # Broadcast the newly joined player
    await sio.emit('update-player-list', serialize_player_information())
    positions = { cid: list(data.coordinates) for cid, data in client_cache.items() }
    await sio.emit('update-player-positions', positions, to=client_id)

    #lr.Log.info(f'Client connected with ID: {client_id}, Alias: "{alias}" and IP: {ip}', highlight=[client_id, ip, alias])

@sio.event
async def disconnect(client_id:str):
    """
    **Called when a client is disconnecting.**
    
    *Parameters*:
    - `client_id` (str): The ID of the disconnecting client.
    """
    player:PlayerInformation = client_cache.get(client_id)
    # Check if player exists in cache
    if player == None:
        #lr.Log.warn(f'Non-connected client tried to disconnect: {client_id}', highlight=client_id)
        raise ConnectionRefusedError('Not connected')

    # Unassign color
    ColorManager.unassign(player.color)

    # Grab alias before deleting cache
    alias = player.alias

    # Flush cache
    del client_cache[client_id]
    
    # Broadcast the disconnected client
    await sio.emit('update-player-list', serialize_player_information())
    positions = { cid: list(data.coordinates) for cid, data in client_cache.items() }
    await sio.emit('update-player-positions', positions)

    #lr.Log.info(f'Client "{alias}" disconnected with ID: {client_id}', highlight=[client_id, alias])

@sio.on('heartbeat')
async def heartbeat(client_id:str) -> dict:
    """
    **Heartbeat endpoint that the client can hit.**
    
    *Parameters*:
    - `client_id` (str): The ID of the hitting client.
    
    *Returns*:
    - (dict): Status of the heartbeat.
    """
    return { 'status': 'ok' }

@sio.on('position-update')
async def on_client_position_update(client_id:str, coordinates:list, utc_timestamp:int):
    player = client_cache.get(client_id)
    
    player.coordinates.append({
        'utc_timestamp': utc_timestamp,
        'coordinates': coordinates
    })

    positions = { cid: list(data.coordinates) for cid, data in client_cache.items() }
    await sio.emit('update-player-positions', positions)

async def fetching_worker():
    while True:
        for client_id, client_data in client_cache.items():
            try:
                if client_data.observer:
                    print('Client has an observer')
                    data = client_data.observer.fetch()
                    if data:
                        print('Client had data!')
                        client_data.health = {
                            'percent': data.get('current').get('Health'),
                            'deltarate': data.get('delta-per-min', {}).get('Health'),
                            'eta_top': data.get('est-time-min', {}).get('Health')
                        }
                        client_data.growth = {
                            'percent': data.get('current').get('Growth'),
                            'deltarate': data.get('delta-per-min', {}).get('Growth'),
                            'eta_top': data.get('est-time-min', {}).get('Growth')
                        }
                        client_data.hunger = {
                            'percent': data.get('current').get('Hunger'),
                            'deltarate': data.get('delta-per-min', {}).get('Hunger'),
                            'eta_top': data.get('est-time-min', {}).get('Hunger')
                        }
                        client_data.thirst = {
                            'percent': data.get('current').get('Thirst'),
                            'deltarate': data.get('delta-per-min', {}).get('Thirst'),
                            'eta_top': data.get('est-time-min', {}).get('Thirst')
                        }
                        client_data.balance = data.get('balance')
                        client_data.species = data.get('dinosaur')
            except Exception as e:
                #lr.Log.error(f'Error occurred while fetching: {e}')
                pass

        await sio.emit('update-player-list', serialize_player_information())

        await asyncio.sleep(get_seconds_till_next_minute())

async def heartbeat_worker():
    """
    **Called by a thread. Sends heartbeats to all connected clients,
    disconnecting any clients that the heartbeat doesn't reach.**
    """
    heartbeat_config:dict = CONFIG.get('heartbeat')

    while True:
        for client_id in list(client_cache.keys()):
            try:
                await sio.call('heartbeat', to=client_id, timeout=heartbeat_config.get('timeout_sec'))
            except (socketio.exceptions.TimeoutError, socketio.exceptions.BadNamespaceError):
                #lr.Log.warn(f"Heartbeat didn't reach client: {client_id}", highlight=client_id)
                await sio.disconnect(client_id)
            
        await asyncio.sleep(heartbeat_config.get('interval_sec'))

async def on_startup(app:web.Application):
    """
    **Called by the web application on startup.**
    
    *Parameters*:
    - `app` (web.Application): The application that runs the hook.
    """
    app['heartbeat_task'] = asyncio.create_task(heartbeat_worker())
    app['fetching_task'] = asyncio.create_task(fetching_worker())

async def on_cleanup(app:web.Application):
    """
    **Called by the web application on cleanup.**
    
    *Parameters*:
    - `app` (web.Application): The application that runs the hook.
    """
    app['heartbeat_task'].cancel()
    app['fetching_task'].cancel()

def main():
    """
    **Main entrypoint.**
    """
    
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    web.run_app(app, host='0.0.0.0', port=CONFIG.get('port'))

if __name__ == '__main__': main()