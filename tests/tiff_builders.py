"""Hand-built TIFF files for the page-recovery tests.

Pillow cannot write the damage these tests need (a tag whose data offset points
past the end of the file), so the bytes are assembled here directly. Every file
is synthetic — no customer scans.
"""

from __future__ import annotations

import struct
from pathlib import Path

WIDTH = HEIGHT = 64

# Tag ids used below.
IMAGE_WIDTH = 256
IMAGE_LENGTH = 257
BITS_PER_SAMPLE = 258
COMPRESSION = 259
PHOTOMETRIC = 262
IMAGE_DESCRIPTION = 270
STRIP_OFFSETS = 273
SAMPLES_PER_PIXEL = 277
ROWS_PER_STRIP = 278
STRIP_BYTE_COUNTS = 279
XMP = 700

_TYPE_ASCII = 2
_TYPE_SHORT = 3
_TYPE_LONG = 4
_TYPE_SIZES = {_TYPE_ASCII: 1, _TYPE_SHORT: 2, _TYPE_LONG: 4}

ENTRY_SIZE = 12
PAST_EOF = 9_000_000  # an offset no test file is anywhere near


def _entry(tag: int, typ: int, count: int, value: int) -> bytes:
    """One 12-byte IFD entry; values wider than 4 bytes are an offset."""
    payload = (
        struct.pack("<L", value)
        if _TYPE_SIZES[typ] * count > 4 or typ == _TYPE_LONG
        else struct.pack("<H", value) + b"\0\0"
    )
    return struct.pack("<HHL", tag, typ, count) + payload


def _ifd(entries: list[bytes], next_offset: int) -> bytes:
    return struct.pack("<H", len(entries)) + b"".join(entries) + struct.pack("<L", next_offset)


def _page_entries(strip_offset: int, byte_count: int, bad_tag: int | None) -> list[bytes]:
    tags = [
        (IMAGE_WIDTH, _TYPE_SHORT, 1, WIDTH),
        (IMAGE_LENGTH, _TYPE_SHORT, 1, HEIGHT),
        (BITS_PER_SAMPLE, _TYPE_SHORT, 1, 8),
        (COMPRESSION, _TYPE_SHORT, 1, 1),  # uncompressed
        (PHOTOMETRIC, _TYPE_SHORT, 1, 1),  # black is zero
        (STRIP_OFFSETS, _TYPE_LONG, 1, strip_offset),
        (SAMPLES_PER_PIXEL, _TYPE_SHORT, 1, 1),
        (ROWS_PER_STRIP, _TYPE_SHORT, 1, HEIGHT),
        (STRIP_BYTE_COUNTS, _TYPE_LONG, 1, byte_count),
    ]
    if bad_tag is not None:
        # An out-of-line tag whose data lives past EOF — the damage Pillow gives
        # up on. Tags are emitted in ascending id order as a real writer does, so
        # where the bad tag sorts decides how much is lost: XMP (700) sorts after
        # every tag needed to decode, so the page still renders but the pointer to
        # the next page is never reached; ImageDescription (270) sorts before
        # StripOffsets (273), so the page itself becomes unreadable.
        tags.append((bad_tag, _TYPE_ASCII, 64, PAST_EOF))
    return [_entry(*t) for t in sorted(tags)]


def build_tiff(
    shades: list[int],
    damaged_page: int | None = None,
    bad_tag: int = XMP,
) -> bytes:
    """A multi-page grayscale TIFF, one page per entry in `shades` (0-255).

    `damaged_page` (0-based) gets a `bad_tag` whose data lives past end of file.
    """
    pixels = [bytes([shade]) * (WIDTH * HEIGHT) for shade in shades]
    header_len = 8
    damage = [bad_tag if i == damaged_page else None for i in range(len(shades))]
    ifd_lens = [
        2 + len(_page_entries(0, 0, damage[i])) * ENTRY_SIZE + 4 for i in range(len(shades))
    ]
    strip_start = header_len + sum(ifd_lens)

    out = b"II" + struct.pack("<HL", 42, 8)
    ifd_offset = header_len
    strip_offset = strip_start
    for i, data in enumerate(pixels):
        ifd_offset += ifd_lens[i]
        next_offset = ifd_offset if i + 1 < len(pixels) else 0
        out += _ifd(_page_entries(strip_offset, len(data), damage[i]), next_offset)
        strip_offset += len(data)
    return out + b"".join(pixels)


def write_damaged_tiff(
    path: Path,
    shades: list[int],
    damaged_page: int = 0,
    bad_tag: int = XMP,
) -> Path:
    """A multi-page TIFF whose `damaged_page` carries a past-EOF tag."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(build_tiff(shades, damaged_page=damaged_page, bad_tag=bad_tag))
    return path


def write_cut_tiff(path: Path, shades: list[int], keep_pixel_rows: int) -> Path:
    """A multi-page TIFF whose file ends mid-way through the last page's pixels."""
    path.parent.mkdir(parents=True, exist_ok=True)
    full = build_tiff(shades)
    drop = (HEIGHT - keep_pixel_rows) * WIDTH
    path.write_bytes(full[:-drop])
    return path


