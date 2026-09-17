"""Damaged TIFFs must still convert, completely, and say what was wrong.

The fixtures are built byte-by-byte in `tiff_builders` — no customer scan is
copied into the repository — but they carry the exact damage seen in a real
NMSLO delivery: a tag whose data offset points past the end of the file, and the
old-style JPEG-in-TIFF layout that makes Pillow warn "Truncated File Read".
"""

import warnings

import fitz  # PyMuPDF
import pytest
from PIL import Image

from abstract_tools.tiff_convert import (
    ConversionError,
    convert_one,
    count_pdf_pages,
    count_tiff_pages,
    default_output,
    run_conversion,
    scan_tiff_ifds,
)
from tests.tiff_builders import (
    IMAGE_DESCRIPTION,
    XMP,
    write_cut_tiff,
    write_damaged_tiff,
    write_old_style_jpeg_tiff,
)
from tests.tiff_builders import build_tiff as _build_tiff

WHITE, BLACK, GREY = 255, 0, 128


def _healthy(path, shades=(WHITE, BLACK, GREY)):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_build_tiff(list(shades)))
    return path


def _rendered_shades(pdf_path):
    """Mean brightness of each PDF page's centre, to check page order and content."""
    shades = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=24)
            x, y = pix.width // 2, pix.height // 2
            shades.append(sum(pix.pixel(x, y)[:3]) / 3)
    return shades


def test_scan_finds_the_pages_pillow_loses(tmp_path):
    """The defect itself: Pillow stops at the damaged page; the walk does not."""
    src = write_damaged_tiff(tmp_path / "damaged.tif", [WHITE, BLACK, GREY], damaged_page=0)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with Image.open(src) as img:
            assert img.n_frames == 1  # Pillow alone: two pages are invisible

    assert scan_tiff_ifds(src).pages == 3
    assert count_tiff_pages(src) == 3


def test_damaged_tiff_converts_every_page_in_order(tmp_path):
    src = write_damaged_tiff(tmp_path / "damaged.tif", [WHITE, BLACK, GREY], damaged_page=0)
    dst = tmp_path / "damaged.pdf"

    notes = convert_one(src, dst)

    assert count_pdf_pages(dst) == 3
    white, black, grey = _rendered_shades(dst)
    assert white > 200 and black < 60 and 90 < grey < 170
    assert any("damaged tag on page 1" in n for n in notes)


def test_tiff_pillow_cannot_open_at_all_still_converts(tmp_path):
    """Damage before the tags needed to decode: Pillow refuses the file outright."""
    src = write_damaged_tiff(
        tmp_path / "unopenable.tif", [WHITE, BLACK], damaged_page=0, bad_tag=IMAGE_DESCRIPTION
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with pytest.raises(Exception):  # noqa: B017 — UnidentifiedImageError
            Image.open(src)

    notes = convert_one(src, tmp_path / "unopenable.pdf")

    assert count_pdf_pages(tmp_path / "unopenable.pdf") == 2
    assert notes


def test_page_with_incomplete_scan_data_is_converted_and_named(tmp_path):
    src = write_cut_tiff(tmp_path / "cut.tif", [WHITE, BLACK, GREY], keep_pixel_rows=20)

    notes = convert_one(src, tmp_path / "cut.pdf")

    assert count_pdf_pages(tmp_path / "cut.pdf") == 3
    assert any("incomplete scan data on page 3" in n for n in notes)


def test_old_style_jpeg_tiff_converts_silently(tmp_path):
    """The delivery's own layout: no warning, no repair note, pixels intact."""
    src = write_old_style_jpeg_tiff(tmp_path / "scan.tif", size=(300, 400))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        notes = convert_one(src, tmp_path / "scan.pdf")

    assert [str(w.message) for w in caught] == []
    assert notes == []
    assert count_pdf_pages(tmp_path / "scan.pdf") == 1


def test_old_style_jpeg_tiff_keeps_its_exif(tmp_path):
    """Proof the descriptor stays in sync: Pillow reads the tags back, not garbage.

    A file's Orientation lives in that EXIF; when this parse fails, a page that
    should be rotated is written upright instead.
    """
    from abstract_tools.tiff_convert import _TiffReader

    src = write_old_style_jpeg_tiff(tmp_path / "scan.tif", size=(300, 400), orientation=6)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        reader = _TiffReader(src)
        try:
            with Image.open(reader) as img:
                img.load()
                exif = dict(img.getexif())
        finally:
            reader.close()

    assert [str(w.message) for w in caught] == []
    assert exif  # empty when Pillow misparses image data as a tag directory


def test_healthy_tiff_reports_nothing(tmp_path):
    src = _healthy(tmp_path / "fine.tif")

    assert convert_one(src, tmp_path / "fine.pdf") == []
    assert count_pdf_pages(tmp_path / "fine.pdf") == 3


def test_run_conversion_lists_damaged_files_as_repaired(tmp_path):
    src_root = tmp_path / "lease"
    _healthy(src_root / "fine.tif")
    write_damaged_tiff(src_root / "damaged.tif", [WHITE, BLACK, GREY], damaged_page=0, bad_tag=XMP)
    out = default_output(src_root)

    summary = run_conversion(src_root, out, standardize=False)

    assert summary.converted == 2
    assert summary.failures == []
    assert [p.name for p, _ in summary.repaired] == ["damaged.tif"]
    assert "damaged tag" in summary.repaired[0][1]
    assert count_pdf_pages(out / "damaged.pdf") == 3


def test_unreadable_file_still_fails_loudly(tmp_path):
    src_root = tmp_path / "lease"
    src_root.mkdir()
    (src_root / "junk.tif").write_bytes(b"not a tiff at all")
    out = default_output(src_root)

    summary = run_conversion(src_root, out)

    assert summary.converted == 0
    assert [p.name for p, _ in summary.failures] == ["junk.tif"]
    assert summary.repaired == []


def test_scan_rejects_a_file_that_is_not_a_tiff(tmp_path):
    path = tmp_path / "junk.tif"
    path.write_bytes(b"XX\x2a\x00\x08\x00\x00\x00")

    with pytest.raises(ConversionError):
        scan_tiff_ifds(path)


def test_scan_walks_a_bigtiff_chain(tmp_path):
    from tests.tiff_builders import write_bigtiff

    src = write_bigtiff(tmp_path / "big.tif", pages=3)

    assert scan_tiff_ifds(src).pages == 3


def test_scan_stops_on_a_chain_that_points_back_at_itself(tmp_path):
    """A corrupt next-page pointer must not spin forever."""
    import struct

    data = bytearray(_build_tiff([WHITE, BLACK]))
    entries = struct.unpack_from("<H", data, 8)[0]
    struct.pack_into("<L", data, 8 + 2 + entries * 12, 8)  # page 1 -> itself
    src = tmp_path / "loop.tif"
    src.write_bytes(bytes(data))

    assert scan_tiff_ifds(src).pages == 1
