import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from abstract_tools import tools as tools_module
from abstract_tools import version as v
from abstract_tools.ui.home_board import HomeBoard
from abstract_tools.ui.main_window import MainWindow


def test_home_board_shows_version_badge(qtbot):
    board = HomeBoard(tools_module.TOOLS, on_launch=lambda _id: None)
    qtbot.addWidget(board)
    assert board.version_label.objectName() == "versionBadge"
    assert board.version_label.text() == v.display_version()


def test_window_title_includes_version(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert v.display_version() in window.windowTitle()
