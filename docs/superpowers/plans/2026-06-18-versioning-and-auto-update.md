# Versioning & In-App Update Nudge — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Abstract Tools a visible version, publish each release as a downloadable Windows `.exe` from GitHub Actions, and show a dismissible in-app banner when a newer version exists.

**Architecture:** Four small units. A pure **version module** holds the version string (stamped by CI) and semver comparison. A pure **update_check module** queries GitHub's public "latest release" API and downloads the release asset — both injectable for tests, never raising. The **GUI layer** shows a version badge and a dismissible update banner driven by a background worker. The **CI workflow** stamps the version from the git tag and publishes a public GitHub Release.

**Tech Stack:** Python 3.12, PySide6 6.7 (Qt), pytest 8 + pytest-qt, Python stdlib `urllib`/`json` (no new runtime dependency), GitHub Actions, PyInstaller.

## Global Constraints

- Python `>=3.12`; PySide6 `6.7.*`; pytest with `pytest-qt`. (verbatim from `requirements.txt`)
- **No new runtime dependency.** Networking uses stdlib `urllib`/`json` only. (spec: "no new dependency", "no tokens")
- All GUI tests run headless: `QT_QPA_PLATFORM=offscreen python -m pytest`. (CLAUDE.md)
- Network is **never** touched in tests — the HTTP layer is always injected/stubbed. (spec: Testing strategy)
- Update checker and downloader **never raise**; on any error they return `None` / clean up. (spec: Error handling)
- Repo constant: `REPO = "ciswindell/abstract-tools"`, defined in ONE place. (spec: decided owner)
- Dev sentinel version: `"0.0.0+dev"`. A dev build skips the update check and shows `dev`. (spec: Unit A)
- Downloaded file name: `Abstract Tools {version}.exe`. (spec: Unit C)
- Commits use conventional format (`feat:`, `fix:`, `chore:`, `docs:`, `ci:`). (CLAUDE.md)

---

## File Structure

**Create:**
- `src/abstract_tools/version.py` — version string + semver parse/compare (Unit A)
- `src/abstract_tools/update_check.py` — GitHub API check + asset download, both injectable (Unit B)
- `src/abstract_tools/ui/update_banner.py` — the dismissible banner widget (Unit C)
- `tests/test_version.py`, `tests/test_update_check.py`, `tests/test_update_download.py`, `tests/test_ui_version_badge.py`, `tests/test_ui_update_banner.py`

**Modify:**
- `src/abstract_tools/ui/home_board.py` — add version badge to the top row
- `src/abstract_tools/ui/main_window.py` — window title + banner + background check wiring
- `src/abstract_tools/ui/theme.py` — styles for `versionBadge` and `updateBanner`
- `.github/workflows/build-windows.yml` — stamp version, publish Release
- `abstract_tools.spec` — bundle the generated `_build_version` module
- `.gitignore` — ignore the generated `_build_version.py`

**Generated only in CI (never committed):**
- `src/abstract_tools/_build_version.py` — `BUILD_VERSION = "X.Y.Z"`, written from the tag before PyInstaller runs.

---

## Task 1: Version module (Unit A)

**Files:**
- Create: `src/abstract_tools/version.py`
- Test: `tests/test_version.py`

