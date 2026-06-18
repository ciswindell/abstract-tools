# Batch TIFF to PDF Converter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Batch TIFF to PDF Converter" tool to the Abstract Tools desktop app that converts a folder tree of TIFFs to PDFs (mirroring structure, copying non-TIFFs), shown under the NM State Land Office group.

**Architecture:** A pure, Qt-free conversion engine (`tiff_convert.py`) adapted from the existing standalone CLI script, driven by a thread pool. A new tool package (`src/aa_tool/ui/tiff_converter/`) provides an open screen and a plan/result screen, with conversion run off the UI thread via a QThread worker that reports progress into the shared header's progress pill. The tool is registered in `tools.py` and grouped under "NM State Land Office".

**Tech Stack:** Python 3.12, PySide6 (Qt), Pillow + pypdf (TIFF decode / PDF assembly), pytest + pytest-qt.

## Global Constraints

- Python `>=3.12` (from `pyproject.toml`).
- GUI uses PySide6 `6.7.*` (`from PySide6 import QtCore, QtGui, QtWidgets, QtSvg`).
- No multiprocessing — use `concurrent.futures.ThreadPoolExecutor` only (packaged-Windows-`.exe` safety).
- No log files written by the converter — results are surfaced in the UI only.
- Output destination defaults to a sibling folder named exactly `"<source.name> converted"`.
- TIFF detection is case-insensitive on extensions `.tif` and `.tiff`.
- Tests must run headless: every UI test module begins with
  `import os` then `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` BEFORE importing any `aa_tool.ui` module.
- Run tests with the project venv: `./venv/bin/python -m pytest`.
- Tool display name: exactly `"Batch TIFF to PDF Converter"`. Category: exactly `"NM State Land Office"`.
- Qt widget styling is driven by `objectName`; reuse existing names: `screen`, `h1`, `sub`, `primary`, `ghost`, `savePath`, `success`, `warn`.

---

## File Structure

- **Create** `src/aa_tool/tiff_convert.py` — pure conversion engine (no Qt).
- **Create** `src/aa_tool/ui/tiff_converter/__init__.py` — empty package marker.
- **Create** `src/aa_tool/ui/tiff_converter/tool.py` — `TiffConverterTool` widget + open screen.
- **Create** `src/aa_tool/ui/tiff_converter/plan_screen.py` — plan/convert/result screen + `ConversionWorker`.
- **Create** `src/aa_tool/resources/icons/tiff_converter.svg` — tool icon.
- **Modify** `src/aa_tool/ui/header.py` — add optional `steps` parameter.
- **Modify** `src/aa_tool/tools.py` — register `TIFF_CONVERTER_TOOL`.
- **Modify** `requirements.txt` — add `Pillow` and `pypdf`.
- **Create** `tests/test_tiff_convert.py` — engine tests.
- **Create** `tests/test_tiff_converter_tool.py` — UI tests.
- **Modify** `tests/test_ui_header.py` — add a test for the `steps` parameter.

---

### Task 1: Add Pillow + pypdf dependencies

**Files:**
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: nothing.
- Produces: `PIL` (Pillow) and `pypdf` importable in the project venv — every later task relies on these.

- [ ] **Step 1: Add the two dependencies to requirements.txt**

The file currently reads:

```
PySide6==6.7.*
pymupdf==1.24.*
openpyxl==3.1.*
pytest==8.*
pytest-qt==4.*
```

Change it to:

```
PySide6==6.7.*
pymupdf==1.24.*
openpyxl==3.1.*
Pillow==10.*
pypdf==4.*
pytest==8.*
pytest-qt==4.*
```

- [ ] **Step 2: Install into the project venv**

Run:
```bash
./venv/bin/pip install "Pillow==10.*" "pypdf==4.*"
```
Expected: ends with `Successfully installed Pillow-10.x.x pypdf-4.x.x` (or "already satisfied").

- [ ] **Step 3: Verify both import**

Run:
```bash
./venv/bin/python -c "import PIL, pypdf; print('both present')"
```
Expected: prints `both present`.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "build: add Pillow and pypdf for TIFF conversion"
```

---

### Task 2: Conversion engine (`tiff_convert.py`)

**Files:**
- Create: `src/aa_tool/tiff_convert.py`
- Test: `tests/test_tiff_convert.py`

**Interfaces:**
- Consumes: `PIL.Image`, `pypdf` (Task 1).
- Produces (later tasks rely on these exact names/signatures):
  - `default_output(source: Path) -> Path`
  - `plan_actions(source_root: Path, output_root: Path, force: bool) -> list[Action]`
  - `summarize_plan(actions: list[Action]) -> PlanSummary` where
    `PlanSummary` is a frozen dataclass with int fields `tiff_count`, `copy_count`, `dir_count`, `total_bytes`.
  - `run_conversion(source_root: Path, output_root: Path, *, standardize: bool = True, force: bool = False, workers: int | None = None, progress_cb: Callable[[int, int, str], None] | None = None) -> RunSummary`
    where `RunSummary` is a frozen dataclass with int fields `converted`, `copied`, `dirs_created` and `failures: list[tuple[Path, str]]` (source path, error message).
  - `should_skip(src: Path, dst: Path) -> bool`
  - `count_tiff_pages(path: Path) -> int`, `count_pdf_pages(path: Path) -> int`
  - `Action` (frozen dataclass: `kind: str`, `src: Path`, `dst: Path`)
  - `ConversionError` (Exception)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tiff_convert.py`:

