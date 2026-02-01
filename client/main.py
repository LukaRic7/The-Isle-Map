import socketio, os, json
import loggerric as lr
import tkinter as tk

from gui import Gui
import utils

# Initialize client
sio = socketio.Client()

# Read the config
with open(utils.get_exe_path('config.json')) as file:
    CONFIG:dict = json.load(file)

# Create a tkinter root
root = tk.Tk()
root.wm_title('The Isle Map v3.0')
root.wm_resizable(False, False)

# Create an instance of the GUI app
app = Gui(root, sio, CONFIG)
app.pack()

# Called when client connected successfully
@sio.event
def connect():
    """Called when the client connected successfully. Tell the server aswell."""

    lr.Log.info('Connected!')
    sio.emit('client-connect')

# Called when any client on the server updates their position
@sio.on("update-position")
def on_update(players_positions:str):
    """
    Called when any client on the server updates their position. Then updates
    this clients positions on the map.
    
    *Parameters*:
    - `players_positions` (str): Serialized positions of all players. Can be
    deserialized to a dictionary with key being the clients color, and value
    being the list of positions.
    """

    app.update_positions_online(players_positions)

# Called when the server assigns this client a color
@sio.on('color-assignment')
def on_color_assignment(color:str):
    """
    Called when the server assigns this client a color. Then updates the color
    in the GUI on this client.
    
    *Parameters*:
    - `color` (str): The color the server assigned this client.
    """

    app.set_color(color)

if __name__ == '__main__':
    root.mainloop()