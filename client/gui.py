import pyperclip, json, socketio, threading, math, time
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageTk
from dataclasses import dataclass, field
from collections import deque
from tkinter import ttk
import loggerric as lr
import tkinter as tk

from utils import get_exe_path, get_seconds_till_next_minute, darken_hex_color, translate_coords
from fetch import Observer

@dataclass
class PlayerInformation:
    je_cookie:str=None
    color:str=None
    coordinates:deque[dict]=field(default_factory=lambda: deque(maxlen=5)) # [{ 'utc_timestamp': 0, 'coordinates': '...' }, ...]
    species:str=None
    health:dict=field(default_factory=dict) # { 'percent': 0, 'deltarate': 0, 'eta_top': -0 }
    growth:dict=field(default_factory=dict) # { -||- }
    hunger:dict=field(default_factory=dict) # { -||- }
    thirst:dict=field(default_factory=dict) # { -||- }
    balance:int=None
    alias:str='No Username'

class Gui(ttk.Frame):
    def __init__(self, root:tk.Tk, sio:socketio.Client, config:dict):
        super().__init__(root)

        self.root = root
        self.sio = sio
        self.config = config
        self.je_fetcher = Observer(self.config.get('je_cookie'), self.config.get('user_agent'))

        self.raw_image = Image.open(get_exe_path(self.config.get('map', {}).get('path')))
        self.render_image = None
        self.tk_image:ImageTk.PhotoImage = None

        self._render_job = None
        self._rendering = False
        self.canvas_image_id = None

        self.player_list:dict = {}
        self.player_list_widgets:dict = {}
        self.offline_stats = PlayerInformation(
            je_cookie=config.get('je_cookie'), color='#ff0000',
            alias=config.get('online', {}).get('alias', 'No Username')
        )
        self.online_mode = False
        self.je_thread:threading.Thread = None

        self.kill_threads = False
        root.protocol("WM_DELETE_WINDOW", self.__on_close)

        self.__add_widgets()

    def __on_close(self):
        self.kill_threads = True

    def __render_scaled_image(self, target_width:int, target_height:int):
        base = self.raw_image

        bw, bh = base.size
        scale = min(target_width / bw, target_height / bh)

        new_size = (int(bw * scale), int(bh * scale))
        resized = base.resize(new_size, Image.Resampling.LANCZOS).convert('RGBA')

        canvas = Image.new('RGBA', (target_width, target_height), self.config.get('map').get('letterboxing_color'))

        offset_x = (target_width - new_size[0]) // 2
        offset_y = (target_height - new_size[1]) // 2

        canvas.paste(resized, (offset_x, offset_y))

        chess_overlay = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(chess_overlay)

        # Player coords
        #self.update()
        print('__render_scaled_image', self.online_mode, self.sio.connected)
        if self.online_mode and self.sio.connected:
            for client_id, player_data in self.player_list.items():
                if not player_data: continue

                translated_points = []
                base_color = player_data.get('color')
                for data in player_data.get('coordinates', []):
                    coords = data.get('coordinates')
                    if coords:
                        mx, my = translate_coords(coords, new_size, self.config.get('map', {}).get('world_bounds'))
                        x = offset_x + mx
                        y = offset_y + my
                        translated_points.append((x, y))

                initial_size = self.canvas_frame.winfo_width()

                if len(translated_points) > 1:
                    line_color = darken_hex_color(base_color, 0.4)
                    for i in range(len(translated_points) - 1):
                        draw.line((translated_points[i], translated_points[i + 1]), fill=line_color, width=int(initial_size * 0.005))

                for i, (x, y) in enumerate(translated_points):
                    if i == len(translated_points) - 1:
                        radius = int(initial_size * 0.01)
                        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=base_color, outline="#ffffff", width=1)
                    else:
                        radius = int(initial_size * 0.005)
                        try:
                            history_dot_color = darken_hex_color(base_color, 0.2)
                        except Exception:
                            history_dot_color = base_color
                            
                        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=history_dot_color, outline=None)
        else:
            translated_points = []
            base_color = self.offline_stats.color
            for data in self.offline_stats.coordinates:
                coords = data.get('coordinates')
                if coords:
                    mx, my = translate_coords(coords, new_size, self.config.get('map', {}).get('world_bounds'))
                    x = offset_x + mx
                    y = offset_y + my
                    translated_points.append((x, y))

            initial_size = self.canvas_frame.winfo_width()

            if len(translated_points) > 1:
                line_color = darken_hex_color(base_color, 0.4)
                for i in range(len(translated_points) - 1):
                    draw.line((translated_points[i], translated_points[i + 1]), fill=line_color, width=int(initial_size * 0.005))

            for i, (x, y) in enumerate(translated_points):
                if i == len(translated_points) - 1:
                    radius = int(initial_size * 0.01)
                    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=base_color, outline="#ffffff", width=1)
                else:
                    radius = int(initial_size * 0.005)
                    try:
                        history_dot_color = darken_hex_color(base_color, 0.2)
                    except Exception:
                        history_dot_color = base_color
                        
                    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=history_dot_color, outline=None)

        # Chess grid
        cols = 8
        rows = 8
        cell_w = new_size[0] / cols
        cell_h = new_size[1] / rows

        line_color = (255, 255, 255, 128)

        for c in range(cols + 1):
            x = offset_x + (c * cell_w)
            draw.line((x, offset_y, x, offset_y + new_size[1]), fill=line_color, width=1)

        for r in range(rows + 1):
            y = offset_y + (r * cell_h)
            draw.line((offset_x, y, offset_x + new_size[0], y), fill=line_color, width=1)

        letters = 'ABCDEFGH'

        for c in range(cols):
            x = offset_x + (c * cell_w) + 15
            y = offset_y + 5
            draw.text((x, y), letters[c], fill=line_color)

        for r in range(rows):
            x = offset_x + 5
            y = offset_y + (r * cell_h) + 15
            draw.text((x, y), str(r + 1), fill=line_color)

        final_canvas = Image.alpha_composite(canvas, chess_overlay)

        return final_canvas, scale, (offset_x, offset_y)

    def render_map(self):
        if self._rendering: return
        self._rendering = True

        w = self.canvas_frame.winfo_width()
        h = self.canvas_frame.winfo_height()

        if w < 50 or h < 50:
            self._rendering = False
            return

        rendered, scale, offset = self.__render_scaled_image(w, h)

        self.canvas.delete('all')

        self.tk_image = ImageTk.PhotoImage(rendered)
        self.canvas_image_id = self.canvas.create_image(0, 0, anchor='nw', image=self.tk_image)

        self._rendering = False

    def __schedule_render(self, event=None):
        if self._render_job is not None:
            self.after_cancel(self._render_job)
        
        self._render_job = self.after(10, self.render_map)

    def redraw_player_list(self):
        for _ in range(60):
            self.update() # Give time for the variables to update
        print('redraw_player_list', self.online_mode, self.sio.connected)
    
        if self.online_mode and self.sio.connected:
            self.player_list_widgets['OFFLINE'] = None

            for child in self.player_frame.winfo_children():
                child.destroy()
            self.player_list_widgets.clear()

            for index, (client_id, client_data) in enumerate(self.player_list.copy().items()):
                if self.player_list_widgets.get(client_id) == None:
                    self.player_list_widgets[client_id] = {}
                
                    label_frame = ttk.Labelframe(self.player_frame, text=client_data.get('alias'))
                    label_frame.grid(row=index, column=0, padx=10, pady=10, sticky='new')

                    stats_frame = ttk.Frame(label_frame)
                    stats_frame.grid(row=1, column=0, padx=10, pady=10, sticky='nsew')

                    color_bar = ttk.Label(label_frame, font=('Seoge UI', 3), background=client_data.get('color'))
                    color_bar.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 0), sticky='nsew')

                    for index, stat in enumerate(['health', 'growth', 'hunger', 'thirst']):
                        color = { 'health': '#cc3d3d', 'growth': '#5fbf00', 'hunger': '#cc8400', 'thirst': '#00b3b3' }[stat]

                        title = ttk.Label(stats_frame, text=f'{stat.title()}:', foreground=color)
                        title.grid(row=index, column=0, padx=10, sticky='nsew')

                        percent = ttk.Label(stats_frame, text='-%', foreground=color)
                        percent.grid(row=index, column=1, padx=10, sticky='nsew')

                        change = ttk.Label(stats_frame, text='0.00%/m', foreground=color)
                        change.grid(row=index, column=2, padx=10, sticky='nsew')

                        eta = ttk.Label(stats_frame, text='0 min', foreground=color)
                        eta.grid(row=index, column=3, padx=10, sticky='nsew')

                        self.player_list_widgets[client_id][stat] = {
                            'percent': percent, 'change': change, 'eta': eta
                        }

                    insight_frame = ttk.Frame(label_frame)
                    insight_frame.grid(row=1, column=1, padx=10, pady=10, sticky='nsew')

                    last_position = ttk.Label(insight_frame, anchor='center', justify='center', text='Last position:\n- minutes ago')
                    last_position.grid(row=0, column=0, padx=10, sticky='nsew')
                    
                    balance = ttk.Label(insight_frame, anchor='center', justify='center', text=f'Balance:\n$-')
                    balance.grid(row=1, column=0, padx=10, pady=(10, 0), sticky='nsew')

                    self.player_list_widgets[client_id]['label_frame'] = label_frame
                    self.player_list_widgets[client_id]['balance'] = balance
                    self.player_list_widgets[client_id]['last_position'] = last_position

                self.player_list_widgets[client_id]['balance'].configure(text=f'Balance:\n${client_data.get("balance") or 0}')

                self.player_list_widgets[client_id]['label_frame'].configure(text=f'{client_data.get("alias")} - {client_data.get("species")}')

                now_utc_ts = int(datetime.now(tz=timezone.utc).timestamp())
                if len(client_data.get('coordinates') or []) > 0:
                    last_pos_ts = client_data['coordinates'][-1]
                    minutes_ago = math.floor((now_utc_ts - last_pos_ts['utc_timestamp']) / 60)
                    self.player_list_widgets[client_id]['last_position'].configure(text=f'Last position:\n{minutes_ago} minutes ago')
                
                for index, (key, stat) in enumerate([
                    ('health', client_data['health']), ('growth', client_data['growth']),
                    ('hunger', client_data['hunger']), ('thirst', client_data['thirst'])]):
                    self.player_list_widgets[client_id][key]['percent'].configure(text=f"{(stat.get('percent', 0) or 0) * 100:.0f}%")
                    self.player_list_widgets[client_id][key]['change'].configure(text=f"{(stat.get('deltarate', 0) or 0) * 100:.2f}%/m")
                    self.player_list_widgets[client_id][key]['eta'].configure(text=f"{stat.get('eta_top', 0) or 0:.0f} min")
        else:
            if self.player_list_widgets.get('OFFLINE') == None:
                self.player_list_widgets['OFFLINE'] = {}

                label_frame = ttk.Labelframe(self.player_frame, text=self.offline_stats.alias)
                label_frame.grid(row=0, column=0, padx=10, pady=10, sticky='new')

                stats_frame = ttk.Frame(label_frame)
                stats_frame.grid(row=1, column=0, padx=10, pady=10, sticky='nsew')

                color_bar = ttk.Label(label_frame, font=('Seoge UI', 3), background='#ff0000')
                color_bar.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 0), sticky='nsew')

                for index, stat in enumerate(['health', 'growth', 'hunger', 'thirst']):
                    color = { 'health': '#cc3d3d', 'growth': '#5fbf00', 'hunger': '#cc8400', 'thirst': '#00b3b3' }[stat]

                    title = ttk.Label(stats_frame, text=f'{stat.title()}:', foreground=color)
                    title.grid(row=index, column=0, padx=10, sticky='nsew')

                    percent = ttk.Label(stats_frame, text='-%', foreground=color)
                    percent.grid(row=index, column=1, padx=10, sticky='nsew')

                    change = ttk.Label(stats_frame, text='0.00%/m', foreground=color)
                    change.grid(row=index, column=2, padx=10, sticky='nsew')

                    eta = ttk.Label(stats_frame, text='0 min', foreground=color)
                    eta.grid(row=index, column=3, padx=10, sticky='nsew')

                    self.player_list_widgets['OFFLINE'][stat] = {
                        'percent': percent, 'change': change, 'eta': eta
                    }

                insight_frame = ttk.Frame(label_frame)
                insight_frame.grid(row=1, column=1, padx=10, pady=10, sticky='nsew')

                last_position = ttk.Label(insight_frame, anchor='center', justify='center', text='Last position:\n- minutes ago')
                last_position.grid(row=0, column=0, padx=10, sticky='nsew')
                
                balance = ttk.Label(insight_frame, anchor='center', justify='center', text=f'Balance:\n$-')
                balance.grid(row=1, column=0, padx=10, pady=(10, 0), sticky='nsew')

                self.player_list_widgets['OFFLINE']['label_frame'] = label_frame
                self.player_list_widgets['OFFLINE']['balance'] = balance
                self.player_list_widgets['OFFLINE']['last_position'] = last_position
            
            self.player_list_widgets['OFFLINE']['balance'].configure(text=f'Balance:\n${self.offline_stats.balance}')

            self.player_list_widgets['OFFLINE']['label_frame'].configure(text=f'{self.offline_stats.alias} - {self.offline_stats.species}')

            now_utc_ts = int(datetime.now(tz=timezone.utc).timestamp())
            if len(self.offline_stats.coordinates) > 0:
                last_pos_ts = self.offline_stats.coordinates[-1]
                minutes_ago = math.floor((now_utc_ts - last_pos_ts['utc_timestamp']) / 60)
                self.player_list_widgets['OFFLINE']['last_position'].configure(text=f'Last position:\n{minutes_ago} minutes ago')
            
            for index, (key, stat) in enumerate([
                ('health', self.offline_stats.health), ('growth', self.offline_stats.growth),
                ('hunger', self.offline_stats.hunger), ('thirst', self.offline_stats.thirst)]):
                self.player_list_widgets['OFFLINE'][key]['percent'].configure(text=f"{(stat.get('percent', 0) or 0) * 100:.0f}%")
                self.player_list_widgets['OFFLINE'][key]['change'].configure(text=f"{(stat.get('deltarate', 0) or 0) * 100:.2f}%/m")
                self.player_list_widgets['OFFLINE'][key]['eta'].configure(text=f"{stat.get('eta_top', 0) or 0:.0f} min")
            
    def on_new_local_coords(self, coords:tuple[float, float]):
        lr.Log.debug(f'New coordinates detected: {coords}', highlight=coords)

        if self.online_mode:
            self.sio.emit('position-update', (coords, int(datetime.now(tz=timezone.utc).timestamp())))
        else:
            self.offline_stats.coordinates.append({
                'utc_timestamp': int(datetime.now(tz=timezone.utc).timestamp()),
                'coordinates': coords
            })

        self.root.after(0, self.render_map)
        self.root.after(0, self.redraw_player_list)

    def je_worker(self):
        lr.Log.debug('JE Worker started!')
        while not self.online_mode and not self.kill_threads:
            data = self.je_fetcher.fetch()
            if data:
                self.offline_stats.health = {
                    'percent': data.get('current').get('Health'),
                    'deltarate': data.get('delta-per-min', {}).get('Health'),
                    'eta_top': data.get('est-time-min', {}).get('Health')
                }
                self.offline_stats.growth = {
                    'percent': data.get('current').get('Growth'),
                    'deltarate': data.get('delta-per-min', {}).get('Growth'),
                    'eta_top': data.get('est-time-min', {}).get('Growth')
                }
                self.offline_stats.hunger = {
                    'percent': data.get('current').get('Hunger'),
                    'deltarate': data.get('delta-per-min', {}).get('Hunger'),
                    'eta_top': data.get('est-time-min', {}).get('Hunger')
                }
                self.offline_stats.thirst = {
                    'percent': data.get('current').get('Thirst'),
                    'deltarate': data.get('delta-per-min', {}).get('Thirst'),
                    'eta_top': data.get('est-time-min', {}).get('Thirst')
                }
                self.offline_stats.balance = data.get('balance')
                self.offline_stats.species = data.get('dinosaur')

            self.root.after(0, self.redraw_player_list)

            time.sleep(get_seconds_till_next_minute())
        
        lr.Log.debug('JE Worker killed!')

    def update_countdown(self):
        self.je_countdown.configure(text=f'Updating stats in:\n{get_seconds_till_next_minute() + 3} seconds')

        self.root.after(1000, self.update_countdown)

    def reset_map(self):
        self.offline_stats.coordinates = []

        self.root.after(0, self.render_map)

    def heartbeat_worker(self):
        """
        **Called by a thread. Sends heartbeats to the server.**
        """
        while not self.kill_threads and self.sio.connected:
            try:
                self.sio.call('heartbeat', timeout=2)
            except (socketio.exceptions.TimeoutError, socketio.exceptions.BadNamespaceError):
                lr.Log.warn("Heartbeat didn't reach server!")

            time.sleep(5)

    def __connect(self):
        if self.sio.connected:
            self.connect_btn.configure(state='disabled')
            self.sio.disconnect()
            self.connect_btn.configure(state='enabled', text='Connect')
            self.reset_map_btn.configure(state='enabled')

            for child in self.player_frame.winfo_children():
                child.destroy()

            self.reset_map()
            self.redraw_player_list()
            self.online_mode = False
            return
        
        def connect_thread():
            try:
                oc:dict = self.config.get('online')
                self.sio.connect(f'http://{oc.get("ip")}:{oc.get("port")}', auth={
                    'password': oc.get('password'), 'je-cookie': self.config.get('je_cookie'),
                    'alias': oc.get('alias'), 'user-agent': self.config.get('user_agent')
                })

                # UI updates must run in main thread
                self.online_mode = True
                self.connect_btn.after(0, lambda: self.connect_btn.configure(state='enabled', text='Disconnect'))
                self.connect_btn.after(0, lambda: self.reset_map_btn.configure(state='disabled'))

                for child in self.player_frame.winfo_children():
                    child.destroy()

                threading.Thread(target=self.heartbeat_worker, daemon=True).start()
            except Exception as e:
                lr.Log.error('Error occurred on connection attempt:', e)
                self.connect_btn.after(0, lambda: self.connect_btn.configure(state='enabled', text='Connect'))

        self.connect_btn.configure(state='disabled', text='Connecting')

        threading.Thread(target=connect_thread, daemon=True).start()

        self.reset_map()

    def __add_widgets(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.canvas_frame = ttk.Frame(self)
        self.canvas_frame.grid(row=0, column=0, sticky='nsew')
        self.canvas_frame.grid_rowconfigure(0, weight=1)
        self.canvas_frame.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(self.canvas_frame, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky='nsew')

        self.canvas.bind('<Configure>', self.__schedule_render)

        self.sidebar_frame = ttk.Frame(self)
        self.sidebar_frame.grid(row=0, column=1, sticky='nsew')
        self.sidebar_frame.grid_rowconfigure(2, weight=1)
        self.sidebar_frame.grid_columnconfigure([0, 2], weight=1)

        self.connect_btn = ttk.Button(self.sidebar_frame, width=20, text='Connect', command=self.__connect)
        self.connect_btn.grid(row=0, column=0, padx=10, pady=10, sticky='nsew')

        self.je_countdown = ttk.Label(self.sidebar_frame, anchor='center', justify='center', text='Updating stats in:\n- seconds')
        self.je_countdown.grid(row=0, column=1, padx=10, pady=10, sticky='nsew')
        self.update_countdown()

        self.reset_map_btn = ttk.Button(self.sidebar_frame, width=20, text='Reset Map', command=self.reset_map)
        self.reset_map_btn.grid(row=0, column=2, padx=10, pady=10, sticky='nsew')

        seperator = ttk.Separator(self.sidebar_frame, orient='horizontal')
        seperator.grid(row=1, column=0, columnspan=3, padx=10, pady=(0, 10), sticky='new')

        self.player_frame = ttk.Frame(self.sidebar_frame)
        self.player_frame.grid(row=2, column=0, columnspan=3, padx=10, pady=(0, 10), sticky='nsew')
        self.player_frame.grid_columnconfigure(0, weight=1)

        self.je_thread = threading.Thread(target=self.je_worker, daemon=True)
        self.je_thread.start()

        self.redraw_player_list()