**Interfaces:**
- Produces:
  - `__version__: str` — current version; defaults to `"0.0.0+dev"`, overridden by an optional generated `_build_version.BUILD_VERSION`.
  - `is_dev_build(text: str = __version__) -> bool`
  - `is_newer(latest: str, current: str) -> bool` — semver-aware, tolerant of a leading `v` and of pre-release/build suffixes.
  - `display_version(text: str = __version__) -> str` — returns `"dev"` for dev builds, else `f"v{clean}"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_version.py
from abstract_tools import version as v


def test_is_newer_handles_numeric_ordering():
    assert v.is_newer("1.10.0", "1.9.0") is True   # the classic string-sort trap
    assert v.is_newer("2.0.0", "1.9.9") is True
    assert v.is_newer("1.2.3", "1.2.3") is False
    assert v.is_newer("1.2.2", "1.2.3") is False


def test_is_newer_tolerates_leading_v_and_suffixes():
    assert v.is_newer("v1.4.0", "1.3.0") is True
    assert v.is_newer("1.4.0", "v1.4.0") is False
    assert v.is_newer("1.4.0+build7", "1.4.0") is False


def test_dev_build_detection_and_display():
    assert v.is_dev_build("0.0.0+dev") is True
    assert v.is_dev_build("1.2.3") is False
    assert v.display_version("0.0.0+dev") == "dev"
    assert v.display_version("1.2.3") == "v1.2.3"
    assert v.display_version("v1.2.3") == "v1.2.3"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_version.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'abstract_tools.version'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/abstract_tools/version.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_version.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/abstract_tools/version.py tests/test_version.py
git commit -m "feat: add version module with semver comparison"
```

---

## Task 2: Update checker (Unit B — check)

**Files:**
- Create: `src/abstract_tools/update_check.py`
- Test: `tests/test_update_check.py`

**Interfaces:**
- Consumes: `abstract_tools.version` (`__version__`, `is_dev_build`, `is_newer`).
- Produces:
  - `REPO: str = "ciswindell/abstract-tools"`
  - `@dataclass(frozen=True) UpdateInfo(latest_version: str, download_url: str, release_notes: str)`
  - `check_for_update(current: str | None = None, *, repo: str = REPO, http_get: Callable[[str], str] = _default_get) -> UpdateInfo | None`
  - `_default_get(url: str) -> str` (real urllib fetch; not used in tests)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_update_check.py
import json

from abstract_tools import update_check as uc


def _release_json(tag="1.3.0", asset_name="Abstract Tools.exe"):
    return json.dumps(
        {
            "tag_name": tag,
            "body": "Fixed the thing.",
            "assets": [
                {"name": asset_name,
                 "browser_download_url": f"https://example.test/{asset_name}"}
            ],
        }
    )


def test_returns_updateinfo_when_remote_is_newer():
    info = uc.check_for_update("1.2.0", http_get=lambda url: _release_json("1.3.0"))
    assert info is not None
    assert info.latest_version == "1.3.0"
    assert info.download_url == "https://example.test/Abstract Tools.exe"
    assert info.release_notes == "Fixed the thing."


def test_returns_none_when_up_to_date():
    assert uc.check_for_update("1.3.0", http_get=lambda url: _release_json("1.3.0")) is None


def test_returns_none_when_no_exe_asset():
    body = _release_json("9.9.9", asset_name="notes.txt")
    assert uc.check_for_update("1.0.0", http_get=lambda url: body) is None


def test_dev_build_skips_check():
    called = False

    def spy(url):
        nonlocal called
        called = True
        return _release_json("9.9.9")

    assert uc.check_for_update("0.0.0+dev", http_get=spy) is None
    assert called is False


def test_network_or_parse_errors_return_none():
    def boom(url):
        raise OSError("offline")

    assert uc.check_for_update("1.0.0", http_get=boom) is None
    assert uc.check_for_update("1.0.0", http_get=lambda url: "not json") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_update_check.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'abstract_tools.update_check'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/abstract_tools/update_check.py
"""Check GitHub's public 'latest release' API and locate the .exe asset.

Pure and injectable: the HTTP layer is a parameter so tests never hit the
network. Never raises — any failure yields ``None`` (offline-friendly).
"""

