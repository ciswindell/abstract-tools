import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PIL import Image
from PySide6 import QtWidgets

from aa_tool.ui.tiff_converter.tool import TiffConverterTool


def _make_tiff(path: Path, pages: int = 1) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = [Image.new("RGB", (120, 160), "white") for _ in range(pages)]
    frames[0].save(path, save_all=True, append_images=frames[1:])
    return path


def test_open_screen_has_choose_button(qtbot):
    tool = TiffConverterTool(on_back_to_tools=lambda: None)
    qtbot.addWidget(tool)
    buttons = [b.text() for b in tool.findChildren(QtWidgets.QPushButton)]
    assert any("Choose" in t for t in buttons)


def test_back_to_tools_callback_wired(qtbot):
    called = []
    tool = TiffConverterTool(on_back_to_tools=lambda: called.append(True))
    qtbot.addWidget(tool)
    back = [b for b in tool.findChildren(QtWidgets.QPushButton)
            if b.objectName() == "backToTools"]
    assert back
    back[0].click()
    assert called == [True]


def test_load_folder_shows_plan_counts(qtbot, tmp_path):
    src = tmp_path / "scans"
    _make_tiff(src / "a.tif")
    _make_tiff(src / "b.tif")
    (src / "notes.txt").write_text("hi")

    tool = TiffConverterTool(on_back_to_tools=lambda: None)
    qtbot.addWidget(tool)
    tool.load_folder(src)

    assert tool.plan_screen is not None
    assert tool.plan_screen.summary.tiff_count == 2
    assert tool.plan_screen.summary.copy_count == 1


def test_do_convert_writes_pdfs(qtbot, tmp_path):
    src = tmp_path / "scans"
    _make_tiff(src / "a.tif", pages=2)

    tool = TiffConverterTool(on_back_to_tools=lambda: None)
    qtbot.addWidget(tool)
    tool.load_folder(src)
    result = tool.plan_screen.do_convert()

    assert result.converted == 1
    assert (tool.plan_screen.out_dir / "a.pdf").exists()
