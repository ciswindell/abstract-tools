"""Check GitHub's public 'latest release' API and locate the .exe asset.

Pure and injectable: the HTTP layer is a parameter so tests never hit the
network. Never raises — any failure yields ``None`` (offline-friendly).
"""

import json
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from abstract_tools import version as _v

REPO = "ciswindell/abstract-tools"
_TIMEOUT_SECONDS = 8


@dataclass(frozen=True)
class UpdateInfo:
    latest_version: str
    download_url: str
    release_notes: str


def _default_get(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "abstract-tools",
        },
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
        return resp.read().decode("utf-8")


def check_for_update(
    current: str | None = None,
    *,
    repo: str = REPO,
    http_get: Callable[[str], str] = _default_get,
) -> UpdateInfo | None:
    current = _v.__version__ if current is None else current
    if _v.is_dev_build(current):
        return None
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        data = json.loads(http_get(url))
        tag = str(data["tag_name"])
        exe = next(
            (a for a in data.get("assets", [])
             if str(a.get("name", "")).lower().endswith(".exe")),
            None,
        )
        if exe is None or not _v.is_newer(tag, current):
            return None
        return UpdateInfo(
            latest_version=tag.lstrip("vV"),
            download_url=str(exe["browser_download_url"]),
            release_notes=str(data.get("body", "") or ""),
        )
    except Exception:
        return None


def _default_get_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "abstract-tools"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
        return resp.read()


def downloads_dir() -> Path:
    candidate = Path.home() / "Downloads"
    return candidate if candidate.is_dir() else Path.home()


def download_release(
    url: str,
    dest_dir: Path,
    filename: str,
    *,
    get_bytes: Callable[[str], bytes] = _default_get_bytes,
) -> Path:
    dest = Path(dest_dir) / filename
    tmp = dest.with_name(dest.name + ".part")
    try:
        tmp.write_bytes(get_bytes(url))
        tmp.replace(dest)
        return dest
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
