"""The page rail has to follow the page being classified.

With a long lease the user works far past the pages the rail shows at rest, so
the rail must scroll to keep the current page in view — otherwise there is no
way to tell which page is on screen.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore

from abstract_tools.ingest import SourcePdf
from abstract_tools.model import SegmentationModel
from abstract_tools.ui.nmslo_segmentor.segmentation_screen import SegmentationScreen

PAGES = 60


def _screen(qtbot, make_pdf, pages: int = PAGES):
    pdf = make_pdf("407751.pdf", pages)
    model = SegmentationModel([SourcePdf(pdf, "407751", "0", pages)])
    screen = SegmentationScreen(
        model, "K03153", on_continue=lambda: None, on_back_to_tools=lambda: None
    )
    qtbot.addWidget(screen)
    screen.resize(1200, 800)
    screen.show()
    qtbot.waitExposed(screen)
    return screen


def _current_row_is_in_view(screen) -> bool:
    row = screen._page_rows[screen.selected_index]
    top = row.mapTo(screen._rail_inner, QtCore.QPoint(0, 0)).y()
    bar = screen._rail_scroll.verticalScrollBar()
    view_top = bar.value()
    view_bottom = view_top + screen._rail_scroll.viewport().height()
    return view_top <= top and top + row.height() <= view_bottom


def test_rail_follows_the_page_being_classified(qtbot, make_pdf):
    """Classifying past the visible rows must scroll the rail, not leave it at page 1."""
    screen = _screen(qtbot, make_pdf)

    screen.mark_first_page()  # page 1 is a source start, so F; lands on page 2
    for _ in range(30):
        screen.mark_continuation()

    assert screen.selected_index == 31
    assert _current_row_is_in_view(screen)
    assert screen._rail_scroll.verticalScrollBar().value() > 0


def test_rail_follows_a_jump_to_a_far_page(qtbot, make_pdf):
    screen = _screen(qtbot, make_pdf)

    screen.select_page(PAGES - 1)

    assert _current_row_is_in_view(screen)


def test_rail_scrolls_back_when_moving_to_an_earlier_page(qtbot, make_pdf):
    screen = _screen(qtbot, make_pdf)
    screen.select_page(PAGES - 1)

    screen.select_page(0)

    assert _current_row_is_in_view(screen)
    assert screen._rail_scroll.verticalScrollBar().value() == 0


def test_classifying_keeps_the_rail_rows_alive(qtbot, make_pdf):
    """The rows must survive classification — rebuilding them is what broke the
    scroll: fresh widgets have no geometry yet, so the scroll lands nowhere."""
    screen = _screen(qtbot, make_pdf)
    before = screen._page_rows[10]

    screen.mark_first_page()
    screen.mark_continuation()

    assert screen._page_rows[10] is before


def test_classifying_still_updates_the_dots(qtbot, make_pdf):
    screen = _screen(qtbot, make_pdf)
    screen.select_page(5)

    screen.mark_first_page()
    assert screen._page_rows[5].dot.objectName() == "dotFirst"

    screen.select_page(5)
    screen.mark_continuation()
    assert screen._page_rows[5].dot.objectName() == "dotCont"
