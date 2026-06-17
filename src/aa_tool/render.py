from pathlib import Path

import fitz


def render_page_png(path: Path, page_index: int, zoom: float = 1.5) -> bytes:
    with fitz.open(path) as doc:
        page = doc[page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        return pix.tobytes("png")


def page_size(path: Path, page_index: int) -> tuple[float, float]:
    """Return the (width, height) of a page in points (1 point = 1/72 inch).

    Used to compute fit-to-width / fit-to-page zoom factors: a pixmap rendered
    at zoom z is page_width_pt * z pixels wide, so to fit a viewport W px wide,
    zoom = W / page_width_pt.
    """
    with fitz.open(path) as doc:
        rect = doc[page_index].rect
        return (rect.width, rect.height)
