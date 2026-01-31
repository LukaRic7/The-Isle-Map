import loggerric as lr
import tkinter as tk
import sockric as sr
import os, json

from gui import Gui

with open(os.path.join(os.path.dirname(__file__), 'config.json')) as file:
    CONFIG:dict = json.load(file)

server_config:dict = CONFIG.get('server', {})
client = sr.Client(server_config.get('ip'), server_config.get('port'))

root = tk.Tk()
root.wm_title('The Isle Map v3.0')
root.wm_resizable(False, False)

app = Gui(root, client, CONFIG)
app.pack()

@client.on_packet(sr.EventDefaults.SERVER_STOPPED)
def on_server_stopped(data:dict) -> None:
    print(data, 'server_stopped')

@client.on_packet('update_positions')
def on_update_positions(data:dict) -> None:
    print(data, 'update_positions')

@client.on_packet('color_assignment')
def on_color_assignment(data:dict) -> None:
    print(data, 'color_assignment')

if __name__ == '__main__':
    root.mainloop()