```python
from pathlib import Path

from PIL import Image

from aa_tool.tiff_convert import (
    Action,
    PlanSummary,
    RunSummary,
    count_pdf_pages,
    count_tiff_pages,
    default_output,
    plan_actions,
    run_conversion,
    should_skip,
    summarize_plan,
)


def _make_tiff(path: Path, pages: int = 1, size=(120, 160)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = [Image.new("RGB", size, "white") for _ in range(pages)]
    frames[0].save(path, save_all=True, append_images=frames[1:])
    return path


def test_default_output_is_sibling_named_converted(tmp_path):
    src = tmp_path / "lease scans"
    assert default_output(src) == tmp_path / "lease scans converted"


def test_plan_actions_classifies_tree(tmp_path):
    src = tmp_path / "src"
    _make_tiff(src / "a.tif")
    _make_tiff(src / "sub" / "b.TIFF")
    (src / "sub").mkdir(parents=True, exist_ok=True)
    (src / "notes.txt").write_text("hi")

    out = default_output(src)
    actions = plan_actions(src, out, force=False)
    kinds = sorted(a.kind for a in actions)
    convert = [a for a in actions if a.kind == "Convert"]
    copy = [a for a in actions if a.kind == "Copy"]

    assert len(convert) == 2
    assert all(a.dst.suffix == ".pdf" for a in convert)
    assert len(copy) == 1 and copy[0].dst.name == "notes.txt"
    assert "MakeDir" in kinds


def test_summarize_plan_counts(tmp_path):
    src = tmp_path / "src"
    _make_tiff(src / "a.tif")
    (src / "notes.txt").write_text("hi")
    actions = plan_actions(src, default_output(src), force=False)

    summary = summarize_plan(actions)
    assert isinstance(summary, PlanSummary)
    assert summary.tiff_count == 1
    assert summary.copy_count == 1
    assert summary.total_bytes > 0


def test_run_conversion_round_trips_pages(tmp_path):
    src = tmp_path / "src"
    _make_tiff(src / "two.tif", pages=2)
    (src / "keep.txt").write_text("hi")
    out = default_output(src)

    result = run_conversion(src, out, standardize=True)
    assert isinstance(result, RunSummary)
    assert result.converted == 1
    assert result.copied == 1
    assert not result.failures

    pdf = out / "two.pdf"
    assert pdf.exists()
    assert count_pdf_pages(pdf) == count_tiff_pages(src / "two.tif") == 2
    assert (out / "keep.txt").exists()


def test_run_conversion_no_standardize(tmp_path):
    src = tmp_path / "src"
    _make_tiff(src / "a.tif", pages=1)
    out = default_output(src)
    result = run_conversion(src, out, standardize=False)
    assert result.converted == 1
    assert count_pdf_pages(out / "a.pdf") == 1


def test_should_skip_only_when_pages_match(tmp_path):
    src = tmp_path / "src"
    _make_tiff(src / "a.tif", pages=2)
    out = default_output(src)
    run_conversion(src, out, standardize=True)

    assert should_skip(src / "a.tif", out / "a.pdf") is True
    assert should_skip(src / "a.tif", out / "missing.pdf") is False


def test_progress_callback_reports_total(tmp_path):
    src = tmp_path / "src"
    _make_tiff(src / "a.tif")
    _make_tiff(src / "b.tif")
    out = default_output(src)

    seen = []
    run_conversion(src, out, progress_cb=lambda done, total, label: seen.append((done, total)))
    assert seen, "progress_cb was never called"
    assert seen[-1] == (2, 2)


def test_run_conversion_records_failure(tmp_path):
    src = tmp_path / "src"
    bad = src / "bad.tif"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"not a real tiff")
    out = default_output(src)

    result = run_conversion(src, out)
    assert result.converted == 0
    assert len(result.failures) == 1
    assert result.failures[0][0] == bad
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_tiff_convert.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aa_tool.tiff_convert'`.

- [ ] **Step 3: Write the engine**

Create `src/aa_tool/tiff_convert.py`. The functions marked "(verbatim from CLI)" are copied unchanged from
`ciswindell-tools/tiff-batch-to-pdf/1.1.0/skills/tiff-batch-to-pdf/tiff_batch_to_pdf.py`:

