import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aa_tool.ui.header import Header


def test_back_to_tools_link_invokes_callback(qtbot):
    called = []
    header = Header(active_step=2, context_html="NMSLO Segmentor",
                    on_back_to_tools=lambda: called.append(True))
    qtbot.addWidget(header)
    header.back_button.click()
    assert called == [True]


def test_no_back_link_without_callback(qtbot):
    header = Header(active_step=1)
    qtbot.addWidget(header)
    assert header.back_button is None


def test_custom_steps_render(qtbot):
    from PySide6 import QtWidgets

    header = Header(active_step=2, steps=["1 · Open", "2 · Convert"])
    qtbot.addWidget(header)
    labels = [w.text() for w in header.findChildren(QtWidgets.QLabel)]
    assert "2 · Convert" in labels
    assert "3 · Export" not in labels