import json
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

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
    current = current or _v.__version__
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_update_check.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/abstract_tools/update_check.py tests/test_update_check.py
git commit -m "feat: add GitHub release update checker"
```

---

## Task 3: Release download helper (Unit B — download)

**Files:**
- Modify: `src/abstract_tools/update_check.py`
- Test: `tests/test_update_download.py`

**Interfaces:**
- Produces:
  - `download_release(url: str, dest_dir: Path, filename: str, *, get_bytes: Callable[[str], bytes] = _default_get_bytes) -> Path` — writes to a `.part` temp file then atomically renames; returns the final path. Cleans up the temp file and re-raises on failure.
  - `downloads_dir() -> Path` — the user's Downloads folder, falling back to home.
  - `_default_get_bytes(url: str) -> bytes`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_update_download.py
import pytest

from abstract_tools import update_check as uc


def test_download_writes_file_atomically(tmp_path):
    dest = uc.download_release(
        "https://example.test/app.exe",
        tmp_path,
        "Abstract Tools 1.3.0.exe",
        get_bytes=lambda url: b"PE\x00\x00fake-exe",
    )
    assert dest == tmp_path / "Abstract Tools 1.3.0.exe"
    assert dest.read_bytes() == b"PE\x00\x00fake-exe"
    # no leftover temp file
    assert list(tmp_path.glob("*.part")) == []


def test_download_cleans_up_and_raises_on_failure(tmp_path):
    def boom(url):
        raise OSError("connection reset")

    with pytest.raises(OSError):
        uc.download_release("https://example.test/app.exe", tmp_path,
                            "Abstract Tools 1.3.0.exe", get_bytes=boom)
    assert list(tmp_path.iterdir()) == []  # nothing left behind


def test_downloads_dir_is_a_path():
    from pathlib import Path
    assert isinstance(uc.downloads_dir(), Path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_update_download.py -v`
Expected: FAIL — `AttributeError: module 'abstract_tools.update_check' has no attribute 'download_release'`

- [ ] **Step 3: Write minimal implementation (append to `update_check.py`)**

```python
# add to imports at top of src/abstract_tools/update_check.py
from pathlib import Path


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_update_download.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/abstract_tools/update_check.py tests/test_update_download.py
git commit -m "feat: add release asset download helper"
```

---

## Task 4: Version badge in the GUI (Unit C — label)

**Files:**
- Modify: `src/abstract_tools/ui/home_board.py` (top row, after the brand stretch)
- Modify: `src/abstract_tools/ui/main_window.py` (window title)
- Modify: `src/abstract_tools/ui/theme.py` (add `versionBadge` style)
- Test: `tests/test_ui_version_badge.py`

**Interfaces:**
- Consumes: `abstract_tools.version.display_version`, `abstract_tools.version.__version__`.
- Produces: `HomeBoard.version_label` (a `QLabel` with objectName `versionBadge`); window title `f"Abstract Tools {display_version()}"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ui_version_badge.py
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from abstract_tools import tools as tools_module
from abstract_tools import version as v
from abstract_tools.ui.home_board import HomeBoard
from abstract_tools.ui.main_window import MainWindow


def test_home_board_shows_version_badge(qtbot):
    board = HomeBoard(tools_module.TOOLS, on_launch=lambda _id: None)
    qtbot.addWidget(board)
    assert board.version_label.objectName() == "versionBadge"
    assert board.version_label.text() == v.display_version()


def test_window_title_includes_version(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert v.display_version() in window.windowTitle()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_ui_version_badge.py -v`
Expected: FAIL — `AttributeError: 'HomeBoard' object has no attribute 'version_label'`

- [ ] **Step 3: Write minimal implementation**

In `src/abstract_tools/ui/home_board.py`, add the import at the top:

```python
from abstract_tools import version as app_version
```

Then in `HomeBoard.__init__`, replace the top-row block:

```python
        top = QtWidgets.QWidget()
        top.setObjectName("boardTop")
        top_row = QtWidgets.QHBoxLayout(top)
        top_row.setContentsMargins(28, 14, 28, 14)
        brand = QtWidgets.QLabel("Abstract Tools")
        brand.setObjectName("boardBrand")
        top_row.addWidget(brand)
        top_row.addStretch()
        outer.addWidget(top)
```

with:

