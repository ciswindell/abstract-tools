from pathlib import Path

import fitz

from aa_tool.ingest import SourcePdf
from aa_tool.labels import build_bookmark_label
from aa_tool.model import Document


def export_pdf(
    sources: list[SourcePdf], documents: list[Document], out_path: Path
) -> None:
    merged = fitz.open()
    try:
        for source in sources:
            with fitz.open(source.path) as src:
                merged.insert_pdf(src)

        toc = [
            [1, build_bookmark_label(doc.index), doc.first_global_index + 1]
            for doc in documents
        ]
        merged.set_toc(toc)
        merged.save(str(out_path))
    finally:
        merged.close()
