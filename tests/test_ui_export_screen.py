import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aa_tool.ingest import scan_lease_folder
from aa_tool.model import SegmentationModel
from aa_tool.ui.export_screen import ExportScreen


def test_export_screen_summary_and_export(qtbot, make_pdf, tmp_path):
    lease = tmp_path / "B11294"
    make_pdf("368481.pdf", 1, parent=lease / "0")
    make_pdf("368495.pdf", 3, parent=lease / "0")

    result = scan_lease_folder(lease)
    model = SegmentationModel(result.sources)

    screen = ExportScreen(result, model, on_back=lambda: None)
    qtbot.addWidget(screen)
    assert "2 documents" in screen.summary_label.text()

    screen.out_dir = tmp_path / "out"
    (tmp_path / "out").mkdir()
    summary = screen.do_export()

    assert summary.pdf_path.exists()
    assert summary.xlsx_path.exists()
    assert summary.pdf_path.name == "B11294 File Documents.pdf"