```python
        top = QtWidgets.QWidget()
        top.setObjectName("boardTop")
        top_row = QtWidgets.QHBoxLayout(top)
        top_row.setContentsMargins(28, 14, 28, 14)
        brand = QtWidgets.QLabel("Abstract Tools")
        brand.setObjectName("boardBrand")
        top_row.addWidget(brand)
        top_row.addStretch()
        self.version_label = QtWidgets.QLabel(app_version.display_version())
        self.version_label.setObjectName("versionBadge")
        top_row.addWidget(self.version_label)
        outer.addWidget(top)
```

In `src/abstract_tools/ui/main_window.py`, add the import:

```python
from abstract_tools import version as app_version
```

and change the title line in `MainWindow.__init__`:

```python
        self.setWindowTitle(f"Abstract Tools {app_version.display_version()}")
```

In `src/abstract_tools/ui/theme.py`, add next to the other `board*` rules (after the `QLabel#boardBrand` line):

```python
QLabel#versionBadge {{ font-family: "{MONO}"; font-size: 11px; color: {INK_SOFT}; }}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_ui_version_badge.py tests/test_ui_home_board.py tests/test_ui_main_window.py -v`
Expected: PASS (existing board/window tests still green)

- [ ] **Step 5: Commit**

```bash
git add src/abstract_tools/ui/home_board.py src/abstract_tools/ui/main_window.py src/abstract_tools/ui/theme.py tests/test_ui_version_badge.py
git commit -m "feat: show version badge in home board and window title"
```

---

## Task 5: Update banner widget (Unit C — banner)

**Files:**
- Create: `src/abstract_tools/ui/update_banner.py`
- Modify: `src/abstract_tools/ui/theme.py` (add `updateBanner` styles)
- Test: `tests/test_ui_update_banner.py`

**Interfaces:**
- Consumes: `abstract_tools.update_check.UpdateInfo`.
- Produces: `UpdateBanner(QtWidgets.QFrame)` with:
  - signals `download_requested = QtCore.Signal(object)` (emits the `UpdateInfo`) and `dismissed = QtCore.Signal()`
  - `show_update(info: UpdateInfo) -> None` — sets text `f"Version {info.latest_version} is available"` and makes the banner visible, storing `self.info`
  - `set_status(text: str) -> None` — replaces the message text (used during/after download)
  - objectName `updateBanner`; the message label objectName `updateBannerText`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ui_update_banner.py
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from abstract_tools.ui.update_banner import UpdateBanner
from abstract_tools.update_check import UpdateInfo


def _info():
    return UpdateInfo("1.3.0", "https://example.test/app.exe", "notes")


def test_show_update_sets_text_and_visibility(qtbot):
    banner = UpdateBanner()
    qtbot.addWidget(banner)
    banner.show()
    banner.show_update(_info())
    assert banner.isVisibleTo(banner.parent()) or banner.isVisible()
    assert "1.3.0" in banner.text_label.text()
    assert banner.info == _info()


def test_download_button_emits_info(qtbot):
    banner = UpdateBanner()
    qtbot.addWidget(banner)
    banner.show_update(_info())
    with qtbot.waitSignal(banner.download_requested, timeout=1000) as blocker:
        banner.download_button.click()
    assert blocker.args[0] == _info()


def test_dismiss_hides_and_emits(qtbot):
    banner = UpdateBanner()
    qtbot.addWidget(banner)
    banner.show_update(_info())
    with qtbot.waitSignal(banner.dismissed, timeout=1000):
        banner.close_button.click()
    assert banner.isHidden()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_ui_update_banner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'abstract_tools.ui.update_banner'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/abstract_tools/ui/update_banner.py
from PySide6 import QtCore, QtWidgets

from abstract_tools.update_check import UpdateInfo


