from datetime import datetime as dt, timezone as tz
import socketio, json, asyncio, sys
from pathlib import Path
from aiohttp import web
import loggerric as lr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.utils import set_project_root, get_exe_path
from shared.je_fetching import Observer, get_sleep_time
from shared.colors import ColorManager
from shared.datastructs import (Client, JurassicEchoes, JEStat, Coord,
                         serialize_client)

set_project_root(ROOT)

sio = socketio.AsyncServer()
app = web.Application()
sio.attach(app)

client_cache:dict[str, Client] = {}

# Read the config file once
with open(get_exe_path('server/config.json'), 'r') as file:
    CONFIG:dict = json.load(file)

async def disconnect_protocol(client_id:str):
    """
    **Run the cleanup process when a client disconnects.**
    
    *Parameters*:
    - `client_id` (str): The ID of the disconnecting client.
    """
    # Make sure user exists in the cache
    if not client_cache.get(client_id):
        lr.Log.warn(f'Non-cached user "{client_id}" tried to disconnect!',
                    highlight=client_id)
        return

    ColorManager.unassign(client_cache[client_id].color)

    del client_cache[client_id]

    # Broadcast the new locations without the disconnected client to everyone
    coord_data = {
        client_data.color: [
            coord.coordinates for coord in client_data.coordinates
        ]
        for client_data in client_cache.values()
    }
    pin_data = {
        client_data.color: client_data.pin_position
        for client_data in client_cache.values()
    }
    await sio.emit('update-map', (coord_data, pin_data))

    # Broadcast the new client list to everyone
    data = {
        client_id: serialize_client(client)
        for client_id, client in client_cache.items()
    }
    await sio.emit('update-player-list', data)

@sio.event
async def connect(client_id:str, environment_values:dict, authentication:dict):
    """
    **Called when a client is attempting to connect.**
    
    *Parameters*:
    - `client_id` (str): The ID of the connecting client.
    - `environment_values` (dict): Transport metadata.
    - `authentication` (dict): Authentication parameters, password & cookies.
    """
    ip:str = environment_values.get('REMOTE_ADDR')
    lr.Log.debug(f'Incomming connection attempt from IP: "{ip}"',
                 highlight=ip)

    # Make sure user doesn't exists in the cache
    if client_cache.get(client_id):
        lr.Log.warn(f'Cached user "{client_id}" tried to connect!',
                    highlight=client_id)
        #await sio.emit('auth-error', 'Already connected!', client_id)
        return False
    
    # Assert correct password
    if authentication.get('password') != CONFIG.get('password'):
        lr.Log.warn(f'Rejected client "{client_id}" for incorrect password:',
                    '"{}"'.format(authentication.get('password')),
                    highlight=client_id)
        await sio.emit('auth-error', 'Incorrect password!', client_id)
        await sio.sleep(0)
        await sio.disconnect(client_id)
        return False

    # Make sure theres not an alias duplication
    alias_list = [data.alias for client_id, data in client_cache.copy().items()]
    if authentication.get('alias') in alias_list:
        lr.Log.warn(f'Rejected client "{client_id}" for alias duplication!',
                    highlight=client_id)
        await sio.emit('auth-error', 'Alias already taken!', client_id)
        await sio.sleep(0)
        await sio.disconnect(client_id)
        return False

    lr.Log.info(f'New client "{client_id}" connected!', highlight=client_id)

    # Create a jurassic echoes client if possible
    jurassic_echoes:JurassicEchoes = None
    je_cookie = authentication.get('je-cookie')
    user_agent = authentication.get('user-agent')
    if je_cookie and user_agent:
        jurassic_echoes = JurassicEchoes(
            cookie=je_cookie,
            user_agent=user_agent,
            fetching_client=Observer(je_cookie=je_cookie, user_agent=user_agent)
        )

    # Append the new client to the cache
    client_cache[client_id] = Client(
        alias=authentication.get('alias'),
        color=ColorManager.occupy(),
        je=jurassic_echoes
    )

    # Broadcast the locations to the new client
    coord_data = {
        client_data.color: [
            coord.coordinates for coord in client_data.coordinates
        ]
        for client_data in client_cache.values()
    }
    pin_data = {
        client_data.color: client_data.pin_position
        for client_data in client_cache.values()
    }
    await sio.emit('update-map', (coord_data, pin_data), client_id)

    # Broadcast the new client list to everyone
    data = {
        client_id: serialize_client(client)
        for client_id, client in client_cache.items()
    }
    await sio.emit('update-player-list', data)

