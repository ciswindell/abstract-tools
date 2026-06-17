import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aa_tool.ingest import SourcePdf
from aa_tool.model import SegmentationModel
from aa_tool.ui.segmentation_screen import SegmentationScreen


def _model(make_pdf):
    pdf = make_pdf("368495.pdf", 4)
    sources = [SourcePdf(pdf, "368495", "0", 4)]
    return SegmentationModel(sources)


def test_buttons_reflect_selected_page(qtbot, make_pdf):
    model = _model(make_pdf)
    screen = SegmentationScreen(model, on_continue=lambda: None)
    qtbot.addWidget(screen)

    screen.select_page(0)  # first page of source, and global 0
    assert screen.first_button.isEnabled() is False
    assert screen.continuation_button.isEnabled() is False

    screen.select_page(1)  # interior continuation page
    assert screen.first_button.isEnabled() is True
    assert screen.continuation_button.isEnabled() is False

    screen.mark_first_page()  # promote page 1 to a document start
    assert model.is_first_page(1) is True
    assert screen.first_button.isEnabled() is False
    assert screen.continuation_button.isEnabled() is True

    screen.mark_continuation()  # demote it back
    assert model.is_first_page(1) is False
