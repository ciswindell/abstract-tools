# src/abstract_tools/ui/srp_parser/drop_screen.py
"""SRP Parser main screen: two drop zones, a Process button, and inline result."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from abstract_tools.srp import run_srp_merge
from abstract_tools.ui.header import Header
from abstract_tools.ui.srp_parser.drop_zone import FileDropZone

SRP_STEPS = ["1 · Drop files", "2 · Result"]


@dataclass(frozen=True)
class MergeResult:
    ok: bool
    error: str = ""


class MergeWorker(QtCore.QObject):
    """Runs run_srp_merge off the UI thread, relaying success or error."""

    finished = QtCore.Signal(object)  # MergeResult

    def __init__(self, srp_path: Path, worksheet_path: Path):
        super().__init__()
        self._srp_path = srp_path
        self._worksheet_path = worksheet_path

    @QtCore.Slot()
    def run(self) -> None:
        try:
            run_srp_merge(self._srp_path, self._worksheet_path)
            self.finished.emit(MergeResult(ok=True))
        except Exception as exc:  # surfaced inline on the screen
            self.finished.emit(MergeResult(ok=False, error=str(exc)))


class DropScreen(QtWidgets.QWidget):
    def __init__(self, on_back_to_tools: Callable[[], None]):
        super().__init__()
        self.setObjectName("screen")
        self._thread: QtCore.QThread | None = None
        self._worker: MergeWorker | None = None

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.header = Header(
            active_step=1,
            context_html="SRP Parser",
            on_back_to_tools=on_back_to_tools,
            steps=SRP_STEPS,
        )
        outer.addWidget(self.header)

        center = QtWidgets.QVBoxLayout()
        center.setContentsMargins(48, 0, 48, 0)
        center.setSpacing(16)
        center.addStretch()
        outer.addLayout(center, 1)

        title = QtWidgets.QLabel("Add SRP data to an Abstract Worksheet")
        title.setObjectName("h1")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        center.addWidget(title)

        zones = QtWidgets.QHBoxLayout()
        zones.setSpacing(16)
        self.srp_zone = FileDropZone("Drop SRP file here\n(or click to browse)")
        self.worksheet_zone = FileDropZone(
            "Drop Abstract Worksheet here\n(or click to browse)"
        )
        self.srp_zone.selected.connect(self._on_zone_selected)
        self.worksheet_zone.selected.connect(self._on_zone_selected)
        zones.addWidget(self.srp_zone)
        zones.addWidget(self.worksheet_zone)
        center.addLayout(zones)

        center.addSpacing(8)
        self.process_button = QtWidgets.QPushButton("Process  →")
        self.process_button.setObjectName("primary")
        self.process_button.setEnabled(False)
        self.process_button.clicked.connect(self._on_process_clicked)
        center.addWidget(
            self.process_button, alignment=QtCore.Qt.AlignmentFlag.AlignCenter
        )

        self.result_label = QtWidgets.QLabel()
        self.result_label.setObjectName("success")
        self.result_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.result_label.setWordWrap(True)
        self.result_label.setVisible(False)
        center.addSpacing(6)
        center.addWidget(self.result_label)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(10)
        actions.addStretch()
        self.open_file_button = QtWidgets.QPushButton("Open worksheet")
        self.open_file_button.setObjectName("ghost")
        self.open_file_button.clicked.connect(self._open_file)
        self.open_folder_button = QtWidgets.QPushButton("Open folder")
        self.open_folder_button.setObjectName("ghost")
        self.open_folder_button.clicked.connect(self._open_folder)
        self.again_button = QtWidgets.QPushButton("Parse another  →")
        self.again_button.setObjectName("primary")
        self.again_button.clicked.connect(self._reset)
        for b in (self.open_file_button, self.open_folder_button, self.again_button):
            b.setVisible(False)
            actions.addWidget(b)
        actions.addStretch()
        center.addSpacing(4)
        center.addLayout(actions)

        center.addStretch()

    # --- enable logic ---
    @QtCore.Slot(object)
    def _on_zone_selected(self, _path: Path) -> None:
        self.process_button.setEnabled(
            self.srp_zone.path is not None and self.worksheet_zone.path is not None
        )

    # --- synchronous core (tests + worker share the engine call) ---
    def do_merge(self) -> None:
        run_srp_merge(self.srp_zone.path, self.worksheet_zone.path)

    # --- background run ---
    def _on_process_clicked(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            return
        self.process_button.setEnabled(False)
        self.result_label.setVisible(False)

        self._thread = QtCore.QThread(self)
        self._worker = MergeWorker(self.srp_zone.path, self.worksheet_zone.path)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_thread_refs)
        self._thread.start()

    @QtCore.Slot()
    def _clear_thread_refs(self) -> None:
        self._thread = None
        self._worker = None

    @QtCore.Slot(object)
    def _on_finished(self, result: MergeResult) -> None:
        if result.ok:
            self.result_label.setObjectName("success")
            self.result_label.setText("✓ Worksheet updated")
            self.open_file_button.setVisible(True)
            self.open_folder_button.setVisible(True)
            self.again_button.setVisible(True)
        else:
            self.result_label.setObjectName("warn")
            self.result_label.setText(f"Could not process: {result.error}")
            self.process_button.setEnabled(True)
        self.result_label.style().unpolish(self.result_label)
        self.result_label.style().polish(self.result_label)
        self.result_label.setVisible(True)

    # --- result actions ---
    def _open_file(self) -> None:
        path = self.worksheet_zone.path
        if path:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))

    def _open_folder(self) -> None:
        path = self.worksheet_zone.path
        if path:
            QtGui.QDesktopServices.openUrl(
                QtCore.QUrl.fromLocalFile(str(path.parent))
            )

    def _reset(self) -> None:
        for zone in (self.srp_zone, self.worksheet_zone):
            zone.path = None
            zone._name.setText("")
        self.process_button.setEnabled(False)
        for b in (self.open_file_button, self.open_folder_button, self.again_button):
            b.setVisible(False)
        self.result_label.setVisible(False)

    # --- teardown ---
    def shutdown(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()

    def closeEvent(self, event):  # noqa: N802 (Qt override)
        self.shutdown()
        super().closeEvent(event)