@sio.event
async def disconnect(client_id:str):
    """
    **Called when a client is disconnecting.**
    
    *Parameters*:
    - `client_id` (str): The ID of the disconnecting client.
    """
    lr.Log.info(f'Client "{client_id}" disconnecting!', highlight=client_id)

    await disconnect_protocol(client_id)

@sio.on('heartbeat')
async def heartbeat(client_id:str) -> dict:
    """
    **Heartbeat endpoint that the client can hit.**
    
    *Parameters*:
    - `client_id` (str): The ID of the hitting client.
    
    *Returns*:
    - (dict): Status of the heartbeat.
    """
    # Make sure user exists in the cache
    if not client_cache.get(client_id):
        lr.Log.warn(f'Non-cached user "{client_id}" hit heartbeat endpoint!',
                    highlight=client_id)
        return { 'status': 'not connected' }

    # Update their heartbeat timestamp
    utc_ts = int(dt.now(tz=tz.utc).timestamp())
    client_cache[client_id].last_heartbeat_utc_ts = utc_ts

    return { 'status': 'ok' }

@sio.on('updated-location')
async def updated_location(client_id:str, coordinates:list[float, float]):
    """
    **Called when a client updates their location.**
    
    *Parameters*:
    - `client_id` (str): The ID of the client updating their location.
    - `coordinates` (list[float, float]): The position of their new location.
    """
    # Make sure user exists in the cache
    if not client_cache.get(client_id):
        lr.Log.warn(f'Non-cached user "{client_id}" tried updating location!',
                    highlight=client_id)
        return
    
    lr.Log.debug(f'Client "{client_id}" updated their position!',
                 highlight=client_id)

    # Append the coordinate to their location cache
    utc_ts = int(dt.now(tz=tz.utc).timestamp())
    client_cache[client_id].coordinates.append(Coord(
        utc_timestamp=utc_ts,
        coordinates=coordinates
    ))

    client_cache[client_id].last_coordinate_utc_ts = utc_ts

    # Broadcast the new location to everyone
    coord_data = {
        client_data.color: [
            coord.coordinates for coord in client_data.coordinates
        ]
        for client_data in client_cache.values()
    }
    pin_data = {
        client_data.color: client_data.pin_position
        for client_data in client_cache.values()
    }
    await sio.emit('update-map', (coord_data, pin_data))

@sio.on('reset-coordinates')
async def reset_coordinates(client_id:str):
    """
    **Called when a client wants to reset their cached coordinates.**
    
    *Parameters*:
    - `client_id` (str): The ID of the client whos coordinates to reset.
    """
    # Make sure user exists in the cache
    if not client_cache.get(client_id):
        lr.Log.warn(f'Non-cached user "{client_id}" tried resetting location!',
                    highlight=client_id)
        return

    lr.Log.debug(f'Resetting client "{client_id}" location data!',
                 highlight=client_id)
    
    client_cache[client_id].coordinates.clear()

    # Broadcast the reset to everyone
    coord_data = {
        client_data.color: [
            coord.coordinates for coord in client_data.coordinates
        ]
        for client_data in client_cache.values()
    }
    pin_data = {
        client_data.color: client_data.pin_position
        for client_data in client_cache.values()
    }
    await sio.emit('update-map', (coord_data, pin_data))

