import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from abstract_tools.ingest import SourcePdf
from abstract_tools.model import SegmentationModel
from abstract_tools.ui.nmslo_segmentor.segmentation_screen import SegmentationScreen


def _model(make_pdf):
    pdf = make_pdf("368495.pdf", 4)
    sources = [SourcePdf(pdf, "368495", "0", 4)]
    return SegmentationModel(sources)


def _screen(model):
    return SegmentationScreen(model, "B11294", on_continue=lambda: None,
                              on_back_to_tools=lambda: None)


def test_classify_buttons_show_current_state_by_color(qtbot, make_pdf):
    model = _model(make_pdf)
    screen = _screen(model)
    qtbot.addWidget(screen)

    # Page 0 is the very first page: a first page, and continuation is disabled.
    screen.select_page(0)
    assert screen.first_button.property("active") == "true"
    assert screen.continuation_button.property("active") == "false"
    assert screen.continuation_button.isEnabled() is False

    # An interior page is pre-seeded as a continuation: yellow active, first inactive.
    screen.select_page(1)
    assert screen.first_button.property("active") == "false"
    assert screen.continuation_button.property("active") == "true"
    assert screen.continuation_button.isEnabled() is True


def test_mark_first_page_auto_advances(qtbot, make_pdf):
    model = _model(make_pdf)
    screen = _screen(model)
    qtbot.addWidget(screen)

    screen.select_page(1)
    screen.mark_first_page()  # promote page 1 to a document start

    assert model.is_first_page(1) is True
    # Auto-advance moved selection to the next page (never skips pages).
    assert screen.selected_index == 2


def test_mark_continuation_auto_advances_and_demotes(qtbot, make_pdf):
    model = _model(make_pdf)
    screen = _screen(model)
    qtbot.addWidget(screen)

    screen.select_page(1)
    screen.mark_first_page()  # page 1 -> first; selection now on page 2
    screen.select_page(1)
    screen.mark_continuation()  # demote page 1 back to continuation

    assert model.is_first_page(1) is False
    assert screen.selected_index == 2  # auto-advanced again


def test_first_page_cannot_be_made_continuation(qtbot, make_pdf):
    model = _model(make_pdf)
    screen = _screen(model)
    qtbot.addWidget(screen)

    screen.select_page(0)
    screen.mark_continuation()  # must be a no-op on the very first page

    assert model.is_first_page(0) is True
    assert screen.selected_index == 0  # no advance happened
