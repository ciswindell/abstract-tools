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
import struct
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
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


class _TiffReader(io.RawIOBase):
    """The file object every TIFF is opened through. Two deliberate differences
    from a plain ``open(path, "rb")``:

    * **No ``fileno()``.** For a compressed TIFF, Pillow hands the raw file
      descriptor to libtiff, which moves the OS file offset; Pillow's own
      buffered reads afterwards land on the wrong bytes. It then parses image
      data as a tag directory and warns ``UserWarning: Truncated File Read``,
      losing the file's EXIF — including the orientation that decides whether a
      page comes out upright. Without a descriptor, Pillow feeds libtiff from
      Python-side reads and stays in sync.
    * **Reads past EOF are zero-padded** instead of returning short. A tag whose
      data offset points past the end of the file otherwise aborts Pillow's
      directory parse *before* it reads the pointer to the next page, silently
      dropping every page after the damaged one.
    """

    def __init__(self, path: Path):
        super().__init__()
        self._fp = open(path, "rb")  # noqa: SIM115 — closed in close()

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        return self._fp.seek(offset, whence)

    def tell(self) -> int:
        return self._fp.tell()

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            return self._fp.read()
        start = self._fp.tell()
        data = self._fp.read(size)
        if len(data) < size:
            data += b"\x00" * (size - len(data))
            self._fp.seek(start + size)  # keep tell() consistent with a full read
        return data

    def readinto(self, buffer) -> int:  # noqa: ANN001 (buffer protocol)
        data = self.read(len(buffer))
        buffer[: len(data)] = data
        return len(data)

    def close(self) -> None:
        try:
            self._fp.close()
        finally:
            super().close()


# TIFF structure constants (see the TIFF 6.0 spec / BigTIFF).
_CLASSIC_MAGIC = 42
_BIG_MAGIC = 43
_STRIP_OFFSETS, _STRIP_BYTE_COUNTS = 273, 279
_TILE_OFFSETS, _TILE_BYTE_COUNTS = 324, 325
_INT_TYPES = {1: 1, 3: 2, 4: 4, 16: 8}  # BYTE, SHORT, LONG, LONG8
# Width in bytes of every TIFF field type (6.0 plus the BigTIFF additions).
_TYPE_WIDTHS = {
    1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4,
    10: 8, 11: 4, 12: 8, 13: 4, 16: 8, 17: 8, 18: 8,
}
_MAX_PAGES = 100_000  # a lease scan never approaches this; a corrupt chain might


@dataclass(frozen=True)
class TiffScan:
    """What a TIFF's directory chain says, read without trusting Pillow.

    ``offsets`` is one file offset per page, in order. The rest name damage, by
    1-based page number: ``partial_pages`` have pixel data running past the end
    of the file, ``damaged_tag_pages`` have a tag whose data does (the damage
    Pillow abandons the page chain over), and ``truncated`` means the chain
    itself ran off the end.
    """

    offsets: tuple[int, ...]
    truncated: bool = False
    partial_pages: tuple[int, ...] = ()
    damaged_tag_pages: tuple[int, ...] = ()

    @property
    def pages(self) -> int:
        return len(self.offsets)

    @property
    def damaged(self) -> bool:
        return self.truncated or bool(self.partial_pages or self.damaged_tag_pages)


def _read_ints(fp, endian: str, typ: int, count: int, raw: bytes, size: int) -> list[int]:
    """Values of an integer-typed tag, whether stored inline or at an offset."""
    unit = _INT_TYPES.get(typ)
    if unit is None:
        return []
    if unit * count > len(raw):
        (offset,) = struct.unpack(endian + ("Q" if size == 8 else "L"), raw[:size])
        fp.seek(offset)
        raw = fp.read(unit * count)
        if len(raw) < unit * count:
            return []
    code = {1: "B", 2: "H", 4: "L", 8: "Q"}[unit]
    return list(struct.unpack(f"{endian}{count}{code}", raw[: unit * count]))


