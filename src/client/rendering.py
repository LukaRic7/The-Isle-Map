from PIL import Image, ImageDraw
from pathlib import Path
import sys

# Handle both normal execution and PyInstaller bundled exe
if getattr(sys, 'frozen', False):
    # Running as PyInstaller exe
    ROOT = Path(sys._MEIPASS).parent
else:
    # Running as script
    ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.colors import darken_hex_color

def translate_coords(coord:tuple[float, float], image_size:tuple[int, int],
                     bounds:dict) -> tuple[int, int]:
    """
    **Translates coordinates from a defined bounding box to pixel coordinates
    for an image.**

    *Parameters*:
    - `coord` (tuple[float, float]): The original (x, y) coordinates to
    translate.
    - `image_size` (tuple[int, int]): Width and height of the target image.
    - `bounds` (dict): Dictionary with min/max bounds for x and y:
        {"min_x": float, "max_x": float, "min_y": float, "max_y": float}

    *Returns*:
    - (tuple[int, int]): The translated x,y on the image.
    """
    y, x = coord
    w, h = image_size

    min_x = bounds['min_x']
    max_x = bounds['max_x']
    min_y = bounds['min_y']
    max_y = bounds['max_y']

    # Scale x relative to image width
    px = (x - min_x) / (max_x - min_x) * w

    # Scale y relative to image height, flip vertically
    py = h - (y - min_y) / (max_y - min_y) * h

    return int(px), int(py)

def render_scaled_image(base_image:Image.Image, target_width:int,
                        target_height:int, coordinates:dict[str, list[tuple]],
                        pin_map:dict[str, tuple],
                        bounds:dict[str, int]) -> Image.Image:
    """
    **Render a scaled image of the map, rendering coords and chess grid.**
    
    *Parameters*:
    - `base_image` (Image.Image): The base image of the map.
    - `target_width` (int): The target width of the image.
    - `target_height` (int): The target height of the image.
    - `coordinates` (dict[str, list[tuple]]): Coordinates of all clients to
    render onto the map.
    - `bounds` (dict[str, int]): Bounds of the ingame map so the coords can be
    correctly translated onto the map.
    
    *Returns*:
    - (Image.Image): The rendered image.
    """

    base_width, base_height = base_image.size
    scale = min(target_width / base_width, target_height / base_height)
    new_size = (int(base_width * scale), int(base_height * scale))
    
    resized = base_image.resize(new_size, Image.Resampling.LANCZOS)
    resized = resized.convert('RGBA')

    letterboxing_color = resized.getpixel((0, 0))
    canvas = Image.new('RGBA', (target_width, target_height), letterboxing_color)

    offset_x = (target_width - new_size[0]) // 2
    offset_y = (target_height - new_size[1]) // 2

    canvas.paste(resized, (offset_x, offset_y))

    overlay = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Pin locations
    for color, pin_scale in pin_map.items():
        if not pin_scale: continue

        x = new_size[0] * pin_scale[0] + offset_x
        y = new_size[1] * pin_scale[1] + offset_y

        radius = int(new_size[0] * 0.03)

        draw.circle((x, y), radius=radius, fill=None, outline=color, width=2)

    # Location lines
    for color, coordlist in coordinates.items():
        # Precompute coords
        translated = []
        for coords in coordlist:
            x, y = translate_coords(coords, new_size, bounds)
            translated.append((x + offset_x, y + offset_y))
        
        # Draw connecting line
        if len(translated) > 1:
            for i in range(len(translated) - 1):
                draw.line(
                    (translated[i], translated[i + 1]),
                    fill=darken_hex_color(color, 0.4),
                    width=int(new_size[0] * 0.005)
                )
        
        # Draw dots
        for i, (x, y) in enumerate(translated):
            if i == len(translated) - 1:
                radius = int(new_size[0] * 0.008)
                draw.ellipse(
                    (x - radius, y - radius, x + radius, y + radius),
                    fill=color, outline='#ffffff', width=1
                )
            else:
                radius = int(new_size[0] * 0.005)
                try:
                    history_dot_color = darken_hex_color(color, 0.2)
                except Exception:
                    history_dot_color = color
                
                draw.ellipse(
                    (x - radius, y - radius, x + radius, y + radius),
                    fill=history_dot_color, outline=None
                )

    # Chess grid
    cell_size = new_size[0] / 8

    color = (255, 255, 255, 128)

    for c in range(9):
        x = offset_x + (c * cell_size)
        draw.line((x, offset_y, x, offset_y + new_size[0]), fill=color, width=1)
    
    for r in range(9):
        y = offset_y + (r * cell_size)
        draw.line((offset_x, y, offset_x + new_size[0], y), fill=color, width=1)
    
    for c in range(8):
        x = offset_x + (c * cell_size) + 15
        y = offset_y + 5
        draw.text((x, y), 'ABCDEFGH'[c], fill=color)
    
    for r in range(8):
        x = offset_x + 5
        y = offset_y + (r * cell_size) + 15
        draw.text((x, y), str(r + 1), fill=color)
    
    return Image.alpha_composite(canvas, overlay)