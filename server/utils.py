import os, sys

# Relative path, compilation safe
def resource_path(relative_path:str) -> str:
    """
    Returns the full path to a relative path. Compilation safe.

    *Parameters*:
    - `relative_path` (str): The path from "." to the target.
    """

    try:
        # Compiled
        base_path = sys._MEIPASS
    except AttributeError:
        # Interpreted
        base_path = os.path.dirname(__file__)
    
    # Join the paths and return the result
    return os.path.join(base_path, relative_path)