def write_bigtiff(path: Path, pages: int = 2) -> Path:
    """A minimal BigTIFF (magic 43, 8-byte offsets); IFD structure only."""
    path.parent.mkdir(parents=True, exist_ok=True)
    entry_count = 2
    ifd_len = 8 + entry_count * 20 + 8
    out = b"II" + struct.pack("<HHH", 43, 8, 0) + struct.pack("<Q", 16)
    for i in range(pages):
        offset = 16 + (i + 1) * ifd_len
        next_offset = offset if i + 1 < pages else 0
        entries = b"".join(
            struct.pack("<HHQQ", tag, _TYPE_SHORT, 1, value)
            for tag, value in ((IMAGE_WIDTH, WIDTH), (IMAGE_LENGTH, HEIGHT))
        )
        out += struct.pack("<Q", entry_count) + entries + struct.pack("<Q", next_offset)
    path.write_bytes(out)
    return path


# --- old-style JPEG-in-TIFF ---------------------------------------------------
# The layout the NMSLO delivery uses: one strip holding a whole JPEG, pointed at
# by both StripOffsets (273) and JPEGInterchangeFormat (513), YCbCr photometric.
# Pillow decodes this through libtiff, which is what triggers the stale-descriptor
# EXIF misparse and its "Truncated File Read" warning.

ORIENTATION = 274
X_RESOLUTION = 282
Y_RESOLUTION = 283
PLANAR_CONFIGURATION = 284
RESOLUTION_UNIT = 296
SOFTWARE = 305
DATETIME = 306
JPEG_INTERCHANGE_FORMAT = 513

_TYPE_RATIONAL = 5
_JPEG_TYPE_SIZES = {_TYPE_ASCII: 1, _TYPE_SHORT: 2, _TYPE_LONG: 4, _TYPE_RATIONAL: 8}


def _jpeg_bytes(size: tuple[int, int], seed: int = 3) -> bytes:
    import io
    import random

    from PIL import Image

    rng = random.Random(seed)
    image = Image.new("RGB", size, "white")
    pixels = image.load()
    for x in range(0, size[0], 5):  # texture, so the JPEG does not compress to nothing
        for y in range(0, size[1], 9):
            pixels[x, y] = (rng.randrange(256),) * 3
    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=70)
    return buf.getvalue()


def write_old_style_jpeg_tiff(
    path: Path, size: tuple[int, int] = (600, 800), orientation: int = 1
) -> Path:
    """A single-page JPEG-compressed TIFF laid out like the scanner's output."""
    path.parent.mkdir(parents=True, exist_ok=True)
    jpeg = _jpeg_bytes(size)
    width, height = size
    strip_start = 768

    blobs: list[tuple[int, bytes]] = []
    cursor = strip_start

    def place(data: bytes) -> int:
        nonlocal cursor
        cursor -= len(data)
        blobs.append((cursor, data))
        return cursor

    bits_off = place(struct.pack("<3H", 8, 8, 8))
    xres_off = place(struct.pack("<LL", 300, 1))
    yres_off = place(struct.pack("<LL", 300, 1))
    software_off = place(b"synthetic fixture for abstract-tools tests\0")
    datetime_off = place(b"2026:09:17 12:00:00\0")

    tags = [
        (254, _TYPE_LONG, 1, 0),
        (IMAGE_WIDTH, _TYPE_LONG, 1, width),
        (IMAGE_LENGTH, _TYPE_LONG, 1, height),
        (BITS_PER_SAMPLE, _TYPE_SHORT, 3, bits_off),
        (COMPRESSION, _TYPE_SHORT, 1, 7),  # JPEG
        (PHOTOMETRIC, _TYPE_SHORT, 1, 6),  # YCbCr
        (STRIP_OFFSETS, _TYPE_LONG, 1, strip_start),
        (ORIENTATION, _TYPE_SHORT, 1, orientation),
        (SAMPLES_PER_PIXEL, _TYPE_SHORT, 1, 3),
        (ROWS_PER_STRIP, _TYPE_LONG, 1, height),
        (STRIP_BYTE_COUNTS, _TYPE_LONG, 1, len(jpeg)),
        (X_RESOLUTION, _TYPE_RATIONAL, 1, xres_off),
        (Y_RESOLUTION, _TYPE_RATIONAL, 1, yres_off),
        (PLANAR_CONFIGURATION, _TYPE_SHORT, 1, 1),
        (RESOLUTION_UNIT, _TYPE_SHORT, 1, 2),
        (SOFTWARE, _TYPE_ASCII, 42, software_off),
        (DATETIME, _TYPE_ASCII, 20, datetime_off),
        (JPEG_INTERCHANGE_FORMAT, _TYPE_LONG, 1, strip_start),
    ]

    out = bytearray(b"II" + struct.pack("<HL", 42, 8) + struct.pack("<H", len(tags)))
    for tag, typ, count, value in sorted(tags):
        wide = _JPEG_TYPE_SIZES[typ] * count > 4
        payload = (
            struct.pack("<L", value)
            if wide or typ == _TYPE_LONG
            else struct.pack("<H", value) + b"\0\0"
        )
        out += struct.pack("<HHL", tag, typ, count) + payload
    out += struct.pack("<L", 0)
    out += b"\0" * (strip_start - len(out))
    for offset, data in blobs:
        out[offset : offset + len(data)] = data
    path.write_bytes(bytes(out) + jpeg)
    return path
