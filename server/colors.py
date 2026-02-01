import loggerric as lr
import random

class ColorManager:
    """
    Manages a fixed pool of colors, allowing them to be assigned and released.
    """

    _available_colors = [
        "#F6C945",  # Gold
        "#F0672E",  # Orange
        "#2ED1C5",  # Teal
        "#A75DF0",  # Purple
        "#7BEB4F",  # Lime
        "#FF7ACD",  # Pink
        "#48C9FA",  # Cyan
        "#E63946",  # Red
    ]

    # Currently occupied colors
    _assigned_colors: set[str] = set()

    @staticmethod
    def occupy() -> str | None:
        """
        Assigns and returns a random free color from the available pool.
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
    def unassign(color:str) -> None:
        """
        Releases a previously occupied color, making it available again.

        *Parameters*:
        - `color` (str): The color hex code to release.
        """

        lr.Log.debug(f'Unassigning color: {color}')
        
        # discard avoids KeyError if color was not assigned
        ColorManager._assigned_colors.discard(color)

    @staticmethod
    def reset() -> None:
        """
        Clears all assigned colors, making the entire pool available again.
        """

        lr.Log.debug('Resetting available colors!')
        
        ColorManager._assigned_colors.clear()