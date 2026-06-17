from pathlib import Path

import fitz


def render_page_png(path: Path, page_index: int, zoom: float = 1.5) -> bytes:
    with fitz.open(path) as doc:
        page = doc[page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        return pix.tobytes("png")
