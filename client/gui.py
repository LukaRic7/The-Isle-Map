import pyperclip, json, socketio, threading
from PIL import Image, ImageDraw, ImageTk
from collections import deque
from tkinter import ttk
import loggerric as lr
import tkinter as tk

import utils

class Gui(ttk.Frame):
    """
    GUI class for displaying and tracking player positions on a map.

    This class integrates clipboard monitoring, offline and online tracking,
    drawing trails on a map image, and server connection using Socket.IO.

    *Parameters*:
    - `root` (tk.Tk): The main Tkinter window.
    - `sio` (socketio.Client): Socket.IO client instance.
    - `config` (dict): Configuration dictionary with keys:
        - "map": {"path": str, "scale": float}
        - "world_bounds": {"min_x": float, "max_x": float, "min_y": float, "max_y": float}
        - "trail": {"dot_size": int}
        - "server": {"ip": str, "port": int, "pass": str}
    """
    def __init__(self, root: tk.Tk, sio: socketio.Client, config: dict):
        super().__init__(root)

        self.root = root
        self.sio = sio
        self.config = config

        # Last clipboard value
        self.last_clip: str = None
        # Label showing current player color
        self.identifier_label: ttk.Label = None

        # Queue of offline coordinates (max 10 points)
        self.offline_positions: deque[tuple] = deque(maxlen=10)
        # Default player color
        self.color = '#ff0000'

        # Load and scale map image
        self.raw_image = Image.open(utils.resource_path(
            self.config.get('map', {}).get('path')
        ))
        self.raw_image = self.raw_image.resize(
            tuple([
                round(size * self.config.get('map', {}).get('scale'))
                for size in self.raw_image.size
            ])
        )

        # Draw chess-style grid overlay on map
        self.__draw_chess_grid()

        # Copy of the image for drawing trails
        self.image = self.raw_image.copy()
        self.draw = ImageDraw.Draw(self.image)

        # Add all widgets to GUI
        self.__add_widgets()
    
        # Start periodic clipboard monitoring
        self.root.after(500, self.__check_clipboard)

    def set_color(self, color: str) -> None:
        """
        Sets the player's color and updates the identifier label.

        *Parameters*:
        - `color` (str): Hex color string, e.g., "#FF0000"
        """

        self.identifier_label.configure(foreground=color)
        self.color = color

    def __check_clipboard(self) -> None:
        """
        Periodically checks the clipboard for new coordinates.

        If valid coordinates are detected, they are added to offline positions
        and sent to the server if connected.
        """

        try:
            clip = pyperclip.paste().strip()
        except Exception:
            clip = ''

        # Only process if clipboard changed and contains valid coordinates
        if clip != self.last_clip and utils.is_valid_coords(clip):
            coords = utils.parse_coords(clip)[0:2]

            # Add to offline positions
            self.offline_positions.append(coords)
            
            self.last_clip = clip

            # Update local trail display
            self.update_positions_offline()

            # Emit update to server if connected
            if self.sio.connected:
                self.sio.emit('update-position', coords)
        
        # Repeat every 500ms
        self.root.after(500, self.__check_clipboard)

    def update_positions_online(self, players_positions: str) -> None:
        """
        Updates the map with online players' positions.

        Draws trails for each player with faded lines connecting points.

        *Parameters*:
        - `players_positions` (str): JSON string mapping colors to coordinate
        lists.
        """

        self.__clear_canvas()

        players_positions = json.loads(players_positions)

        for color, positions in players_positions.items():
            last_point: tuple[float] = None
            for coord in positions:
                # Translate world coordinates to image pixels
                x, y = utils.translate_coords(
                    coord,
                    self.raw_image.size,
                    self.config.get('world_bounds')
                )

                # Draw connecting line to previous point
                if last_point:
                    self.draw.line(
                        (last_point, (x, y)),
                        fill=utils.darken_hex_color(color, 0.3)
                    )
                
                # Draw dot at current point
                dot_size = self.config.get('trail').get('dot_size')
                self.draw.ellipse(
                    (x - dot_size, y - dot_size, x + dot_size, y + dot_size),
                    fill=color,
                    outline='black'
                )

                last_point = (x, y)

        self.update_display()

    def update_positions_offline(self) -> None:
        """
        Updates the map with offline player positions.

        Draws trails from the `offline_positions` deque.
        """

        self.__clear_canvas()

        last_point: tuple[float] = None
        for coord in self.offline_positions:
            # Translate world coordinates to image pixels
            x, y = utils.translate_coords(
                coord,
                self.raw_image.size,
                self.config.get('world_bounds')
            )

            # Draw connecting line
            if last_point:
                self.draw.line(
                    (last_point, (x, y)),
                    fill=utils.darken_hex_color(self.color, 0.3)
                )
            
            # Draw dot at current point
            dot_size = self.config.get('trail').get('dot_size')
            self.draw.ellipse(
                (x - dot_size, y - dot_size, x + dot_size, y + dot_size),
                fill=self.color,
                outline='black'
            )

            last_point = (x, y)
        
        self.update_display()

    def update_display(self) -> None:
        """
        Updates the Tkinter label with the current image.

        Converts PIL image to ImageTk format and prevents garbage collection.
        """

        self.tk_image = ImageTk.PhotoImage(self.image)
        self.image_label.configure(image=self.tk_image)
        self.image_label.image = self.tk_image  # Prevent GC

        self.update_idletasks()

    def __cb_reset(self) -> None:
        """
        Callback for the 'Reset Map' button.

        Clears offline positions, clipboard, and redraws the map.
        """

        self.offline_positions = []
        
        self.last_clip = ''
        pyperclip.copy('')

        self.__clear_canvas()

    def __cb_connect(self) -> None:
        """
        Callback for the 'Connect' button.

        Handles connection/disconnection to the Socket.IO server in a separate
        thread to avoid freezing the UI.
        """

        s_config = self.config.get('server')
        
        if self.sio.connected:
            # Disconnect if already connected
            self.connect_btn.configure(state='disabled')
            self.sio.disconnect()
            self.connect_btn.configure(state='enabled', text='Connect')
            self.set_color('#ff0000')
            self.__cb_reset()
            self.__clear_canvas()
            return

        # Function to run in a separate thread for connection
        def connect_thread():
            try:
                self.sio.connect(
                    f"http://{s_config.get('ip')}:{s_config.get('port')}",
                    auth={'password': s_config.get('pass')}
                )
                # UI updates must run in main thread
                self.connect_btn.after(0, lambda: self.connect_btn.configure(state='enabled', text='Disconnect'))
            except Exception as e:
                lr.Log.error('Error occurred on connection attempt:', e)
                self.connect_btn.after(0, lambda: self.connect_btn.configure(state='enabled', text='Connect'))

        # Disable button immediately in main thread
        self.connect_btn.configure(state='disabled', text='Connecting')
        
        # Start connection in a new thread
        threading.Thread(target=connect_thread, daemon=True).start()
        
        # Reset offline data and canvas
        self.__cb_reset()
        self.__clear_canvas()

    def __clear_canvas(self) -> None:
        """Clears all drawings on the map and restores the original image."""

        self.image = self.raw_image.copy()
        self.draw = ImageDraw.Draw(self.image)

        self.update_display()

    def __add_widgets(self) -> None:
        """
        Adds all GUI widgets (buttons, labels, image display) to the frame.
        """

        self.connect_btn = ttk.Button(self, text='Connect', width=20, command=self.__cb_connect)
        self.connect_btn.grid(row=0, column=0, padx=5, pady=5)

        self.identifier_label = ttk.Label(
            self, text='YOU', foreground='#ff0000', font=('Seoge UI', 12, 'bold')
        )
        self.identifier_label.grid(row=0, column=1, padx=5, pady=5)

        self.reset_btn = ttk.Button(self, text='Reset Map', width=20, command=self.__cb_reset)
        self.reset_btn.grid(row=0, column=2, padx=5, pady=5)

        # Initial map display
        self.tk_image = ImageTk.PhotoImage(self.image)
        self.image_label = ttk.Label(self, image=self.tk_image)
        self.image_label.grid(row=1, column=0, columnspan=3)

    def __draw_chess_grid(self) -> None:
        """
        Draws a chessboard-style grid on the map image.

        Adds vertical and horizontal lines and labels (A-H, 1-8).
        """

        cols = 8
        rows = 8

        w, h = self.raw_image.size
        cell_w = w / cols
        cell_h = h / rows

        draw = ImageDraw.Draw(self.raw_image)

        # Semi-transparent white lines
        line_color = (255, 255, 255, 160)

        # Draw vertical lines
        for c in range(cols + 1):
            x = c * cell_w
            draw.line((x, 0, x, h), fill=line_color, width=1)

        # Draw horizontal lines
        for r in range(rows + 1):
            y = r * cell_h
            draw.line((0, y, w, y), fill=line_color, width=1)

        # Draw chess labels
        letters = "ABCDEFGH"

        for c in range(cols):
            draw.text((c * cell_w + 15, 5), letters[c], fill=line_color)

        for r in range(rows):
            draw.text((5, r * cell_h + 15), str(r + 1), fill=line_color)