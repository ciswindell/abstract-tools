import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aa_tool.ui.main_window import MainWindow


def test_starts_on_board_then_launches_and_returns(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    # Starts on the board.
    assert window.stack.currentWidget() is window.board

    window.launch_tool("nmslo_segmentor")
    assert window.stack.currentWidget() is window._current_tool

    window.show_board()
    assert window.stack.currentWidget() is window.board
