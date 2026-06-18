# src/abstract_tools/ui/srp_parser/drop_zone.py
"""A labeled drag-and-drop target for a single .xlsx file (also click-to-browse)."""

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets


def _xlsx_path(url: QtCore.QUrl) -> Path | None:
    if not url.isLocalFile():
        return None
    path = Path(url.toLocalFile())
    return path if path.suffix.lower() == ".xlsx" else None


class FileDropZone(QtWidgets.QFrame):
    """Drop one .xlsx here, or click to browse. Emits `selected` with the Path."""

    selected = QtCore.Signal(object)  # Path

    def __init__(self, label: str):
        super().__init__()
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.path: Path | None = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(6)
        layout.addStretch()

        self._title = QtWidgets.QLabel(label)
        self._title.setObjectName("dropZoneTitle")
        self._title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title)

        self._name = QtWidgets.QLabel("")
        self._name.setObjectName("dropZoneName")
        self._name.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._name.setWordWrap(True)
        layout.addWidget(self._name)

        layout.addStretch()

    def set_path(self, path: Path) -> None:
        self.path = path
        self._name.setText(path.name)
        self.selected.emit(path)

    def _set_active(self, active: bool) -> None:
        self.setObjectName("dropZoneActive" if active else "dropZone")
        self.style().unpolish(self)
        self.style().polish(self)

    # --- drag and drop ---
    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        if len(urls) == 1 and _xlsx_path(urls[0]) is not None:
            self._set_active(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        self._set_active(False)

    def dropEvent(self, event: QtGui.QDropEvent) -> None:  # noqa: N802
        self._set_active(False)
        path = _xlsx_path(event.mimeData().urls()[0])
        if path is not None:
            self.set_path(path)
            event.acceptProposedAction()

    # --- click to browse ---
    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        start = str(self.path.parent) if self.path else str(Path.home())
        chosen, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Choose .xlsx file", start, "Excel files (*.xlsx)"
        )
        if chosen:
            self.set_path(Path(chosen))
