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
        base_path = os.path.abspath('.')
    
    # Join the paths and return the result
    return os.path.join(base_path, relative_path)

# Get the exe path when compiled
def get_exe_path(relative_path: str) -> str:
    """Get the folder where the exe or script is located."""

    if getattr(sys, 'frozen', False):
        # Compiled with PyInstaller
        return os.path.join(os.path.dirname(sys.executable), relative_path)

    # Running as script
    return os.path.join(os.path.abspath('.'), relative_path)