class UpdateBanner(QtWidgets.QFrame):
    """A dismissible 'new version available' bar shown above the main stack."""

    download_requested = QtCore.Signal(object)  # UpdateInfo
    dismissed = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("updateBanner")
        self.info: UpdateInfo | None = None

        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(28, 10, 16, 10)
        row.setSpacing(12)

        self.text_label = QtWidgets.QLabel("")
        self.text_label.setObjectName("updateBannerText")
        row.addWidget(self.text_label)
        row.addStretch()

        self.download_button = QtWidgets.QPushButton("Download update")
        self.download_button.setObjectName("primary")
        self.download_button.clicked.connect(self._on_download)
        row.addWidget(self.download_button)

        self.close_button = QtWidgets.QPushButton("✕")
        self.close_button.setObjectName("ghost")
        self.close_button.setFixedWidth(34)
        self.close_button.clicked.connect(self._on_close)
        row.addWidget(self.close_button)

        self.hide()

    def show_update(self, info: UpdateInfo) -> None:
        self.info = info
        self.text_label.setText(f"Version {info.latest_version} is available")
        self.download_button.setEnabled(True)
        self.show()

    def set_status(self, text: str) -> None:
        self.text_label.setText(text)

    def _on_download(self) -> None:
        if self.info is not None:
            self.download_requested.emit(self.info)

    def _on_close(self) -> None:
        self.hide()
        self.dismissed.emit()
```

In `src/abstract_tools/ui/theme.py`, add (near the `board*` rules):

```python
QFrame#updateBanner {{ background: #eaf3ec; border-bottom: 1px solid {LINE}; }}
QLabel#updateBannerText {{ color: {PINE_DEEP}; font-size: 13px; font-weight: 600; }}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_ui_update_banner.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/abstract_tools/ui/update_banner.py src/abstract_tools/ui/theme.py tests/test_ui_update_banner.py
git commit -m "feat: add dismissible update banner widget"
```

---

## Task 6: Wire the banner + background check + download into MainWindow (Unit C — integration)

**Files:**
- Modify: `src/abstract_tools/ui/main_window.py`
- Test: `tests/test_ui_main_window.py` (add cases)

**Interfaces:**
- Consumes: `UpdateBanner`, `update_check.check_for_update`, `update_check.download_release`, `update_check.downloads_dir`.
- Produces on `MainWindow`:
  - constructor gains `update_checker: Callable[[], UpdateInfo | None] | None = None` and `downloader: Callable[[UpdateInfo], Path] | None = None` (both default to the real implementations; injected in tests).
  - `self.banner: UpdateBanner` placed above `self.stack` in a vertical container.
  - `_on_update_found(info: UpdateInfo) -> None` — calls `banner.show_update`.
  - `_on_download_requested(info: UpdateInfo) -> None` — disables the button, sets "Downloading…", runs the downloader, then `_on_download_done` / `_on_download_failed`.
  - `start_update_check() -> None` — runs the checker on a background `QThread`; safe no-op result handling.

> Threading note: mirror the existing `ConversionWorker` pattern in
> `ui/tiff_converter/plan_screen.py` (a `QtCore.QObject` worker moved to a
> `QtCore.QThread`, signals back to the UI). Tests do **not** spin the thread —
> they call `_on_update_found` / `_on_download_requested` directly with injected
> fakes, so no real network or thread is exercised.

- [ ] **Step 1: Write the failing test (append to `tests/test_ui_main_window.py`)**

```python
from pathlib import Path

from abstract_tools.update_check import UpdateInfo


