import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aa_tool.ui.icons import svg_pixmap


def test_svg_pixmap_renders_square_non_null(qtbot):
    pm = svg_pixmap("icons/segmentor.svg", 48)
    assert not pm.isNull()
    assert pm.width() == 48
    assert pm.height() == 48


def test_tiff_converter_icon_renders(qtbot):
    pm = svg_pixmap("icons/tiff_converter.svg", 48)
    assert not pm.isNull()
    assert pm.width() == 48
