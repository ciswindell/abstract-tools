from PySide6 import QtCore, QtGui, QtSvg

from abstract_tools.resources import resource_path


def svg_pixmap(name: str, size: int) -> QtGui.QPixmap:
    """Render a bundled SVG resource to a transparent square pixmap."""
    renderer = QtSvg.QSvgRenderer(str(resource_path(name)))
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    renderer.render(painter)
    painter.end()
    return QtGui.QPixmap.fromImage(image)
