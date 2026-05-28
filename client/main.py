import socketio, json, threading, time, pyperclip
import loggerric as lr
import tkinter as tk

from utils import get_exe_path, parse_coords, is_valid_coords, get_seconds_till_next_minute
from gui import Gui

sio = socketio.Client()
app:Gui = None

last_clip:str = None
kill_threads = False

# Read the config file once
with open(get_exe_path('config.json'), 'r') as file:
    CONFIG:dict = json.load(file)

@sio.on('update-player-list')
def update_player_list(player_list:dict):
    if app:
        app.player_list = player_list
        app.redraw_player_list()

@sio.on('heartbeat')
def heartbeat() -> dict:
    """
    **Heartbeat endpoint that the server can hit.**

    *Returns*:
    - (str): Status of the heartbeat.
    """
    return { 'status': 'ok' }

@sio.on('update-player-positions')
def update_player_positions(positions:dict):
    if app:
        for client_id, poses in positions.items():
            if app.player_list[client_id]:
                app.player_list[client_id]['coordinates'] = poses
        app.render_map()

def clipboard_worker(app:Gui):
    """
    **Called by a thread. Watches the clipboard, notifying GUI of new coords.**
    """
    global last_clip, kill_threads

    while not kill_threads:
        try:
            clip = pyperclip.paste().strip()
        except Exception:
            clip = ''

        # Only process if clipboard changed and contains valid coordinates
        if clip != last_clip and is_valid_coords(clip):
            coords = parse_coords(clip)[0:2]

            app.on_new_local_coords(coords)
            
            last_clip = clip

        time.sleep(0.5)

def on_close(root:tk.Tk):
    global kill_threads

    kill_threads = True

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
    root.wm_title('The Isle Map v4.0')
    root.wm_resizable(True, True)
    app = Gui(root, sio, CONFIG)
    app.pack(expand=True, fill='both')
    root.update()
    root.wm_minsize(600, 400)

    clipboard_thread = threading.Thread(target=clipboard_worker, args=(app,), daemon=True)
    clipboard_thread.start()

    root.protocol("WM_DELETE_WINDOW", lambda: on_close(root))

    app.mainloop()

    clipboard_thread.join()

if __name__ == '__main__': main()