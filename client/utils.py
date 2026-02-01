import os, sys

# Relative path, compilation safe
def resource_path(relative_path: str) -> str:
    """
    Returns the full path to a relative path. Compilation safe.

    *Parameters*:
    - `relative_path` (str): The path from "." to the target.
    """
    try:
        # If running as a PyInstaller bundle
        base_path = sys._MEIPASS
    except AttributeError:
        # If running as a normal script
        base_path = os.path.dirname(__file__)
    
    # Combine base path with relative path
    return os.path.join(base_path, relative_path)

def translate_coords(coord: tuple[float, float], image_size: tuple[int, int], bounds: dict) -> tuple[int, int]:
    """
    Translates coordinates from a defined bounding box to pixel coordinates for
    an image.

    *Parameters*:
    - `coord` (tuple[float, float]): The original (x, y) coordinates to
    translate.
    - `image_size` (tuple[int, int]): Width and height of the target image.
    - `bounds` (dict): Dictionary with min/max bounds for x and y:
        {"min_x": float, "max_x": float, "min_y": float, "max_y": float}
    """
    x, y = coord
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

def darken_hex_color(hex_color: str, percent: float = 0.3) -> str:
    """
    Darkens a hex color by a given percentage.

    *Parameters*:
    - `hex_color` (str): Hexadecimal color string, e.g., "#FFAA00".
    - `percent` (float): Fraction to darken the color by (default 0.3 = 30%).
    """
    hex_color = hex_color.lstrip('#')

    # Convert hex to RGB components
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    # Apply darkening factor and clamp to [0, 255]
    r = max(0, min(255, int(r * (1 - percent))))
    g = max(0, min(255, int(g * (1 - percent))))
    b = max(0, min(255, int(b * (1 - percent))))

    return f'#{r:02X}{g:02X}{b:02X}'

def is_valid_coords(s: str) -> bool:
    """
    Validates if a string represents a proper coordinate list.

    *Parameters*:
    - `s` (str): Input string containing coordinates.
    """
    s = s.replace(' ', '')
    if s.count(',') != 5:  # Must have 5 commas => 6 values
        return False
    try:
        for part in s.split(','):
            float(part)  # Check if each part is numeric
        return True
    except ValueError:
        return False

def parse_coords(coords: str) -> list[float]:
    """
    Parses every other number from a comma-separated coordinate string.

    *Parameters*:
    - `coords` (str): Comma-separated string of coordinates.
    """
    parsed_coords = []
    for index, segment in enumerate(coords.split(',')):
        if index % 2 != 0:  # Skip every odd index (y-coordinates)
            continue
        parsed_coords.append(float(segment))
    return parsed_coords