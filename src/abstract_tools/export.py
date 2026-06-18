from dataclasses import dataclass
from pathlib import Path

from abstract_tools.excel_export import export_excel
from abstract_tools.ingest import IngestResult
from abstract_tools.model import Document
from abstract_tools.pdf_export import export_pdf


@dataclass
class ExportSummary:
    document_count: int
    page_count: int
    source_count: int
    assignments: list[str]
    pdf_path: Path
    xlsx_path: Path


def build_summary(result: IngestResult, documents: list[Document]):
    page_count = sum(s.page_count for s in result.sources)
    assignments = sorted({s.assignment for s in result.sources})
    return (len(documents), page_count, len(result.sources), assignments)


def run_export(
    result: IngestResult, documents: list[Document], out_dir: Path
) -> ExportSummary:
    out_dir = Path(out_dir)
    base = f"{result.lease_number} File Documents"
    pdf_path = out_dir / f"{base}.pdf"
    xlsx_path = out_dir / f"{base}.xlsx"

    export_pdf(result.sources, documents, pdf_path)
    export_excel(documents, xlsx_path)

    doc_count, page_count, source_count, assignments = build_summary(result, documents)
    return ExportSummary(
        document_count=doc_count,
        page_count=page_count,
        source_count=source_count,
        assignments=assignments,
        pdf_path=pdf_path,
        xlsx_path=xlsx_path,
    )
