import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aa_tool.tools import Tool
from aa_tool.ui.home_board import HomeBoard


def _tool(id, category):
    return Tool(id=id, name=id.title(), description="desc", category=category,
                icon="icons/segmentor.svg", build=lambda cb: None)


def test_board_renders_card_per_tool_and_launches(qtbot):
    launched = []
    tools = [_tool("nmslo_segmentor", "NM State Land Office")]
    board = HomeBoard(tools, on_launch=launched.append)
    qtbot.addWidget(board)

    assert set(board.cards.keys()) == {"nmslo_segmentor"}

    # Clicking the card launches by tool id.
    board.cards["nmslo_segmentor"].mousePressEvent(None)
    assert launched == ["nmslo_segmentor"]