```python
"""Convert a folder tree of TIFF files to PDFs while preserving subfolder structure.

Pure engine (no Qt). Adapted from the standalone tiff-batch-to-pdf CLI: the
multiprocessing pool, tqdm progress bar, log-file writing, and argparse front
end are replaced with a thread-pool runner that reports progress via a callback
and returns an in-memory summary. No files other than the converted PDFs and
copied originals are written.
"""

from __future__ import annotations

import functools
import io
import logging
import shutil
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

# pypdf logs WARNING for every malformed/partial PDF it reads; the skip-check
# routinely encounters partials and handles them. Silence below ERROR.
logging.getLogger("pypdf").setLevel(logging.ERROR)


class ConversionError(Exception):
    """Raised when a conversion or verification step fails."""


# Standard page sizes in inches, portrait orientation as (width, height).
LETTER_INCHES = (8.5, 11.0)
LEGAL_INCHES = (8.5, 14.0)
_LETTER_RATIO = LETTER_INCHES[1] / LETTER_INCHES[0]
_LEGAL_RATIO = LEGAL_INCHES[1] / LEGAL_INCHES[0]
_RATIO_CUTOFF = (_LETTER_RATIO + _LEGAL_RATIO) / 2

TIFF_EXTENSIONS = {".tif", ".tiff"}


def _standardize_page(frame):  # (verbatim from CLI)
    from PIL import Image

    rgb = frame.convert("RGB")
    w_px, h_px = rgb.size
    landscape = w_px > h_px
    long_side = max(w_px, h_px)
    short_side = min(w_px, h_px)
    ratio = long_side / short_side if short_side else _LETTER_RATIO

    w_in, h_in = LEGAL_INCHES if ratio >= _RATIO_CUTOFF else LETTER_INCHES
    if landscape:
        w_in, h_in = h_in, w_in

    dpi = max(w_px / w_in, h_px / h_in)
    canvas_w = round(w_in * dpi)
    canvas_h = round(h_in * dpi)

    canvas = Image.new("RGB", (canvas_w, canvas_h), "white")
    canvas.paste(rgb, ((canvas_w - w_px) // 2, (canvas_h - h_px) // 2))
    return canvas, dpi


def count_tiff_pages(path: Path) -> int:  # (verbatim from CLI)
    from PIL import Image

    try:
        with Image.open(path) as img:
            return getattr(img, "n_frames", 1)
    except Exception as exc:  # noqa: BLE001
        raise ConversionError(f"Pillow could not read {path}: {exc}") from exc


def count_pdf_pages(path: Path) -> int:  # (verbatim from CLI)
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    if not path.exists():
        raise ConversionError(f"PDF does not exist: {path}")
    try:
        return len(PdfReader(str(path)).pages)
    except (PdfReadError, OSError, ValueError) as exc:
        raise ConversionError(f"pypdf failed to read {path}: {exc}") from exc


def should_skip(src: Path, dst: Path) -> bool:  # (verbatim from CLI)
    if not dst.exists():
        return False
    try:
        return count_pdf_pages(dst) == count_tiff_pages(src)
    except ConversionError:
        return False


def _convert_pillow(src: Path, dst: Path, standardize: bool = True) -> None:  # (verbatim from CLI)
    from PIL import Image, JpegImagePlugin  # noqa: F401 — JPEG SAVE handler
    from pypdf import PdfWriter

    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        img = Image.open(src)
        n_frames = getattr(img, "n_frames", 1)

        if not standardize:
            pages = []
            for i in range(n_frames):
                img.seek(i)
                pages.append(img.convert("RGB"))
            pages[0].save(dst, "PDF", save_all=True, append_images=pages[1:])
            return

        writer = PdfWriter()
        for i in range(n_frames):
            img.seek(i)
            canvas, dpi = _standardize_page(img.convert("RGB"))
            buf = io.BytesIO()
            canvas.save(buf, "PDF", resolution=dpi)
            buf.seek(0)
            writer.append(buf)
        with open(dst, "wb") as f:
            writer.write(f)
    except Exception as exc:  # noqa: BLE001
        raise ConversionError(f"Pillow convert failed for {src}: {exc}") from exc


def convert_one(src: Path, dst: Path, standardize: bool = True) -> None:  # (adapted from CLI)
    """Convert one TIFF to PDF and verify the output page count matches the source."""
    src_pages = count_tiff_pages(src)
    _convert_pillow(src, dst, standardize=standardize)
    out_pages = count_pdf_pages(dst)
    if out_pages != src_pages:
        raise ConversionError(
            f"Page count mismatch for {src}: source has {src_pages} pages, "
            f"output has {out_pages}"
        )


@dataclass(frozen=True)
class Action:
    """A planned filesystem operation. kind is 'Convert' | 'Copy' | 'MakeDir'."""
    kind: str
    src: Path
    dst: Path


def _is_tiff(path: Path) -> bool:
    return path.suffix.lower() in TIFF_EXTENSIONS


def default_output(source: Path) -> Path:
    return source.parent / f"{source.name} converted"


def plan_actions(source_root: Path, output_root: Path, force: bool) -> list[Action]:  # (verbatim from CLI)
    actions: list[Action] = []
    actions.append(Action("MakeDir", source_root, output_root))

    for entry in sorted(source_root.rglob("*")):
        rel = entry.relative_to(source_root)
        target = output_root / rel

        if entry.is_symlink():
            if entry.resolve().is_dir():
                actions.append(Action("MakeDir", entry, target))
                continue
            entry = entry.resolve()

        if entry.is_dir():
            actions.append(Action("MakeDir", entry, target))
        elif entry.is_file():
            if _is_tiff(entry):
                pdf_target = target.with_suffix(".pdf")
                if not force and should_skip(entry, pdf_target):
                    continue
                actions.append(Action("Convert", entry, pdf_target))
            else:
                actions.append(Action("Copy", entry, target))

    return actions


@dataclass(frozen=True)
class PlanSummary:
    tiff_count: int
    copy_count: int
    dir_count: int
    total_bytes: int


def summarize_plan(actions: list[Action]) -> PlanSummary:
    converts = [a for a in actions if a.kind == "Convert"]
    copies = [a for a in actions if a.kind == "Copy"]
    dirs = [a for a in actions if a.kind == "MakeDir"]
    total = 0
    for a in converts + copies:
        try:
            total += a.src.stat().st_size
        except OSError:
            pass
    return PlanSummary(
        tiff_count=len(converts),
        copy_count=len(copies),
        dir_count=len(dirs),
        total_bytes=total,
    )


@dataclass(frozen=True)
class RunSummary:
    converted: int
    copied: int
    dirs_created: int
    failures: list[tuple[Path, str]]


def _run_convert(action: Action, standardize: bool) -> tuple[Action, str | None]:
    """Execute one Convert action. Returns (action, error_or_None); never raises."""
    try:
        convert_one(action.src, action.dst, standardize=standardize)
        return action, None
    except Exception as exc:  # noqa: BLE001
        return action, f"{type(exc).__name__}: {exc}"


def run_conversion(
    source_root: Path,
    output_root: Path,
    *,
    standardize: bool = True,
    force: bool = False,
    workers: int | None = None,
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> RunSummary:
    """Plan, execute, and summarize a full run using a thread pool.

    Directories and copies run first (sequentially) so the tree exists before
    conversions write into it; conversions then run on a ThreadPoolExecutor.
    progress_cb(done, total, label) is called after each conversion completes,
    where total is the number of conversions.
    """
    import os

    workers = workers or min(8, (os.cpu_count() or 2))

    actions = plan_actions(source_root, output_root, force=force)
    convert_actions = [a for a in actions if a.kind == "Convert"]
    dirs = [a for a in actions if a.kind == "MakeDir"]
    copies = [a for a in actions if a.kind == "Copy"]

    dirs_created = 0
    for a in dirs:
        a.dst.mkdir(parents=True, exist_ok=True)
        dirs_created += 1

    copied = 0
    failures: list[tuple[Path, str]] = []
    for a in copies:
        try:
            a.dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(a.src, a.dst)
            copied += 1
        except OSError as exc:
            failures.append((a.src, f"{type(exc).__name__}: {exc}"))

    converted = 0
    total = len(convert_actions)
    done = 0
    if convert_actions:
        worker = functools.partial(_run_convert, standardize=standardize)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(worker, a) for a in convert_actions]
            for fut in as_completed(futures):
                action, error = fut.result()
                done += 1
                if error is None:
                    converted += 1
                else:
                    failures.append((action.src, error))
                if progress_cb is not None:
                    progress_cb(done, total, action.src.name)

    return RunSummary(
        converted=converted,
        copied=copied,
        dirs_created=dirs_created,
        failures=failures,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_tiff_convert.py -q`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add src/aa_tool/tiff_convert.py tests/test_tiff_convert.py
