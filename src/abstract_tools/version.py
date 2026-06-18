"""Single source of truth for the app version.

The default is a dev sentinel. CI writes ``_build_version.py`` (git-ignored)
with the real tag version *before* PyInstaller runs, so the shipped .exe
reports its release version; running from source reports ``dev``.
"""

try:
    from abstract_tools._build_version import BUILD_VERSION as __version__
except Exception:  # pragma: no cover - exercised only when the file is absent
    __version__ = "0.0.0+dev"

DEV_SENTINEL = "0.0.0+dev"


def is_dev_build(text: str = __version__) -> bool:
    return "+dev" in text or text == DEV_SENTINEL


def _version_tuple(text: str) -> tuple[int, ...]:
    core = text.strip().lstrip("vV").split("+")[0].split("-")[0]
    parts: list[int] = []
    for piece in core.split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    return tuple(parts) or (0,)


def is_newer(latest: str, current: str) -> bool:
    lt = _version_tuple(latest)
    ct = _version_tuple(current)
    width = max(len(lt), len(ct))
    lt = lt + (0,) * (width - len(lt))
    ct = ct + (0,) * (width - len(ct))
    return lt > ct


def display_version(text: str = __version__) -> str:
    if is_dev_build(text):
        return "dev"
    return "v" + text.strip().lstrip("vV")
