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