git commit -m "feat: TIFF-to-PDF conversion engine with thread-pool runner"
```

---

### Task 3: Header `steps` parameter

**Files:**
- Modify: `src/aa_tool/ui/header.py:12-52`
- Test: `tests/test_ui_header.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `Header(active_step, context_html="", on_back_to_tools=None, lease=None, steps=None)` — when `steps` is a list of strings it overrides the default Segmentor step chips; existing callers (no `steps`) are unchanged.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ui_header.py`:

```python
def test_custom_steps_render(qtbot):
    from PySide6 import QtWidgets

    header = Header(active_step=2, steps=["1 · Open", "2 · Convert"])
    qtbot.addWidget(header)
    labels = [w.text() for w in header.findChildren(QtWidgets.QLabel)]
    assert "2 · Convert" in labels
    assert "3 · Export" not in labels
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_ui_header.py::test_custom_steps_render -q`
Expected: FAIL — `Header.__init__() got an unexpected keyword argument 'steps'`.

- [ ] **Step 3: Add the parameter**

In `src/aa_tool/ui/header.py`, change the constructor signature (currently ends with `lease: str | None = None,`) to add `steps`:

```python
    def __init__(
        self,
        active_step: int,
        context_html: str = "",
        on_back_to_tools: Callable[[], None] | None = None,
        lease: str | None = None,
        steps: list[str] | None = None,
    ):
