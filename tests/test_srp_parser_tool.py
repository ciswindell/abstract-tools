# tests/test_srp_parser_tool.py
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

from abstract_tools.ui.srp_parser.tool import SrpParserTool


def test_tool_builds_with_two_drop_zones(qtbot):
    tool = SrpParserTool(on_back_to_tools=lambda: None)
    qtbot.addWidget(tool)
    from abstract_tools.ui.srp_parser.drop_zone import FileDropZone
    assert len(tool.findChildren(FileDropZone)) == 2


def test_back_to_tools_callback_wired(qtbot):
    called = []
    tool = SrpParserTool(on_back_to_tools=lambda: called.append(True))
    qtbot.addWidget(tool)
    back = [b for b in tool.findChildren(QtWidgets.QPushButton)
            if b.objectName() == "backToTools"]
    assert back
    back[0].click()
    assert called == [True]


def test_shutdown_is_safe(qtbot):
    tool = SrpParserTool(on_back_to_tools=lambda: None)
    qtbot.addWidget(tool)
    tool.shutdown()  # nothing running — must not raise
