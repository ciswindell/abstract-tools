from pathlib import Path

import fitz

from aa_tool.ingest import scan_lease_folder
from aa_tool.model import SegmentationModel
from aa_tool.pdf_export import export_pdf


def test_export_pdf_merges_and_bookmarks(make_pdf, tmp_path):
    lease = tmp_path / "B11294"
    make_pdf("368481.pdf", 2, parent=lease / "0")
    make_pdf("368495.pdf", 3, parent=lease / "0")

    result = scan_lease_folder(lease)
    model = SegmentationModel(result.sources)
    model.set_first_page(3)  # split second source into two documents
    docs = model.documents()

    out = tmp_path / "B11294 File Documents.pdf"
    export_pdf(result.sources, docs, out)

    with fitz.open(out) as merged:
        assert merged.page_count == 5
        toc = merged.get_toc()
    # [level, title, 1-based page]
    assert toc == [
        [1, "1-Unknown-NA", 1],
        [1, "2-Unknown-NA", 3],
        [1, "3-Unknown-NA", 4],
    ]