def test_banner_appears_when_update_found(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.banner.isHidden()
    window._on_update_found(UpdateInfo("1.3.0", "https://example.test/app.exe", "n"))
    assert not window.banner.isHidden()
    assert "1.3.0" in window.banner.text_label.text()


def test_download_request_uses_injected_downloader(tmp_path, qtbot):
    saved = tmp_path / "Abstract Tools 1.3.0.exe"
    saved.write_bytes(b"x")

    def fake_downloader(info):
        return saved

    window = MainWindow(downloader=fake_downloader)
    qtbot.addWidget(window)
    info = UpdateInfo("1.3.0", "https://example.test/app.exe", "n")
    window._on_update_found(info)
    window._on_download_requested(info)
    # message reflects success and points at the saved file's folder
    assert "Downloads" in window.banner.text_label.text() or str(saved) in window.banner.text_label.text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_ui_main_window.py -v`
Expected: FAIL — `AttributeError: 'MainWindow' object has no attribute 'banner'`

- [ ] **Step 3: Write minimal implementation**

Rewrite `src/abstract_tools/ui/main_window.py` to this:

```python
from collections.abc import Callable
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from abstract_tools import tools as tools_module
from abstract_tools import update_check
from abstract_tools import version as app_version
from abstract_tools.ui import theme
from abstract_tools.ui.home_board import HomeBoard
from abstract_tools.ui.update_banner import UpdateBanner
from abstract_tools.update_check import UpdateInfo


class _CheckWorker(QtCore.QObject):
    found = QtCore.Signal(object)  # UpdateInfo
    done = QtCore.Signal()

    def __init__(self, checker: Callable[[], UpdateInfo | None]):
        super().__init__()
        self._checker = checker

    @QtCore.Slot()
    def run(self) -> None:
        info = self._checker()
        if info is not None:
            self.found.emit(info)
        self.done.emit()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(
        self,
        update_checker: Callable[[], UpdateInfo | None] | None = None,
        downloader: Callable[[UpdateInfo], Path] | None = None,
    ):
        super().__init__()
        self.setWindowTitle(f"Abstract Tools {app_version.display_version()}")
        self.resize(1200, 820)

        self._update_checker = update_checker or update_check.check_for_update
        self._downloader = downloader or self._real_download

        self.stack = QtWidgets.QStackedWidget()
        self.banner = UpdateBanner()
        self.banner.download_requested.connect(self._on_download_requested)

        container = QtWidgets.QWidget()
        col = QtWidgets.QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self.banner)
        col.addWidget(self.stack, 1)
        self.setCentralWidget(container)

        self._tools = {t.id: t for t in tools_module.TOOLS}
        self.board = HomeBoard(tools_module.TOOLS, on_launch=self.launch_tool)
        self.stack.addWidget(self.board)
        self._current_tool = None

        self._check_thread: QtCore.QThread | None = None
        self._check_worker: _CheckWorker | None = None

    # --- update check -------------------------------------------------
    def start_update_check(self) -> None:
        thread = QtCore.QThread(self)
        worker = _CheckWorker(self._update_checker)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.found.connect(self._on_update_found)
        worker.done.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._check_thread = thread
        self._check_worker = worker
        thread.start()

    @QtCore.Slot(object)
    def _on_update_found(self, info: UpdateInfo) -> None:
        self.banner.show_update(info)

    def _on_download_requested(self, info: UpdateInfo) -> None:
        self.banner.download_button.setEnabled(False)
        self.banner.set_status(f"Downloading version {info.latest_version}…")
        QtWidgets.QApplication.processEvents()
        try:
            saved = self._downloader(info)
        except Exception:
            self._on_download_failed()
            return
        self._on_download_done(saved)

    def _on_download_done(self, saved: Path) -> None:
        self.banner.set_status(
            f"Saved to {saved.parent.name} — close this app and open the new file."
        )

    def _on_download_failed(self) -> None:
        self.banner.download_button.setEnabled(True)
        self.banner.set_status("Download failed — please try again or contact Chris.")

    def _real_download(self, info: UpdateInfo) -> Path:
        return update_check.download_release(
            info.download_url,
            update_check.downloads_dir(),
            f"Abstract Tools {info.latest_version}.exe",
        )

    # --- tool switching (unchanged behaviour) -------------------------
    def launch_tool(self, tool_id: str) -> None:
        tool = self._tools[tool_id]
        widget = tool.build(self.show_board)
        if self._current_tool is not None:
            self.stack.removeWidget(self._current_tool)
            if hasattr(self._current_tool, "shutdown"):
                self._current_tool.shutdown()
            self._current_tool.deleteLater()
        self._current_tool = widget
        self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)

    def show_board(self) -> None:
        self.stack.setCurrentWidget(self.board)
        if self._current_tool is not None:
            self.stack.removeWidget(self._current_tool)
            if hasattr(self._current_tool, "shutdown"):
                self._current_tool.shutdown()
            self._current_tool.deleteLater()
            self._current_tool = None


