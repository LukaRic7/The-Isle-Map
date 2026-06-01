import socketio, json, threading, time, pyperclip, sys, re
from datetime import datetime as dt, timezone as tz
from pathlib import Path
import loggerric as lr
import tkinter as tk

# Handle both normal execution and PyInstaller bundled exe
if getattr(sys, 'frozen', False):
    # Running as PyInstaller exe
    ROOT = Path(sys._MEIPASS).parent
else:
    # Running as script
    ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.utils import set_project_root, get_exe_path
from shared.je_fetching import get_sleep_time
from shared.datastructs import Coord, JEStat
from client.gui import Gui

set_project_root(ROOT)

sio = socketio.Client()

app:Gui = None
threads:list[threading.Thread] = []
last_heartbeat_utc_ts = None
stop_threads = False
last_clip = ''

# Read the config file once
with open(get_exe_path('client/config.json'), 'r') as file:
    CONFIG:dict = json.load(file)

@sio.event
def connect():
    """
    **Called when the client successfully connected.**
    """
    global last_heartbeat_utc_ts

    lr.Log.info('Client connected to server!')

    last_heartbeat_utc_ts = int(dt.now(tz=tz.utc).timestamp())

@sio.event
def disconnect():
    """
    **Called when the client successfully disconnects.**
    """
    lr.Log.info('Disconnected from server!')
    
    if not app: return

    app.connect_btn.configure(text='Connect')
    app.update_player_list(disconnected=True)

@sio.on('auth-error')
def auth_error(reason:str):
    """
    **Called when the server sends an authentication error message.**
    
    *Parameters*:
    - `reason` (str): The error reason message.
    """
    if not app: return

    app.set_status_text(reason, bad=True)

@sio.on('update-map')
def update_map(coordinate_map:dict, pin_map:dict):
    """
    **Called when a player on the server updated their map.**
    
    *Parameters*:
    - `coordinate_map` (dict): The list of coordinates and belonging to whom.
    - `pin_map` (dict): The list of pinned places and belonging to whom.
    """
    if not app: return

    app.render_map(coordinate_map, pin_map)

@sio.on('update-player-list')
def update_player_list(player_list:dict):
    """
    **Called when this client needs to update their player list.**
    
    *Parameters*:
    - `player_list` (dict): The player data.
    """
    if not app: return

    app.update_player_list(player_list)

@sio.on('heartbeat')
def heartbeat():
    """
    **Recieves incomming heartbeats from the server.**
    """
    global last_heartbeat_utc_ts

    last_heartbeat_utc_ts = int(dt.now(tz=tz.utc).timestamp())

def fetching_worker():
    """
    **Called by a thread. Worker fetching data from the Jurassic Echoes API.**
    """
    global stop_threads

    while not stop_threads:
        time.sleep(get_sleep_time())

        if sio.connected: continue

        if not app: continue
        if not app.client_list.get('OFFLINE'): continue
        if not app.client_list['OFFLINE'].je: continue

        client_data = app.client_list['OFFLINE']

        je_data = app.client_list['OFFLINE'].je.fetching_client.fetch()
        invalid_cookie = not client_data.je.fetching_client.valid_cookie
        client_data.je.invalid_cookie = invalid_cookie
        website_down = client_data.je.fetching_client.is_down
        client_data.je.website_down = website_down

        if not je_data: continue

        percent:dict = je_data.get('current', {})
        delta_rate:dict = je_data.get('delta-per-min', {})
        est_time_min:dict = je_data.get('est-time-min', {})

        client_data.je.health = JEStat(
            percent=percent.get('Health'),
            delta_rate=delta_rate.get('Health'),
            eta_to_bounds=est_time_min.get('Health')
        )
        client_data.je.growth = JEStat(
            percent=percent.get('Growth'),
            delta_rate=delta_rate.get('Growth'),
            eta_to_bounds=est_time_min.get('Growth')
        )
        client_data.je.hunger = JEStat(
            percent=percent.get('Hunger'),
            delta_rate=delta_rate.get('Hunger'),
            eta_to_bounds=est_time_min.get('Hunger')
        )
        client_data.je.thirst = JEStat(
            percent=percent.get('Thirst'),
            delta_rate=delta_rate.get('Thirst'),
            eta_to_bounds=est_time_min.get('Thirst')
        )

        client_data.je.species = je_data.get('dinosaur')
        client_data.je.balance = je_data.get('balance')

        app.update_player_list(disconnected=True)

def clipboard_worker():
    """
    **Called by a thread. Watches the clipboard to check if a new valid
    coordinate set has been copied.**
    """
    global stop_threads, last_clip

    while not stop_threads:
        time.sleep(0.5)

        try:
            clip = pyperclip.paste().strip()
        except Exception:
            clip = ''
        
        if clip == last_clip: continue
        last_clip = clip

        s = clip.replace(' ', '')
        if s.count(',') != 5: continue
        
        try:
            for part in s.split(','):
                float(part)

            parsed_coords = []
            for index, segment in enumerate(clip.split(',')):
                if index % 2 != 0: continue
                parsed_coords.append(float(segment))

            if sio.connected:
                sio.emit('updated-location', parsed_coords[0:2])
            else:
                if not app: continue
                
                if app.client_list.get('OFFLINE'):
                    app.client_list['OFFLINE'].coordinates.append(Coord(
                        utc_timestamp=int(dt.now(tz=tz.utc).timestamp()),
                        coordinates=parsed_coords[0:2]
                    ))
                app.render_map()
        except ValueError: continue

def heartbeat_worker():
    """
    **Called by a thread. Sends heartbeats to the server, aswell as checks if
    the server is flatlining in which case it will disconnect the client.**
    """
    global stop_threads

    while not stop_threads:
        if sio.connected:
            sio.emit('heartbeat')

            utc_ts = int(dt.now(tz=tz.utc).timestamp())
            if utc_ts >= last_heartbeat_utc_ts + 12:
                lr.Log.warn('Server timed out!')
                app.set_status_text('Server timed out!', bad=True)
                sio.disconnect()

        time.sleep(5)

def on_close(root:tk.Tk):
    """
    **Called when the Tkinter window is getting destroyed.**
    
    *Parameters*:
    - `root` (tk.Tk): The tkinter instance.
    """
    global stop_threads

    stop_threads = True

    sio.disconnect()
    sio.shutdown()
    root.destroy()
    exit()

def main():
    """
    **Main entrypoint.**
    """
    global app

    root = tk.Tk()
    root.wm_title('The Isle Map v5.0')
    root.wm_resizable(True, True)
    root.protocol('WM_DELETE_WINDOW', lambda: on_close(root))
    root.wm_minsize(640, 360)

    threads.append(threading.Thread(target=fetching_worker, daemon=True))
    threads.append(threading.Thread(target=clipboard_worker, daemon=True))
    threads.append(threading.Thread(target=heartbeat_worker, daemon=True))
    
    for thread in threads:
        thread.start()

    app = Gui(root, sio, CONFIG)
    app.pack(expand=True, fill='both')
    app.mainloop()

if __name__ == '__main__': main()