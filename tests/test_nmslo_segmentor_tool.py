import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aa_tool.ui.nmslo_segmentor.tool import NmsloSegmentorTool


def test_load_lease_builds_model(qtbot, make_pdf, tmp_path):
    lease = tmp_path / "B11294"
    make_pdf("368481.pdf", 2, parent=lease / "0")

    tool = NmsloSegmentorTool(on_back_to_tools=lambda: None)
    qtbot.addWidget(tool)
    tool.load_lease(lease)

    assert tool.ingest_result.lease_number == "B11294"
    assert len(tool.model.pages) == 2


def test_back_to_tools_callback_wired(qtbot, make_pdf, tmp_path):
    called = []
    from PySide6 import QtWidgets

    tool = NmsloSegmentorTool(on_back_to_tools=lambda: called.append(True))
    qtbot.addWidget(tool)
    # The open screen's header has the Back-to-Tools button; clicking it fires the callback.
    back_buttons = [b for b in tool.findChildren(QtWidgets.QPushButton)
                    if b.objectName() == "backToTools"]
    assert back_buttons
    back_buttons[0].click()
    assert called == [True]