def main() -> None:
    import sys

    app = QtWidgets.QApplication(sys.argv)
    theme.apply_theme(app)
    window = MainWindow()
    window.show()
    window.start_update_check()
    sys.exit(app.exec())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_ui_main_window.py -v`
Expected: PASS (existing 1 + new 2)

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest -q`
Expected: PASS (all tests)

- [ ] **Step 6: Commit**

```bash
git add src/abstract_tools/ui/main_window.py tests/test_ui_main_window.py
git commit -m "feat: wire update banner, background check, and download into main window"
```

---

## Task 7: CI version stamping + public Release publishing (Unit D)

**Files:**
- Modify: `.github/workflows/build-windows.yml`
- Modify: `abstract_tools.spec` (bundle the generated version module)
- Modify: `.gitignore` (ignore the generated module)

**Interfaces:**
- Consumes: tag `github.ref_name` (e.g. `v1.3.0`).
- Produces: `src/abstract_tools/_build_version.py` at build time; a public GitHub Release with `Abstract Tools.exe` attached.

> This task has no unit test — its deliverable is verified by the rollout in
> Task 8 (a real tag build). Keep the edits minimal and exact.

- [ ] **Step 1: Ignore the generated module**

Add to `.gitignore` under the Python section:

```
# Generated at build time by CI from the release tag — never committed
src/abstract_tools/_build_version.py
```

- [ ] **Step 2: Bundle the generated module in the PyInstaller spec**

In `abstract_tools.spec`, add to the `hiddenimports` list (CI writes the file before the build runs, so it is present during analysis):

```python
        # Version stamped into _build_version.py by CI before the build;
        # imported lazily in version.py so list it explicitly.
        "abstract_tools._build_version",
```

- [ ] **Step 3: Update the workflow**

Replace `.github/workflows/build-windows.yml` with:

```yaml
name: Build Windows EXE

on:
  push:
    tags: ["v*"]
  workflow_dispatch:

permissions:
  contents: write

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt "pyinstaller==6.*"
      - name: Run tests
        env:
          QT_QPA_PLATFORM: offscreen
        run: python -m pytest -q
      - name: Stamp version from tag
        if: startsWith(github.ref, 'refs/tags/v')
        shell: bash
        run: |
          VERSION="${GITHUB_REF_NAME#v}"
          echo "BUILD_VERSION = \"${VERSION}\"" > src/abstract_tools/_build_version.py
          echo "Stamped version ${VERSION}"
      - name: Build executable
        run: pyinstaller --noconfirm abstract_tools.spec
      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: abstract-tools
          path: "dist/Abstract Tools.exe"
      - name: Publish Release
        if: startsWith(github.ref, 'refs/tags/v')
        uses: softprops/action-gh-release@v2
        with:
          files: "dist/Abstract Tools.exe"
          generate_release_notes: true
```

- [ ] **Step 4: Validate the workflow YAML locally**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/build-windows.yml'))" && echo OK`
Expected: `OK` (install `pyyaml` in the venv first if missing: `pip install pyyaml`)

- [ ] **Step 5: Confirm tests still pass and the spec imports cleanly**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest -q`
Expected: PASS (the stamped module is absent locally → app reports `dev`, which is correct)

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/build-windows.yml abstract_tools.spec .gitignore
git commit -m "ci: stamp version from tag and publish public release"
```

---

## Task 8: Rollout via GitHub CLI (operational — run after Tasks 1–7 merge to `dev`/`master`)

