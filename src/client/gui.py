from datetime import datetime as dt, timezone as tz
import socketio, threading, time, sys
from PIL import Image, ImageTk
from pathlib import Path
from tkinter import ttk
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

from shared.datastructs import Client, JurassicEchoes, Coord, deserialize_client
from shared.je_fetching import Observer, get_sleep_time
from client.rendering import render_scaled_image
from shared.utils import get_exe_path

class Gui(ttk.Frame):
    """
    **The GUI class.**
    
    Builds the GUI, handles all control inputs.
    
    *Methods*:
    - `update_player_list(new_client_list) -> None`: Updates the player list
    based on new or cached information.
    - `render_map(coordinate_map) -> None`: Render the map and display it.
    - `set_status_text(text, bad) -> None`: Sets the status text.
    - `tgl_connect() -> None`: Toggle the server connection.
    - `reset_coordinates() -> None`: Reset the clients own coordinates.
    """
    def __init__(self, root:tk.Tk, sio:socketio.Client, config:dict):
        super().__init__(root)

        self.__sio = sio
        self.__config = config

        self.__last_status_text_utc_ts = 0

        self.__render_job:str = None
        self.__tk_image:ImageTk.PhotoImage = None
        self.__canvas_image_id:int = None # GC Prevention
        self.__next_update_ts:int = get_sleep_time() + int(time.time())

        self.__base_image = Image.open(get_exe_path('client/maps/{}'.format(
            self.__config.get('map', {}).get('filename')
        )))

        self.__zoom = 1.0
        self.__pan_x = 0
        self.__pan_y = 0
        self.__dragging = False
        self.__drag_start_x = 0
        self.__drag_start_y = 0

        self.client_list:dict[str, Client] = {}
        self.__client_widget_list:dict[str, dict[str, ttk.Widget]] = {}

        je:dict = self.__config.get('jurassic_echoes', {})
        self.__sleep_delay:int = je.get('fetching_delay_sec', 3)

        self.__add_widgets()
        self.update_player_list(disconnected=True)

        self.after(500, self.__update_countdown)

    def __update_countdown(self):
        """
        **Updates the countdown timer between JE fetches and client list
        updates.**
        """
        now_ts = int(time.time())
        if self.__next_update_ts - now_ts <= 0:
            self.__next_update_ts = get_sleep_time(self.__sleep_delay) + now_ts

        self.set_status_text(f'Updating in {self.__next_update_ts - now_ts}s')

        self.after(1000, self.__update_countdown)

    def update_player_list(self, new_client_list:dict[str, Client]=None,
                           disconnected:bool=False):
        """
        **Updates the player list based on new or cached information.**
        
        *Parameters*:
        - `new_client_list` (dict[str, Client]): The new client list to replace
        the cached one.
        - `disconnected` (bool): Weather to use public or private client list.
        Defaults to false.
        """
        if disconnected and not self.client_list.get('OFFLINE'):
            je:dict = self.__config.get('jurassic_echoes')
            jurassic_echoes:JurassicEchoes = None
            if je:
                jurassic_echoes = JurassicEchoes(
                    cookie=je.get('cookie'), user_agent=je.get('user_agent'),
                    fetching_client=Observer(
                        je_cookie=je.get('cookie'),
                        user_agent=je.get('user_agent')
                    )
                )

            self.client_list = {
                'OFFLINE': Client(alias='Metrics Display', je=jurassic_echoes)
            }

        if new_client_list:
            self.client_list = {
                client_id: deserialize_client(client_data)
                for client_id, client_data in new_client_list.items()
            }
        
        current_clients = { cid for cid in self.client_list.keys() }
        existing_clients = { cid for cid in self.__client_widget_list.keys() }

        # Destroy widgets of disconnected clients
        for client in (existing_clients - current_clients):
            for widget in self.__client_widget_list.get(client, {}).values():
                widget.destroy()
            
            del self.__client_widget_list[client]

        # Create widgets for newly connected clients
        for client in (current_clients - existing_clients):
            data = self.client_list.get(client)

            row = len(self.__client_widget_list)

            background = ttk.Label(self.__player_frame, background=data.color)
            background.grid(row=row, column=0, padx=8, pady=8, sticky='nsew')

            frame = ttk.Frame(self.__player_frame)
            frame.grid(row=row, column=0, padx=10, pady=10, sticky='nsew')
            frame.grid_columnconfigure(0, weight=1)

            invalid_cookie_var = tk.BooleanVar(
                value=bool(data.je.invalid_cookie if data.je else True)
            )
            invalid_cookie = ttk.Checkbutton(
                frame, state='disabled', text='Invalid Cookie',
                variable=invalid_cookie_var
            )
            invalid_cookie.var = invalid_cookie_var
            invalid_cookie.grid(row=0, column=1, padx=5, pady=5, sticky='nsew')

            website_down_var = tk.BooleanVar(
                value=bool(data.je.website_down if data.je else False)
            )
            website_down = ttk.Checkbutton(
                frame, state='disabled', text='Website Down',
                variable=website_down_var
            )
            website_down.var = website_down_var
            website_down.grid(row=0, column=2, padx=5, pady=5, sticky='nsew')

            alias = ttk.Label(frame, font=('Seoge UI', 10, 'bold'),
                              text=data.alias)
            alias.grid(row=0, column=0, padx=5, pady=5, sticky='nsew')

            utc_ts = int(dt.now(tz=tz.utc).timestamp())
            last_min = (utc_ts - (data.last_coordinate_utc_ts or utc_ts)) / 60
            last_position = ttk.Label(
                frame, text=f'Last position: {last_min:.0f} minutes ago'
            )
            last_position.grid(row=1, column=0, columnspan=3, padx=5,
                               pady=(0, 5), sticky='nsew')

            je_widgets = {}
            if data.je:
                separator = ttk.Separator(frame, orient='horizontal')
                separator.grid(row=2, column=0, columnspan=3, padx=5,
                               sticky='nsew')

                species = ttk.Label(frame, font=('Seoge UI', 9, 'bold'),
                                    text=data.je.species or 'No Species')
                species.grid(row=3, column=0, padx=5, pady=5, sticky='nsew')

                balance = ttk.Label(frame, text=f'${data.je.balance or 0}',
                                    anchor='e', justify='right')
                balance.grid(row=3, column=2, padx=5, pady=5, sticky='nsew')

                stat_frame = ttk.Frame(frame)
                stat_frame.grid(row=4, column=0, columnspan=3, padx=5, pady=5,
                                sticky='nsew')
                stat_frame.grid_columnconfigure([0, 1, 2, 3], weight=1)

                HEALTH_COLOR = '#cc3d3d'
                health = ttk.Label(stat_frame, foreground=HEALTH_COLOR,
                                text='Health:')
                health.grid(row=0, column=0, sticky='nsew')
                health_percent = ttk.Label(
                    stat_frame, foreground=HEALTH_COLOR,
                    text=f'{data.je.health.percent * 100}%'
                )
                health_percent.grid(row=0, column=1, sticky='nsew')
                health_delta = ttk.Label(
                    stat_frame, foreground=HEALTH_COLOR,
                    text=f'{data.je.health.delta_rate * 100:.02f}%/min',
                )
                health_delta.grid(row=0, column=2, sticky='nsew')
                health_eta = ttk.Label(
                    stat_frame, foreground=HEALTH_COLOR,
                    text=f'{data.je.health.eta_to_bounds:.0f} min',
                )
                health_eta.grid(row=0, column=3, sticky='nsew')

                GROWTH_COLOR = '#5fbf00'
                growth = ttk.Label(stat_frame, foreground=GROWTH_COLOR,
                                text='Growth:')
                growth.grid(row=1, column=0, sticky='nsew')
                growth_percent = ttk.Label(
                    stat_frame, foreground=GROWTH_COLOR,
                    text=f'{data.je.growth.percent * 100}%'
                )
                growth_percent.grid(row=1, column=1, sticky='nsew')
                growth_delta = ttk.Label(
                    stat_frame, foreground=GROWTH_COLOR,
                    text=f'{data.je.growth.delta_rate * 100:.02f}%/min',
                )
                growth_delta.grid(row=1, column=2, sticky='nsew')
                growth_eta = ttk.Label(
                    stat_frame, foreground=GROWTH_COLOR,
                    text=f'{data.je.growth.eta_to_bounds:.0f} min',
                )
                growth_eta.grid(row=1, column=3, sticky='nsew')

                HUNGER_COLOR = '#cc8400'
                hunger = ttk.Label(stat_frame, foreground=HUNGER_COLOR,
                                text='Hunger')
                hunger.grid(row=2, column=0, sticky='nsew')
                hunger_percent = ttk.Label(
                    stat_frame, foreground=HUNGER_COLOR,
                    text=f'{data.je.hunger.percent * 100}%'
                )
                hunger_percent.grid(row=2, column=1, sticky='nsew')
                hunger_delta = ttk.Label(
                    stat_frame, foreground=HUNGER_COLOR,
                    text=f'{data.je.hunger.delta_rate * 100:.02f}%/min',
                )
                hunger_delta.grid(row=2, column=2, sticky='nsew')
                hunger_eta = ttk.Label(
                    stat_frame, foreground=HUNGER_COLOR,
                    text=f'{data.je.hunger.eta_to_bounds:.0f} min',
                )
                hunger_eta.grid(row=2, column=3, sticky='nsew')

                THIRST_COLOR = '#00b3b3'
                thirst = ttk.Label(stat_frame, foreground=THIRST_COLOR,
                                text='Thirst:')
                thirst.grid(row=3, column=0, sticky='nsew')
                thirst_percent = ttk.Label(
                    stat_frame, foreground=THIRST_COLOR,
                    text=f'{data.je.thirst.percent * 100}%'
                )
                thirst_percent.grid(row=3, column=1, sticky='nsew')
                thirst_delta = ttk.Label(
                    stat_frame, foreground=THIRST_COLOR,
                    text=f'{data.je.thirst.delta_rate * 100:.02f}%/min',
                )
                thirst_delta.grid(row=3, column=2, sticky='nsew')
                thirst_eta = ttk.Label(
                    stat_frame, foreground=THIRST_COLOR,
                    text=f'{data.je.thirst.eta_to_bounds:.0f} min',
                )
                thirst_eta.grid(row=3, column=3, sticky='nsew')

                je_widgets = {
                    'separator': separator, 'species': species,
                    'balance': balance, 'health': health,
                    'health_percent': health_percent, 'health_eta': health_eta,
                    'health_delta': health_delta, 'growth': growth,
                    'growth_percent': growth_percent, 'growth_eta': growth_eta,
                    'growth_delta': growth_delta, 'hunger': hunger,
                    'hunger_percent': hunger_percent, 'hunger_eta': hunger_eta,
                    'hunger_delta': hunger_delta, 'thirst': thirst,
                    'thirst_percent': thirst_percent, 'thirst_eta': thirst_eta,
                    'thirst_delta': thirst_delta
                }

            self.__client_widget_list[client] = {
                'frame': frame, 'background': background, 'alias': alias,
                'invalid_cookie': invalid_cookie, 'website_down': website_down,
                'last_position': last_position
            } | je_widgets
        
        # Update all values
        for client, data in self.client_list.items():
            widgets = self.__client_widget_list[client]

            utc_ts = int(dt.now(tz=tz.utc).timestamp())
            last_min = (utc_ts - (data.last_coordinate_utc_ts or utc_ts)) / 60
            widgets['last_position'].configure(
                text=f'Last position: {last_min:.0f} minutes ago'
            )

            if data.je:
                widgets['invalid_cookie'].var.set(data.je.invalid_cookie)
                widgets['website_down'].var.set(data.je.website_down)
                widgets['species'].configure(text=data.je.species)
                widgets['balance'].configure(text=f'${data.je.balance or 0}')

                widgets['health_percent'].configure(
                    text=f'{data.je.health.percent * 100:.0f}%'
                )
                widgets['health_delta'].configure(
                    text=f'{(data.je.health.delta_rate or 0) * 100:.02f}%/min'
                )
                widgets['health_eta'].configure(
                    text=f'{(data.je.health.eta_to_bounds or 0):.0f} min'
                )

                widgets['growth_percent'].configure(
                    text=f'{data.je.growth.percent * 100:.0f}%'
                )
                widgets['growth_delta'].configure(
                    text=f'{(data.je.growth.delta_rate or 0) * 100:.02f}%/min'
                )
                widgets['growth_eta'].configure(
                    text=f'{(data.je.growth.eta_to_bounds or 0):.0f} min'
                )

                widgets['hunger_percent'].configure(
                    text=f'{data.je.hunger.percent * 100:.0f}%'
                )
                widgets['hunger_delta'].configure(
                    text=f'{(data.je.hunger.delta_rate or 0) * 100:.02f}%/min'
                )
                widgets['hunger_eta'].configure(
                    text=f'{(data.je.hunger.eta_to_bounds or 0):.0f} min'
                )

                widgets['thirst_percent'].configure(
                    text=f'{data.je.thirst.percent * 100:.0f}%'
                )
                widgets['thirst_delta'].configure(
                    text=f'{(data.je.thirst.delta_rate or 0) * 100:.02f}%/min'
                )
                widgets['thirst_eta'].configure(
                    text=f'{(data.je.thirst.eta_to_bounds or 0):.0f} min'
                )

    def render_map(self, coordinate_map:dict[str, list]=None,
                   pin_map:dict[str, tuple]=None):
        """
        **Render the map and display it.**
        
        *Parameters*:
        - `coordinate_map` (dict[str, list]): The list of coordinates to render.
        - `pin_map` (dict[str, tuple]): The list of pins to render.
        """
        width = self.__canvas_frame.winfo_width()
        height = self.__canvas_frame.winfo_height()

        if not coordinate_map:
            coordinate_map = {
                client_data.color: [
                    coord.coordinates for coord in client_data.coordinates
                ]
                for client_data in self.client_list.values()
            }
        else:
            client_map = {
                client_data.color: client_id
                for client_id, client_data in self.client_list.items()
            }

            for color, coords in coordinate_map.items():
                if client_map.get(color):
                    self.client_list[client_map[color]].coordinates = [Coord(
                        utc_timestamp=0, coordinates=(coord[0], coord[1])
                    ) for coord in coords]
        
        if not pin_map:
            pin_map = {
                client_data.color: client_data.pin_position
                for client_data in self.client_list.values()
            }
        else:
            client_map = {
                client_data.color: client_id
                for client_id, client_data in self.client_list.items()
            }

            for color, pin in pin_map.items():
                if client_map.get(color):
                    self.client_list[client_map[color]].pin_position = pin

        rendered = render_scaled_image(
            self.__base_image, width, height, coordinate_map, self.__zoom,
            (self.__pan_x, self.__pan_y), pin_map,
            self.__config.get('map', {}).get('world_bounds')
        )

        self.__canvas.delete('all')
        self.__tk_image = ImageTk.PhotoImage(rendered)
        self.__canvas_image_id = self.__canvas.create_image(
            0, 0, anchor='nw', image=self.__tk_image
        )

    def __schedule_map_render(self, event:tk.Event=None):
        """
        **Schedule the map to render.**
        
        *Parameters*:
        - `event` (tk.Event): The event associated with the function call.
        """
        if self.__render_job is not None:
            self.after_cancel(self.__render_job)
        
        self.__render_job = self.after(5, self.render_map)

    def set_status_text(self, text:str, bad:bool=False):
        """
        **Sets the status text.**
        
        *Parameters*:
        - `text` (str): The text to display.
        - `bad` (bool): If the text should be frozen for a bit, and the
        foreground color to be red. Defaults to false.
        """
        utc_ts = int(dt.now(tz=tz.utc).timestamp())
        if bad and utc_ts < self.__last_status_text_utc_ts + 5: return
        if bad: self.__last_status_text_utc_ts = utc_ts

        color = '#cc3d3d' if bad else '#000000'
        self.__status_text.configure(text=text, foreground=color)

    def tgl_connect(self):
        """
        **Toggle the server connection.**
        """
        if self.__sio.connected:
            self.__sio.disconnect()
            self.connect_btn.configure(text='Connect')

            self.__schedule_map_render()
            return

        def connect_worker():
            """
            **Connects to the server in a thread to not freeze the GUI.**
            """
            try:
                oc:dict = self.__config.get('online', {})
                je:dict = self.__config.get('jurassic_echoes', {})

                self.__sio.connect(
                    f'http://{oc.get("ip")}:{oc.get("port")}',
                    auth={
                        'password': oc.get('password'),
                        'alias': oc.get('alias'),
                        'je-cookie': je.get('cookie'),
                        'user-agent': je.get('user_agent')
                    }
                )

                self.after(0, lambda: self.connect_btn.configure(
                    state='enabled', text='Disconnect'
                ))
            except Exception:
                lr.Log.warn('Issue occurred while connecting to server!')
                self.after(0, lambda: self.connect_btn.configure(
                    state='enabled', text='Connect'
                ))

        self.connect_btn.configure(state='disabled', text='Connecting...')

        self.__schedule_map_render()

        threading.Thread(target=connect_worker, daemon=True).start()

    def reset_coordinates(self):
        """
        **Reset the clients own coordinates.**
        """
        lr.Log.debug('Resetting coordinates!')

        if self.__sio.connected:
            self.__sio.emit('reset-coordinates')
        else:
            if self.client_list.get('OFFLINE'):
                self.client_list['OFFLINE'].coordinates.clear()
                self.render_map()

    def __canvas_leftclick(self, event:tk.Event=None):
        """
        **Called when the client left clicks on the canvas.**
        
        *Parameters*:
        - `event` (tk.Event): The event associated with the function call.
        """
        canvas_w = self.__canvas.winfo_width()
        canvas_h = self.__canvas.winfo_height()

        img_w, img_h = self.__base_image.size

        scale = min(canvas_w / img_w, canvas_h / img_h) * self.__zoom

        rendered_w = img_w * scale
        rendered_h = img_h * scale

        offset_x = (canvas_w - rendered_w) / 2 + self.__pan_x
        offset_y = (canvas_h - rendered_h) / 2 + self.__pan_y

        # Position relative to rendered image
        rel_x = event.x - offset_x
        rel_y = event.y - offset_y

        # Ignore clicks in letterboxing
        if not (0 <= rel_x <= rendered_w and 0 <= rel_y <= rendered_h):
            return

        # Normalize to 0..1
        nx = rel_x / rendered_w
        ny = rel_y / rendered_h

        if self.__sio.connected:
            self.__sio.emit('pin-location', [nx, ny])
        else:
            if self.client_list.get('OFFLINE'):
                self.client_list['OFFLINE'].pin_position = (nx, ny)
                self.render_map()

    def __canvas_rightclick(self, event:tk.Event=None):
        """
        **Called when the client right clicks on the canvas.**
        
        *Parameters*:
        - `event` (tk.Event): The event associated with the function call.
        """
        if self.__sio.connected:
            self.__sio.emit('pin-location', [None, None])
        else:
            if self.client_list.get('OFFLINE'):
                self.client_list['OFFLINE'].pin_position = None
                self.render_map()

    def __mousewheel(self, event:tk.Event=None):
        """
        **Called when the client scrolls the mouse wheel, hovering the canvas.**
        
        *Parameters*:
        - `event` (tk.Event): The event associated with the function call.
        """
        self.__zoom += 0.1 * (1 if event.delta > 0 else -1)
        self.__zoom = max(1.0, min(3.0, self.__zoom))

        self.render_map()

    def __pan_start(self, event:tk.Event=None):
        """
        **Called when panning starts and records positions.**
        
        *Parameters*:
        - `event` (tk.Event): The event associated with the function call.
        """
        self.__dragging = True
        self.__drag_start_x = event.x
        self.__drag_start_y = event.y

    def __pan_move(self, event:tk.Event=None):
        """
        **Called when panning moves, calculates panning offsets.**
        
        *Parameters*:
        - `event` (tk.Event): The event associated with the function call.
        """
        dx = event.x - self.__drag_start_x
        dy = event.y - self.__drag_start_y

        self.__pan_x += dx
        self.__pan_y += dy

        max_pan = int(self.__tk_image.width())
        self.__pan_x = max(-max_pan, min(max_pan, self.__pan_x))
        self.__pan_y = max(-max_pan, min(max_pan, self.__pan_y))

        self.__drag_start_x = event.x
        self.__drag_start_y = event.y

        self.render_map()

    def __pan_stop(self, event:tk.Event=None):
        """
        **Called when panning stops.**
        
        *Parameters*:
        - `event` (tk.Event): The event associated with the function call.
        """
        self.__dragging = False

    def __double_click_mouse_wheel(self, event:tk.Event=None):
        """
        **Called when the middle mouse is double clicked, resets pan and zoom.**
        
        *Parameters*:
        - `event` (tk.Event): The event associated with the function call.
        """
        self.__pan_x = 0
        self.__pan_y = 0
        self.__zoom = 1.0

        self.render_map()

    def __add_widgets(self):
        """
        **Adds widgets to the GUI.**
        """
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.__canvas_frame = ttk.Frame(self)
        self.__canvas_frame.grid(row=0, column=0, sticky='nsew')
        self.__canvas_frame.grid_rowconfigure(0, weight=1)
        self.__canvas_frame.grid_columnconfigure(0, weight=1)

        self.__canvas = tk.Canvas(self.__canvas_frame, background='black',
                                highlightthickness=0)
        self.__canvas.grid(row=0, column=0, sticky='nsew')
        self.__canvas.bind('<Configure>', self.__schedule_map_render)
        self.__canvas.bind('<ButtonRelease-1>', self.__canvas_leftclick)
        self.__canvas.bind('<ButtonRelease-3>', self.__canvas_rightclick)
        self.__canvas.bind('<MouseWheel>', self.__mousewheel)
        self.__canvas.bind('<ButtonPress-2>', self.__pan_start)
        self.__canvas.bind('<B2-Motion>', self.__pan_move)
        self.__canvas.bind('<ButtonRelease-2>', self.__pan_stop)
        self.__canvas.bind("<Double-Button-2>", self.__double_click_mouse_wheel)

        self.__sidebar_frame = ttk.Frame(self)
        self.__sidebar_frame.grid(row=0, column=1, sticky='nsew')
        self.__sidebar_frame.grid_rowconfigure(2, weight=1)
        self.__sidebar_frame.grid_columnconfigure([0, 2], weight=1)

        self.connect_btn = ttk.Button(self.__sidebar_frame, width=16,
                                      text='Connect', command=self.tgl_connect)
        self.connect_btn.grid(row=0, column=0, padx=10, pady=10, sticky='nsew')

        self.__status_text = ttk.Label(self.__sidebar_frame, anchor='center',
                                     justify='center', width=20)
        self.__status_text.grid(row=0, column=1, pady=10, sticky='nsew')

        self.__reset_coords_btn = ttk.Button(self.__sidebar_frame, width=16,
                                           text='Reset Coords',
                                           command=self.reset_coordinates)
        self.__reset_coords_btn.grid(row=0, column=2, padx=10, pady=10,
                                   sticky='nsew')
        
        separator = ttk.Separator(self.__sidebar_frame, orient='horizontal')
        separator.grid(row=1, column=0, columnspan=3, padx=10, pady=(0, 10),
                       sticky='nsew')
        
        self.__player_frame = ttk.Frame(self.__sidebar_frame)
        self.__player_frame.grid(row=2, column=0, columnspan=3, padx=10,
                               pady=(0, 10), sticky='nsew')
        self.__player_frame.grid_columnconfigure(0, weight=1)