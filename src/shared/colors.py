import loggerric as lr
import random

def darken_hex_color(hex_color:str, percent:float) -> str:
    """
    Darkens a hex color by a given percentage.

    *Parameters*:
    - `hex_color` (str): Hexadecimal color string, e.g., "#FFAA00".
    - `percent` (float): Fraction to darken the color by (default 0.3 = 30%).

    *Returns*:
    - (str): The darkened hex color.
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

class ColorManager:
    """
    **Manages a fixed pool of colors, allowing them to be assigned and
    released.**
    
    *Methods*:
    - `occupy() -> str | None`: Assigns and returns a random free color from
    the available pool.
    - `unassign(color) -> None`: Releases a previously occupied color, making
    it available again.
    - `reset() -> None`: Clears all assigned colors, making the entire pool
    available again.
    """
    _available_colors = [
        "#0072B2",  # Blue
        "#E69F00",  # Amber
        "#009E73",  # Teal Green
        "#CC79A7",  # Magenta
        "#D55E00",  # Vermillion
        "#56B4E9",  # Sky Blue
    ]

    # Currently occupied colors
    _assigned_colors: set[str] = set()

    @staticmethod
    def occupy() -> str | None:
        """
        **Assigns and returns a random free color from the available pool.**
        
        *Returns*:
        - (str): The newly selected color.
        """

        # Build a list of colors that are not currently assigned
        free_colors = [
            c
            for c in ColorManager._available_colors
            if c not in ColorManager._assigned_colors
        ]

        # All colors are occupied
        if not free_colors:
            return None

        # Randomly pick one free color
        color = random.choice(free_colors)

        # Mark the color as occupied
        ColorManager._assigned_colors.add(color)

        lr.Log.debug(f'Occupying color: {color}')

        return color

    @staticmethod
    def unassign(color:str):
        """
        **Releases a previously occupied color, making it available again.**

        *Parameters*:
        - `color` (str): The color hex code to release.
        """

        lr.Log.debug(f'Unassigning color: {color}')
        
        # discard avoids KeyError if color was not assigned
        ColorManager._assigned_colors.discard(color)

    @staticmethod
    def reset():
        """
        **Clears all assigned colors, making the entire pool available again.**
        """

        lr.Log.debug('Resetting available colors!')
        
        ColorManager._assigned_colors.clear()