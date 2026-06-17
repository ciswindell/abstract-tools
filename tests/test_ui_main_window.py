import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aa_tool.ui.main_window import MainWindow


def test_load_lease_builds_model(qtbot, make_pdf, tmp_path):
    lease = tmp_path / "B11294"
    make_pdf("368481.pdf", 2, parent=lease / "0")

    window = MainWindow()
    qtbot.addWidget(window)
    window.load_lease(lease)

    assert window.ingest_result.lease_number == "B11294"
    assert len(window.model.pages) == 2