```

Then change the step-chip loop (currently `for i, label in enumerate(_STEPS, start=1):`) to:

```python
        step_labels = steps if steps is not None else _STEPS
        for i, label in enumerate(step_labels, start=1):
            chip = QtWidgets.QLabel(label)
            chip.setObjectName("stepActive" if i == active_step else "step")
            layout.addWidget(chip)
```

- [ ] **Step 4: Run the header tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_ui_header.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/aa_tool/ui/header.py tests/test_ui_header.py
git commit -m "feat: Header accepts custom step labels"
```

---

### Task 4: Tool icon

**Files:**
- Create: `src/aa_tool/resources/icons/tiff_converter.svg`
- Test: `tests/test_icons.py`

**Interfaces:**
- Consumes: `aa_tool.ui.icons.svg_pixmap` (existing).
- Produces: a renderable resource at `icons/tiff_converter.svg`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_icons.py`:

```python
def test_tiff_converter_icon_renders(qtbot):
    pm = svg_pixmap("icons/tiff_converter.svg", 48)
    assert not pm.isNull()
    assert pm.width() == 48
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_icons.py::test_tiff_converter_icon_renders -q`
Expected: FAIL (the pixmap is null because the file does not exist).

- [ ] **Step 3: Create the icon**

Create `src/aa_tool/resources/icons/tiff_converter.svg` (a document with a conversion arrow, matching the pine stroke style of `segmentor.svg`):

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#1d5c54" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
  <rect x="3" y="4" width="9" height="12" rx="1.5"/>
  <path d="M6 8h3M6 11h3"/>
  <path d="M12 10h6m0 0-2.5-2.5M18 10l-2.5 2.5"/>
  <rect x="14" y="13" width="7" height="7" rx="1.5"/>
</svg>
```

- [ ] **Step 4: Run the icon tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_icons.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/aa_tool/resources/icons/tiff_converter.svg tests/test_icons.py
git commit -m "feat: add Batch TIFF to PDF Converter icon"
```

---

### Task 5: Tool package (open screen + plan/result screen + worker)

**Files:**
- Create: `src/aa_tool/ui/tiff_converter/__init__.py`
- Create: `src/aa_tool/ui/tiff_converter/plan_screen.py`
- Create: `src/aa_tool/ui/tiff_converter/tool.py`
- Test: `tests/test_tiff_converter_tool.py`

**Interfaces:**
- Consumes: `aa_tool.tiff_convert` (`default_output`, `plan_actions`, `summarize_plan`, `PlanSummary`, `run_conversion`, `RunSummary`), `aa_tool.ui.header.Header`, `aa_tool.ui.theme`.
- Produces (Task 6 relies on these):
  - `TiffConverterTool(on_back_to_tools: Callable[[], None])` — a `QtWidgets.QWidget`.
  - `TiffConverterTool.load_folder(folder: Path) -> None` — advances to the plan screen.
  - `TiffConverterTool.plan_screen` attribute holding the current `PlanScreen` (or `None`).
  - `PlanScreen(source, on_back_to_tools, on_new_folder)` with attributes `summary: PlanSummary`, `out_dir: Path`, and a synchronous `do_convert() -> RunSummary` method.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tiff_converter_tool.py`:

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PIL import Image
from PySide6 import QtWidgets

from aa_tool.ui.tiff_converter.tool import TiffConverterTool


def _make_tiff(path: Path, pages: int = 1) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = [Image.new("RGB", (120, 160), "white") for _ in range(pages)]
    frames[0].save(path, save_all=True, append_images=frames[1:])
    return path


def test_open_screen_has_choose_button(qtbot):
    tool = TiffConverterTool(on_back_to_tools=lambda: None)
    qtbot.addWidget(tool)
    buttons = [b.text() for b in tool.findChildren(QtWidgets.QPushButton)]
    assert any("Choose" in t for t in buttons)


def test_back_to_tools_callback_wired(qtbot):
    called = []
    tool = TiffConverterTool(on_back_to_tools=lambda: called.append(True))
    qtbot.addWidget(tool)
    back = [b for b in tool.findChildren(QtWidgets.QPushButton)
            if b.objectName() == "backToTools"]
    assert back
    back[0].click()
    assert called == [True]


def test_load_folder_shows_plan_counts(qtbot, tmp_path):
    src = tmp_path / "scans"
    _make_tiff(src / "a.tif")
    _make_tiff(src / "b.tif")
    (src / "notes.txt").write_text("hi")

    tool = TiffConverterTool(on_back_to_tools=lambda: None)
    qtbot.addWidget(tool)
    tool.load_folder(src)

    assert tool.plan_screen is not None
    assert tool.plan_screen.summary.tiff_count == 2
    assert tool.plan_screen.summary.copy_count == 1