**Files:** none (operational). Uses the authenticated `gh` CLI (logged in as `ciswindell`).

> No automated test. This is the one-time go-live: create the public repo, push,
> cut the first tag, and verify the Release actually contains a downloadable `.exe`
> and that an older local build sees the banner. Stop and report if any check fails.

- [ ] **Step 1: Create the public repo and push**

```bash
gh repo create ciswindell/abstract-tools --public --source=. --remote=origin --push
```
Expected: repo created; current branch pushed. Verify: `gh repo view ciswindell/abstract-tools --web` (or `gh repo view`).

- [ ] **Step 2: Push the main branch the workflow/release should track**

```bash
git push origin master   # ensure the release branch exists on the remote
```
Expected: `master` present on origin. (Confirm `.gitignore` kept `example/` out: `git ls-files example | wc -l` → `0`.)

- [ ] **Step 3: Cut the first release tag**

```bash
git tag v1.0.0
git push origin v1.0.0
```
Expected: tag push triggers the **Build Windows EXE** workflow.

- [ ] **Step 4: Watch the build**

```bash
gh run watch
```
Expected: tests pass → version stamped `1.0.0` → PyInstaller builds → Release published.

- [ ] **Step 5: Verify the Release has the .exe**

```bash
gh release view v1.0.0
```
Expected: a `1.0.0` release listing `Abstract Tools.exe` as an asset.

- [ ] **Step 6: Verify the public API the app reads**

```bash
gh api repos/ciswindell/abstract-tools/releases/latest --jq '.tag_name, (.assets[].name)'
```
Expected: `v1.0.0` and `Abstract Tools.exe`.

- [ ] **Step 7: Verify the update banner end-to-end (local sanity)**

```bash
QT_QPA_PLATFORM=offscreen python -c "
from abstract_tools.update_check import check_for_update
print(check_for_update('0.9.0'))   # pretend we're behind
"
```
Expected: an `UpdateInfo(latest_version='1.0.0', download_url=…Abstract Tools.exe, …)` — proving a real, older build would show the banner. (`check_for_update()` with the real dev version returns `None`, which is also correct.)

- [ ] **Step 8: Report** the release URL and the verification results to Chris.

---

## Self-Review

**1. Spec coverage**

| Spec item | Task |
|---|---|
| Version source of truth = git tag | Task 1 (module) + Task 7 (CI stamp) |
| Visible version in GUI | Task 4 |
| Public Releases host the `.exe` | Task 7 + Task 8 |
| Background, non-blocking update check | Task 6 (`_CheckWorker` on a `QThread`) |
| Dismissible banner | Task 5 + Task 6 |
| Download-for-them to Downloads folder | Task 3 + Task 6 |
| Degrades gracefully offline | Task 2 (returns `None`), Task 6 (`_on_download_failed`) |
| Dev build shows `dev`, skips check | Task 1 (`is_dev_build`/`display_version`) + Task 2 |
| No new runtime dependency | Tasks 2–3 use stdlib `urllib`/`json` |
| No tokens / public API | Task 2 (`api.github.com/.../releases/latest`) |
| Packaging updated for new bundled file | Task 7 (`hiddenimports`) |
| Tests never hit network | Tasks 2, 3, 6 (injected fakes) |
| Repo constant in one place | Task 2 (`REPO`) |

No gaps found.

**2. Placeholder scan:** No "TBD"/"TODO"/"handle edge cases" placeholders; every code step shows complete code.

**3. Type consistency:** `UpdateInfo(latest_version, download_url, release_notes)` is defined in Task 2 and used identically in Tasks 5–6 and tests. `check_for_update`, `download_release`, `downloads_dir`, `display_version`, `is_dev_build`, `is_newer` signatures match across producer/consumer tasks. Banner members (`text_label`, `download_button`, `close_button`, `info`, `show_update`, `set_status`) are consistent between Task 5 and Task 6.
