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


def _long_lease(make_pdf):
    """Two source PDFs, so page 2 is a source start the user will press C on."""
    from pathlib import Path

    a = make_pdf("407751.pdf", 2)
    b = make_pdf("407765.pdf", 3)
    return SegmentationModel([
        SourcePdf(a, "407751", "0", 2),
        SourcePdf(b, "407765", "0", 3),
    ])


def test_continuation_on_a_source_start_explains_itself_inline(qtbot, make_pdf):
    """Pressing C where it cannot apply must say why — without a modal dialog."""
    from PySide6 import QtWidgets

    screen = _screen(_long_lease(make_pdf))
    qtbot.addWidget(screen)
    screen.select_page(2)  # first page of the second source PDF

    screen.mark_continuation()

    assert screen.hint_label.isVisibleTo(screen)
    assert "407765" in screen.hint_label.text()
    assert screen.findChildren(QtWidgets.QMessageBox) == []


def test_holding_continuation_does_not_stack_dialogs(qtbot, make_pdf):
    """Key auto-repeat used to open one modal box per press, all at once."""
    from PySide6 import QtWidgets

    screen = _screen(_long_lease(make_pdf))
    qtbot.addWidget(screen)
    screen.select_page(2)

    for _ in range(20):
        screen.mark_continuation()

    assert screen.findChildren(QtWidgets.QMessageBox) == []
    assert screen.hint_label.isVisibleTo(screen)


def test_hint_clears_when_the_page_changes(qtbot, make_pdf):
    screen = _screen(_long_lease(make_pdf))
    qtbot.addWidget(screen)
    screen.select_page(2)
    screen.mark_continuation()

    screen.select_page(3)

    assert not screen.hint_label.isVisibleTo(screen)