def test_do_convert_writes_pdfs(qtbot, tmp_path):
    src = tmp_path / "scans"
    _make_tiff(src / "a.tif", pages=2)

    tool = TiffConverterTool(on_back_to_tools=lambda: None)
    qtbot.addWidget(tool)
    tool.load_folder(src)
    result = tool.plan_screen.do_convert()

    assert result.converted == 1
    assert (tool.plan_screen.out_dir / "a.pdf").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_tiff_converter_tool.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aa_tool.ui.tiff_converter'`.

- [ ] **Step 3: Create the package marker**

Create `src/aa_tool/ui/tiff_converter/__init__.py` (empty file).

- [ ] **Step 4: Create the plan/result screen and worker**

Create `src/aa_tool/ui/tiff_converter/plan_screen.py`:

```python
from collections.abc import Callable
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from aa_tool.tiff_convert import (
    PlanSummary,
    RunSummary,
    default_output,
    plan_actions,
    run_conversion,
    summarize_plan,
)
from aa_tool.ui import theme
from aa_tool.ui.header import Header

CONVERTER_STEPS = ["1 · Open", "2 · Convert"]


def _format_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{int(size)} B" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


class ConversionWorker(QtCore.QObject):
    """Runs run_conversion off the UI thread, relaying progress and the result."""

    progress = QtCore.Signal(int, int, str)
    finished = QtCore.Signal(object)  # RunSummary

    def __init__(self, source: Path, out_dir: Path, standardize: bool):
        super().__init__()
        self._source = source
        self._out_dir = out_dir
        self._standardize = standardize

    @QtCore.Slot()
    def run(self) -> None:
        summary = run_conversion(
            self._source,
            self._out_dir,
            standardize=self._standardize,
            progress_cb=lambda done, total, label: self.progress.emit(done, total, label),
        )
        self.finished.emit(summary)


class PlanScreen(QtWidgets.QWidget):
    def __init__(
        self,
        source: Path,
        on_back_to_tools: Callable[[], None],
        on_new_folder: Callable[[], None],
    ):
        super().__init__()
        self.setObjectName("screen")
        self.source = source
        self.on_new_folder = on_new_folder
        self.out_dir = default_output(source)
        self.summary: PlanSummary = summarize_plan(
            plan_actions(source, self.out_dir, force=False)
        )
        self._thread: QtCore.QThread | None = None
        self._worker: ConversionWorker | None = None

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.header = Header(
            active_step=2,
            context_html=f'Folder&nbsp;<span style="color:{theme.PINE}">{source.name}</span>',
            on_back_to_tools=on_back_to_tools,
            steps=CONVERTER_STEPS,
        )
        outer.addWidget(self.header)

        center = QtWidgets.QVBoxLayout()
        center.setContentsMargins(48, 0, 48, 0)
        center.setSpacing(16)
        center.addStretch()
        outer.addLayout(center, 1)

        title = QtWidgets.QLabel("Ready to convert")
        title.setObjectName("h1")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        center.addWidget(title)

        self.summary_label = QtWidgets.QLabel(
            f"{self.summary.tiff_count} TIFFs to convert\n"
            f"{self.summary.copy_count} other files to copy\n"
            f"{_format_size(self.summary.total_bytes)} total"
        )
        self.summary_label.setObjectName("sub")
        self.summary_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        center.addWidget(self.summary_label)

        center.addSpacing(10)

        dest = QtWidgets.QHBoxLayout()
        dest.setSpacing(10)
        self.path_label = QtWidgets.QLabel(str(self.out_dir))
        self.path_label.setObjectName("savePath")
        change_button = QtWidgets.QPushButton("Change…")
        change_button.setObjectName("ghost")
        change_button.clicked.connect(self._change_folder)
        dest.addStretch()
        dest.addWidget(QtWidgets.QLabel("Save to:"))
        dest.addWidget(self.path_label)
        dest.addWidget(change_button)
        dest.addStretch()
        center.addLayout(dest)

        self.standardize_checkbox = QtWidgets.QCheckBox(
            "Standardize pages (letter / legal)"
        )
        self.standardize_checkbox.setChecked(True)
        center.addWidget(
            self.standardize_checkbox, alignment=QtCore.Qt.AlignmentFlag.AlignCenter
        )

        center.addSpacing(10)
        self.convert_button = QtWidgets.QPushButton("Convert  →")
        self.convert_button.setObjectName("primary")
        self.convert_button.clicked.connect(self._on_convert_clicked)
        center.addWidget(
            self.convert_button, alignment=QtCore.Qt.AlignmentFlag.AlignCenter
        )

        self.result_label = QtWidgets.QLabel()
        self.result_label.setObjectName("success")
        self.result_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.result_label.setVisible(False)
        center.addSpacing(6)
        center.addWidget(self.result_label)

        self.failures_label = QtWidgets.QLabel()
        self.failures_label.setObjectName("warn")
        self.failures_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.failures_label.setWordWrap(True)
        self.failures_label.setVisible(False)
        center.addWidget(self.failures_label)

        self.new_folder_button = QtWidgets.QPushButton("Convert another folder  →")
        self.new_folder_button.setObjectName("primary")
        self.new_folder_button.clicked.connect(lambda: self.on_new_folder())
        self.new_folder_button.setVisible(False)
        center.addSpacing(4)
        center.addWidget(
            self.new_folder_button, alignment=QtCore.Qt.AlignmentFlag.AlignCenter
        )

        center.addStretch()

    def _change_folder(self) -> None:
        chosen = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Choose output folder", str(self.out_dir)
        )
        if chosen:
            self.out_dir = Path(chosen)
            self.path_label.setText(str(self.out_dir))

    def do_convert(self) -> RunSummary:
        """Synchronous convert (used by tests and as the worker's core call)."""
        return run_conversion(
            self.source,
            self.out_dir,
            standardize=self.standardize_checkbox.isChecked(),
        )

    def _on_convert_clicked(self) -> None:
        self.convert_button.setEnabled(False)
        self.result_label.setVisible(False)
        self.failures_label.setVisible(False)

        self._thread = QtCore.QThread(self)
        self._worker = ConversionWorker(
            self.source, self.out_dir, self.standardize_checkbox.isChecked()
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.start()

    @QtCore.Slot(int, int, str)
    def _on_progress(self, done: int, total: int, label: str) -> None:
        self.header.set_progress(done, total, f"{done}/{total}  {label}")

    @QtCore.Slot(object)
    def _on_finished(self, summary: RunSummary) -> None:
        self.result_label.setText(
            f"✓ {summary.converted} converted · "
            f"{summary.copied} copied · {len(summary.failures)} failed"
        )
        self.result_label.setVisible(True)
        if summary.failures:
            names = ", ".join(src.name for src, _ in summary.failures)
            self.failures_label.setText(f"Failed: {names}")
            self.failures_label.setVisible(True)
        self.new_folder_button.setVisible(True)
        self.convert_button.setEnabled(True)
```