def scan_tiff_ifds(path: Path) -> TiffScan:
    """Walk a TIFF's page (IFD) chain using only each directory's own structure.

    Every page is an IFD: an entry count, that many fixed-width entries, then the
    offset of the next page. Following it needs none of the out-of-line tag data
    that Pillow gives up on, so a damaged tag cannot hide a page from this walk.
    """
    try:
        file_size = path.stat().st_size
        with open(path, "rb") as fp:
            header = fp.read(16)
            if len(header) < 8:
                msg = f"Not a readable TIFF (file is {len(header)} bytes): {path}"
                raise ConversionError(msg)
            if header[:2] == b"II":
                endian = "<"
            elif header[:2] == b"MM":
                endian = ">"
            else:
                msg = f"Not a TIFF (byte order mark is {header[:2]!r}): {path}"
                raise ConversionError(msg)

            (magic,) = struct.unpack(endian + "H", header[2:4])
            if magic == _CLASSIC_MAGIC:
                big, entry_size, count_size, offset_size = False, 12, 2, 4
                (next_ifd,) = struct.unpack(endian + "L", header[4:8])
            elif magic == _BIG_MAGIC:
                (offset_bytes,) = struct.unpack(endian + "H", header[4:6])
                if offset_bytes != 8 or len(header) < 16:
                    msg = f"Unsupported BigTIFF layout: {path}"
                    raise ConversionError(msg)
                big, entry_size, count_size, offset_size = True, 20, 8, 8
                (next_ifd,) = struct.unpack(endian + "Q", header[8:16])
            else:
                msg = f"Not a TIFF (magic number {magic}): {path}"
                raise ConversionError(msg)

            count_code = endian + ("Q" if big else "H")
            offset_code = endian + ("Q" if big else "L")
            offsets: list[int] = []
            partial: list[int] = []
            damaged: list[int] = []
            seen: set[int] = set()
            truncated = False

            while next_ifd and next_ifd not in seen and len(offsets) < _MAX_PAGES:
                seen.add(next_ifd)
                if next_ifd + count_size > file_size:
                    truncated = True
                    break
                fp.seek(next_ifd)
                (entries,) = struct.unpack(count_code, fp.read(count_size))
                block = fp.read(entries * entry_size)
                offsets.append(next_ifd)
                if len(block) < entries * entry_size:
                    truncated = True  # the directory itself runs off the end
                    break
                tail_pos = fp.tell()
                cut_pixels, bad_tag = _inspect_entries(
                    fp, block, endian, big, entry_size, offset_size, file_size
                )
                if cut_pixels:
                    partial.append(len(offsets))
                if bad_tag:
                    damaged.append(len(offsets))
                fp.seek(tail_pos)  # inspecting entries reads tag data elsewhere
                tail = fp.read(offset_size)
                if len(tail) < offset_size:
                    truncated = True
                    break
                (next_ifd,) = struct.unpack(offset_code, tail)

            if not offsets:
                msg = f"TIFF has no readable pages: {path}"
                raise ConversionError(msg)
            return TiffScan(tuple(offsets), truncated, tuple(partial), tuple(damaged))
    except OSError as exc:
        msg = f"Could not read {path}: {exc}"
        raise ConversionError(msg) from exc


def _inspect_entries(
    fp, block, endian: str, big: bool, entry_size: int, offset_size: int, file_size: int
) -> tuple[bool, bool]:
    """Inspect one page's tag entries: (pixel data cut off, tag data past EOF)."""
    tag_code = endian + ("HHQ8s" if big else "HHL4s")
    data_offsets: list[int] = []
    byte_counts: list[int] = []
    bad_tag = False
    for i in range(0, len(block), entry_size):
        tag, typ, count, raw = struct.unpack(tag_code, block[i : i + entry_size])
        width = _TYPE_WIDTHS.get(typ)
        if width is not None and width * count > len(raw):
            (offset,) = struct.unpack(endian + ("Q" if big else "L"), raw[:offset_size])
            if offset + width * count > file_size:
                bad_tag = True
        if tag in (_STRIP_OFFSETS, _TILE_OFFSETS):
            data_offsets = _read_ints(fp, endian, typ, count, raw, offset_size)
        elif tag in (_STRIP_BYTE_COUNTS, _TILE_BYTE_COUNTS):
            byte_counts = _read_ints(fp, endian, typ, count, raw, offset_size)
    if not data_offsets or len(byte_counts) != len(data_offsets):
        return False, bad_tag  # nothing dependable to check the pixel data against
    cut = any(o + c > file_size for o, c in zip(data_offsets, byte_counts))
    return cut, bad_tag


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


def count_tiff_pages(path: Path) -> int:
    """The page count, read from the directory chain rather than from Pillow.

    Pillow under-reports this on a TIFF with a damaged tag — and by exactly the
    pages it would also fail to convert, so a Pillow-vs-Pillow check cannot catch
    a short PDF. This number is independent of that failure.
    """
    return scan_tiff_ifds(path).pages


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


