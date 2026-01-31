from PIL import Image, ImageDraw, ImageTk
import pyperclip, os, sys
from tkinter import ttk
import loggerric as lr
import sockric as sr
import tkinter as tk

import utils

class Gui(ttk.Frame):
    def __init__(self, root:tk.Tk, client:sr.Client, config:dict):
        super().__init__(root)

        self.root = root
        self.client = client
        self.config = config

        self.identifier_label:ttk.Label = None

        self.raw_image = Image.open(utils.resource_path(
            os.path.join(os.path.dirname(__file__), self.config.get('map_path'))
        ))
        self.raw_image = self.raw_image.resize(
            tuple([round(size * self.config.get('image_scale')) for size in self.raw_image.size])
        )

        self.image = self.raw_image.copy()

        self.__add_widgets()
    
    def set_color(self, color:str) -> None:
        self.identifier_label.configure(foreground=color)

    def __cb_reset(self) -> None:
        pass

    def __cb_connect(self) -> None:
        pass

    def __add_widgets(self) -> None:
        self.connect_btn = ttk.Button(self, text='Connect', width=20, command=self.__cb_connect)
        self.connect_btn.grid(row=0, column=0, padx=5, pady=5)

        self.identifier_label = ttk.Label(self, text='YOU', foreground='#ff0000', font=('Seoge UI', 12, 'bold'))
        self.identifier_label.grid(row=0, column=1, padx=5, pady=5)

        self.reset_btn = ttk.Button(self, text='Reset Map', width=20, command=self.__cb_reset)
        self.reset_btn.grid(row=0, column=2, padx=5, pady=5)

        self.tk_image = ImageTk.PhotoImage(self.image)
        self.image_label = ttk.Label(self, image=self.tk_image)
        self.image_label.grid(row=1, column=0, columnspan=3)