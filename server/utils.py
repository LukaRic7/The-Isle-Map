from datetime import datetime
import os, sys

# Relative path, compilation safe
def resource_path(relative_path:str) -> str:
    """
    **Returns the full path to a relative path. Compilation safe.**
    
    *Parameters*:
    - `relative_path` (str): The path from "." to the target.
    
    *Returns*:
    - (str): The full path to the target.
    """

    try:
        # If running as a PyInstaller bundle
        base_path = sys._MEIPASS
    except AttributeError:
        # If running as a normal script
        base_path = os.path.abspath('.')
    
    # Combine base path with relative path
    return os.path.join(base_path, relative_path)

def get_seconds_till_next_minute() -> int:
    """
    **Get the amount of seconds to the next minute hits.**
    
    *Returns*:
    - (int): The amount of seconds until the next minute hits.
    """

    now = datetime.now()
    return 60 - now.second

# Get the exe path when compiled
def get_exe_path(relative_path:str) -> str:
    """
    **Get the folder where the exe or script is located.**
    
    *Parameters*:
    - `relative_path` (str): The path from "." to the target.
    
    *Returns*:
    - (str): The full path to the target.
    """

    if getattr(sys, 'frozen', False):
        # Compiled with PyInstaller
        return os.path.join(os.path.dirname(sys.executable), relative_path)

    # Running as script
    return os.path.join(os.path.abspath('.'), relative_path)