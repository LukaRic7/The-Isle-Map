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
    # Prefer PyInstaller bundle extraction dir when present
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        return Path(meipass)

    # Fall back to project root
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
    tried = []

    # 1) Inside the PyInstaller bundle extraction directory
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        p = (Path(meipass) / relative_path)
        tried.append(str(p))
        if p.exists():
            return str(p.resolve())

    # 2) If running as a frozen executable, check the exe directory
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent
        # Normal check: exe_dir / relative_path
        p = (exe_dir / relative_path)
        tried.append(str(p))
        if p.exists():
            return str(p.resolve())

        # If exe is placed inside a package folder (e.g., exe in .../client),
        # and relative_path begins with that package name, strip the leading
        # segment to avoid duplicated paths like client/client/...
        parts = Path(relative_path).parts
        if parts and parts[0].lower() == exe_dir.name.lower():
            stripped = Path(*parts[1:])
            p = exe_dir / stripped
            tried.append(str(p))
            if p.exists():
                return str(p.resolve())

        # Also allow the resource to live next to the exe using only its basename
        p = exe_dir / Path(relative_path).name
        tried.append(str(p))
        if p.exists():
            return str(p.resolve())

    # 3) Check current working directory
    cwd = Path.cwd()
    p = cwd / relative_path
    tried.append(str(p))
    if p.exists():
        return str(p.resolve())
    p = cwd / Path(relative_path).name
    tried.append(str(p))
    if p.exists():
        return str(p.resolve())

    # 4) Finally, check the configured project root
    base = __get_base_path()
    p = base / relative_path
    tried.append(str(p))
    if p.exists():
        return str(p.resolve())
    p = base / Path(relative_path).name
    tried.append(str(p))
    if p.exists():
        return str(p.resolve())

    # If nothing found, raise a helpful error listing attempted locations
    raise FileNotFoundError(
        f"Resource not found: '{relative_path}'. Tried the following locations:\n"
        + "\n".join(tried)
    )

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