- [ ] **Step 5: Create the tool widget + open screen**

Create `src/aa_tool/ui/tiff_converter/tool.py`:

```python
from collections.abc import Callable
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from aa_tool.ui.header import Header
from aa_tool.ui.tiff_converter.plan_screen import CONVERTER_STEPS, PlanScreen


class TiffConverterTool(QtWidgets.QWidget):
    def __init__(self, on_back_to_tools: Callable[[], None]):
        super().__init__()
        self.setObjectName("screen")
        self.on_back_to_tools = on_back_to_tools
        self.plan_screen: PlanScreen | None = None

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.stack = QtWidgets.QStackedWidget()
        outer.addWidget(self.stack)

        self._build_open_screen()

    def _build_open_screen(self) -> None:
        page = QtWidgets.QWidget()
        page.setObjectName("screen")
        v = QtWidgets.QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(Header(
            active_step=1,
            context_html="Batch TIFF to PDF Converter",
            on_back_to_tools=self.on_back_to_tools,
            steps=CONVERTER_STEPS,
        ))

        center = QtWidgets.QVBoxLayout()
        center.setContentsMargins(0, 0, 0, 0)
        center.setSpacing(14)
        center.addStretch()
        h1 = QtWidgets.QLabel("Convert a folder of TIFFs")
        h1.setObjectName("h1")
        h1.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        sub = QtWidgets.QLabel(
            "Choose a folder. Every TIFF becomes a PDF, the folder structure is\n"
            "mirrored, and other files are copied across unchanged."
        )
        sub.setObjectName("sub")
        sub.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        button = QtWidgets.QPushButton("Choose folder…")
        button.setObjectName("primary")
        button.clicked.connect(self._choose_folder)
        center.addWidget(h1)
        center.addWidget(sub)
        center.addSpacing(8)
        center.addWidget(button, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        center.addStretch()
        v.addLayout(center, 1)

        self.open_index = self.stack.addWidget(page)

    def _choose_folder(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Choose folder of TIFFs", str(Path.home())
        )
        if folder:
            self.load_folder(Path(folder))

    def load_folder(self, folder: Path) -> None:
        screen = PlanScreen(
            folder,
            on_back_to_tools=self.on_back_to_tools,
            on_new_folder=self._restart,
        )
        if self.plan_screen is not None:
            self.stack.removeWidget(self.plan_screen)
            self.plan_screen.deleteLater()
        index = self.stack.addWidget(screen)
        self.stack.setCurrentIndex(index)
        self.plan_screen = screen

    def _restart(self) -> None:
        self.stack.setCurrentIndex(self.open_index)
        if self.plan_screen is not None:
            self.stack.removeWidget(self.plan_screen)
            self.plan_screen.deleteLater()
            self.plan_screen = None
```