def _convert_pillow(src: Path, dst: Path, standardize: bool, scan: TiffScan) -> None:
    """Write every page the directory chain names into one PDF."""
    from PIL import Image, JpegImagePlugin  # noqa: F401 — JPEG SAVE handler
    from pypdf import PdfWriter

    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        reader = _TiffReader(src)
        try:
            img = Image.open(reader)
            _restore_lost_pages(img, scan)

            if not standardize:
                pages = []
                for i in range(scan.pages):
                    img.seek(i)
                    pages.append(img.convert("RGB"))
                pages[0].save(dst, "PDF", save_all=True, append_images=pages[1:])
                return

            writer = PdfWriter()
            for i in range(scan.pages):
                img.seek(i)
                canvas, dpi = _standardize_page(img.convert("RGB"))
                buf = io.BytesIO()
                canvas.save(buf, "PDF", resolution=dpi)
                buf.seek(0)
                writer.append(buf)
            with open(dst, "wb") as f:
                writer.write(f)
        finally:
            reader.close()
    except Exception as exc:  # noqa: BLE001
        raise ConversionError(f"Pillow convert failed for {src}: {exc}") from exc


def _restore_lost_pages(img, scan: TiffScan) -> None:
    """Hand Pillow the page offsets it lost, when it found fewer than the chain has.

    ``TiffImageFile`` seeks by a list of directory offsets and only consults the
    chain when that list is short. Filling the list in is enough to reach a page
    Pillow could not walk to; it still does all the decoding itself.
    """
    if scan.pages <= getattr(img, "n_frames", 1):
        return
    if not hasattr(img, "_frame_pos"):  # an unexpected Pillow — leave it alone
        return
    img._frame_pos = list(scan.offsets)
    img._n_frames = scan.pages
    img.is_animated = scan.pages > 1
    img._TiffImageFile__next = 0


def _damage_notes(scan: TiffScan) -> list[str]:
    """Plain-English notes about what was wrong with a file we converted anyway."""
    notes = []
    if scan.damaged_tag_pages:
        listed = ", ".join(str(n) for n in scan.damaged_tag_pages)
        notes.append(f"repaired damaged tag on page {listed}")
    if scan.truncated:
        notes.append("file ends mid-page-directory")
    if scan.partial_pages:
        listed = ", ".join(str(n) for n in scan.partial_pages)
        notes.append(f"incomplete scan data on page {listed}")
    return notes


def convert_one(src: Path, dst: Path, standardize: bool = True) -> list[str]:
    """Convert one TIFF to PDF, verifying the output against the source page count.

    Returns notes about any damage that had to be worked around — empty for a
    healthy file. The page count comes from :func:`scan_tiff_ifds`, so a PDF that
    is short a page fails here instead of being reported as converted.
    """
    scan = scan_tiff_ifds(src)
    _convert_pillow(src, dst, standardize=standardize, scan=scan)
    out_pages = count_pdf_pages(dst)
    if out_pages != scan.pages:
        raise ConversionError(
            f"Page count mismatch for {src}: source has {scan.pages} pages, "
            f"output has {out_pages}"
        )
    return _damage_notes(scan)


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
    # Files that converted completely but had damage worked around; each note
    # says what, so the user knows which PDFs are worth a look.
    repaired: list[tuple[Path, str]] = field(default_factory=list)


def _run_convert(
    action: Action, standardize: bool
) -> tuple[Action, str | None, list[str]]:
    """Execute one Convert action. Returns (action, error_or_None, notes); never raises."""
    try:
        return action, None, convert_one(action.src, action.dst, standardize=standardize)
    except Exception as exc:  # noqa: BLE001
        return action, f"{type(exc).__name__}: {exc}", []


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
    repaired: list[tuple[Path, str]] = []
    if convert_actions:
        worker = functools.partial(_run_convert, standardize=standardize)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(worker, a) for a in convert_actions]
            for fut in as_completed(futures):
                action, error, notes = fut.result()
                done += 1
                if error is None:
                    converted += 1
                    if notes:
                        repaired.append((action.src, "; ".join(notes)))
                else:
                    failures.append((action.src, error))
                if progress_cb is not None:
                    progress_cb(done, total, action.src.name)

    return RunSummary(
        converted=converted,
        copied=copied,
        dirs_created=dirs_created,
        failures=failures,
        repaired=sorted(repaired),
    )
