import sys
from pathlib import Path


def resource_path(name: str) -> Path:
    """Absolute path to a bundled resource.

    Works from source (src/aa_tool/resources/<name>) and from a PyInstaller
    one-file bundle, where data files are unpacked under sys._MEIPASS.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base is not None:
        return Path(base) / "aa_tool" / "resources" / name
    return Path(__file__).resolve().parent / "resources" / name