- [ ] **Step 6: Run the tool tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_tiff_converter_tool.py -q`
Expected: PASS (4 passed).

- [ ] **Step 7: Commit**

```bash
git add src/aa_tool/ui/tiff_converter/ tests/test_tiff_converter_tool.py
git commit -m "feat: Batch TIFF to PDF Converter tool screens"
```

---

### Task 6: Register the tool on the home board

**Files:**
- Modify: `src/aa_tool/tools.py:25-39`
- Test: `tests/test_tools.py`

**Interfaces:**
- Consumes: `TiffConverterTool` (Task 5), `Tool` dataclass (existing).
- Produces: `TIFF_CONVERTER_TOOL` in the module-level `TOOLS` list.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tools.py`:

```python
def test_tiff_converter_registered_under_nmslo():
    from aa_tool.tools import TOOLS

    by_id = {t.id: t for t in TOOLS}
    tool = by_id["tiff_converter"]
    assert tool.name == "Batch TIFF to PDF Converter"
    assert tool.category == "NM State Land Office"
    assert tool.icon == "icons/tiff_converter.svg"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_tools.py::test_tiff_converter_registered_under_nmslo -q`
Expected: FAIL — `KeyError: 'tiff_converter'`.

- [ ] **Step 3: Register the tool**

In `src/aa_tool/tools.py`, after the `SEGMENTOR_TOOL` definition and before `TOOLS`, add the import and the tool, then extend `TOOLS`:

```python
from aa_tool.ui.tiff_converter.tool import TiffConverterTool

TIFF_CONVERTER_TOOL = Tool(
    id="tiff_converter",
    name="Batch TIFF to PDF Converter",
    description=(
        "Convert a folder of TIFFs to PDFs, mirroring the folder structure "
        "and copying any non-TIFF files across unchanged."
    ),
    category="NM State Land Office",
    icon="icons/tiff_converter.svg",
    build=lambda on_back: TiffConverterTool(on_back),
)

TOOLS: list[Tool] = [SEGMENTOR_TOOL, TIFF_CONVERTER_TOOL]
```

(Replace the existing `TOOLS: list[Tool] = [SEGMENTOR_TOOL]` line.)

- [ ] **Step 4: Run the tools tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_tools.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/aa_tool/tools.py tests/test_tools.py
git commit -m "feat: register Batch TIFF to PDF Converter on the home board"
```

---

### Task 7: Full suite + manual smoke check

**Files:** none (verification only).

- [ ] **Step 1: Run the whole test suite**

Run: `./venv/bin/python -m pytest -q`
Expected: all tests PASS (no failures, no errors).

- [ ] **Step 2: Launch the app and smoke-test the new tool**

Run: `./venv/bin/python main.py`
Expected: the home board shows two cards under "NM State Land Office" — the Segmentor and "Batch TIFF to PDF Converter". Clicking the converter opens the "Convert a folder of TIFFs" screen; choosing a folder shows the plan; Convert produces a `<source> converted/` folder with PDFs and a result line. Close the window when done.

- [ ] **Step 3: Final commit (if any changes were needed during smoke test)**

```bash
git add -A
git commit -m "test: verify Batch TIFF to PDF Converter end to end"
```

---

## Self-Review

**Spec coverage:**
- Open screen → plan screen w/ editable destination + standardize toggle → convert → inline result with failures: Tasks 5 (screens) + 2 (engine). ✓
- Plan shows TIFF count / copy count / total size: Task 2 `summarize_plan`, Task 5 `summary_label`. ✓
- Editable destination defaulting to `<source> converted/`: Task 2 `default_output`, Task 5 `_change_folder`. ✓
- Standardize on by default, toggleable: Task 5 `standardize_checkbox` (checked). ✓
- Skip already-converted files: Task 2 `should_skip` inside `plan_actions`. ✓
- Mirror structure / copy non-TIFFs: Task 2 `plan_actions` + `run_conversion`. ✓
- Thread pool, no multiprocessing: Task 2 `ThreadPoolExecutor`. ✓
- No log files: Task 2 writes only PDFs + copies; no log code. ✓
- Off-UI-thread with header progress pill: Task 5 `ConversionWorker` + `Header.set_progress`. ✓
- Inline result + failure list, "Convert another folder": Task 5 `_on_finished`. ✓
- Header steps configurable: Task 3. ✓
- Registered under NM State Land Office with new icon: Tasks 4 + 6. ✓
- Pillow + pypdf deps: Task 1. ✓

**Placeholder scan:** No TBD/TODO; every code step has complete code. ✓

**Type consistency:** `RunSummary` (converted/copied/dirs_created/failures), `PlanSummary` (tiff_count/copy_count/dir_count/total_bytes), `default_output`, `run_conversion(..., progress_cb)`, `PlanScreen.do_convert`, `TiffConverterTool.load_folder`/`.plan_screen` are used identically across tasks. ✓
