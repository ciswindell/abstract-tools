from abstract_tools.ingest import scan_lease_folder
from abstract_tools.model import SegmentationModel
from abstract_tools.export import run_export


def test_run_export_writes_named_files_and_summary(make_pdf, tmp_path):
    lease = tmp_path / "B11294"
    make_pdf("368481.pdf", 1, parent=lease / "0")
    make_pdf("368495.pdf", 3, parent=lease / "0")
    make_pdf("368521.pdf", 1, parent=lease / "1")

    result = scan_lease_folder(lease)
    model = SegmentationModel(result.sources)
    docs = model.documents()

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    summary = run_export(result, docs, out_dir)

    assert (out_dir / "B11294 File Documents.pdf").exists()
    assert (out_dir / "B11294 File Documents.xlsx").exists()
    assert summary.document_count == 3
    assert summary.page_count == 5
    assert summary.source_count == 3
    assert summary.assignments == ["0", "1"]
