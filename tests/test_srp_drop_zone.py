# tests/test_srp_drop_zone.py
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from abstract_tools.ui.srp_parser.drop_zone import FileDropZone


def test_set_path_updates_state_and_emits(qtbot, tmp_path):
    f = tmp_path / "thing.xlsx"
    f.write_text("x")
    zone = FileDropZone("Drop SRP file here")
    qtbot.addWidget(zone)

    received = []
    zone.selected.connect(lambda p: received.append(p))
    zone.set_path(f)

    assert zone.path == f
    assert received == [f]
    # The filename shows somewhere in the zone's labels.
    from PySide6 import QtWidgets
    texts = [lbl.text() for lbl in zone.findChildren(QtWidgets.QLabel)]
    assert any("thing.xlsx" in t for t in texts)


def test_initial_state_has_no_path(qtbot):
    zone = FileDropZone("Drop SRP file here")
    qtbot.addWidget(zone)
    assert zone.path is None
