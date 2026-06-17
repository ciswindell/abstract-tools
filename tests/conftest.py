from pathlib import Path

import fitz  # PyMuPDF
import pytest


@pytest.fixture
def make_pdf(tmp_path):
    """Factory that writes a synthetic multi-page PDF and returns its path."""

    def _make(name: str, pages: int, parent: Path | None = None) -> Path:
        folder = parent if parent is not None else tmp_path
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / name
        doc = fitz.open()
        for i in range(pages):
            page = doc.new_page()
            page.insert_text((72, 72), f"{path.stem} page {i + 1}")
        doc.save(path)
        doc.close()
        return path

    return _make
