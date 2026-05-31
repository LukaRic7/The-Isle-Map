from typing import Optional, Union
from pathlib import Path
import sys

_PROJECT_ROOT: Optional[Path] = None

def __get_base_path() -> Path:
    """
    **Returns the base path used for resource resolution, either from a
    PyInstaller bundle or the initialized project root.**

    *Returns*:
    - (Path): The base filesystem path for resolving resources.
    """
    try:
        return Path(sys._MEIPASS)
    except AttributeError:
        return get_project_root()

def set_project_root(root:Union[str, Path]):
    """
    **Initialize the application project root from the entrypoint.**

    *Parameters*:
    - `root` (Union[str, Path]): The absolute or relative path to the project
    root directory.
    """
    global _PROJECT_ROOT
    _PROJECT_ROOT = Path(root).resolve()

def get_project_root() -> Path:
    """
    **Return the initialized project root.**

    *Returns*:
    - (Path): The resolved project root path.
    """
    if _PROJECT_ROOT is None:
        raise RuntimeError(
            'Project root is not initialized. Call set_project_root() from the'
            + 'application entrypoint.'
        )

    return _PROJECT_ROOT

def resource_path(relative_path: str) -> str:
    """
    **Returns the full path to a relative path, resolved from the initialized
    project root.**

    *Parameters*:
    - `relative_path` (str): A path relative to the project root or bundle base.

    *Returns*:
    - (str): The resolved absolute filesystem path as a string.
    """
    return str((__get_base_path() / relative_path).resolve())

def get_exe_path(relative_path: str) -> str:
    """
    **Get the full path to a path relative to the initialized project root or
    bundled executable.**

    *Parameters*:
    - `relative_path` (str): Path relative to the runtime base directory.

    *Returns*:
    - (str): The resolved absolute filesystem path as a string.
    """
    return resource_path(relative_path)