@sio.on('pin-location')
async def pin_location(client_id:str, location:list[float, float]):
    """
    **Called when a user pins a location on the map.**
    
    *Parameters*:
    - `client_id` (str): The ID of the client pinning their location.
    - `location` (list[float, float]): The scaled location of the pin.
    """
    # Make sure user exists in the cache
    if not client_cache.get(client_id):
        lr.Log.warn(f'Non-cached user "{client_id}" tried pin location!',
                    highlight=client_id)
        return
    
    lr.Log.debug(f'Client "{client_id}" pinned a location!',
                 highlight=client_id)

    # Check if the client is trying to remove their pin
    if location[0] == None and location[1] == None:
        client_cache[client_id].pin_position = None
    else:
        client_cache[client_id].pin_position = location

    # Broadcast the update to everyone
    coord_data = {
        client_data.color: [
            coord.coordinates for coord in client_data.coordinates
        ]
        for client_data in client_cache.values()
    }
    pin_data = {
        client_data.color: client_data.pin_position
        for client_data in client_cache.values()
    }
    await sio.emit('update-map', (coord_data, pin_data))

async def fetching_worker():
    """
    **Fetches jurassic echoes data for every valid client every minute.
    Broadcasts new information to all connected clients.**
    """
    while True:
        for client_id, client_data in client_cache.copy().items():
            if not client_data.je: continue

            je_data = client_data.je.fetching_client.fetch()
            invalid_cookie = not client_data.je.fetching_client.valid_cookie
            client_cache[client_id].je.invalid_cookie = invalid_cookie
            website_down = client_data.je.fetching_client.is_down
            client_cache[client_id].je.website_down = website_down

            if not je_data: continue

            percent:dict = je_data.get('current', {})
            delta_rate:dict = je_data.get('delta-per-min', {})
            est_time_min:dict = je_data.get('est-time-min', {})

            client_cache[client_id].je.health = JEStat(
                percent=percent.get('Health'),
                delta_rate=delta_rate.get('Health'),
                eta_to_bounds=est_time_min.get('Health')
            )
            client_cache[client_id].je.growth = JEStat(
                percent=percent.get('Growth'),
                delta_rate=delta_rate.get('Growth'),
                eta_to_bounds=est_time_min.get('Growth')
            )
            client_cache[client_id].je.hunger = JEStat(
                percent=percent.get('Hunger'),
                delta_rate=delta_rate.get('Hunger'),
                eta_to_bounds=est_time_min.get('Hunger')
            )
            client_cache[client_id].je.thirst = JEStat(
                percent=percent.get('Thirst'),
                delta_rate=delta_rate.get('Thirst'),
                eta_to_bounds=est_time_min.get('Thirst')
            )

            client_cache[client_id].je.species = je_data.get('dinosaur')
            client_cache[client_id].je.balance = je_data.get('balance')

        # Broadcast the client list with updated values to everyone
        data = {
            client_id: serialize_client(client)
            for client_id, client in client_cache.items()
        }
        await sio.emit('update-player-list', data)

        await asyncio.sleep(get_sleep_time())

async def heartbeat_worker():
    """
    **Enters an infinite while loop. Sends heartbeats to all clients every
    few seconds, aswell as checks the heartbeats recieved by clients and
    disconnects any flatlining clients.**
    """
    while True:
        await sio.emit('heartbeat')

        utc_ts = int(dt.now(tz=tz.utc).timestamp())
        for client_id, data in client_cache.copy().items():
            if utc_ts >= data.last_heartbeat_utc_ts + 12:
                lr.Log.warn(f'Client "{client_id}" timed out!',
                            highlight=client_id)
                await sio.disconnect(client_id)

        await asyncio.sleep(5)

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

    try:
        web.run_app(app, host='0.0.0.0', port=CONFIG.get('port'))
    except KeyboardInterrupt:
        lr.Log.info('Keyboard interrupt detected, quitting!')

if __name__ == '__main__': main()