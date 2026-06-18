from collections.abc import Callable
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from abstract_tools.tiff_convert import (
    PlanSummary,
    RunSummary,
    default_output,
    plan_actions,
    run_conversion,
    summarize_plan,
)
from abstract_tools.ui import theme
from abstract_tools.ui.header import Header

CONVERTER_STEPS = ["1 · Open", "2 · Convert"]


def _format_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{int(size)} B" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


class ConversionWorker(QtCore.QObject):
    """Runs run_conversion off the UI thread, relaying progress and the result."""

    progress = QtCore.Signal(int, int, str)
    finished = QtCore.Signal(object)  # RunSummary

    def __init__(self, source: Path, out_dir: Path, standardize: bool):
        super().__init__()
        self._source = source
        self._out_dir = out_dir
        self._standardize = standardize

    @QtCore.Slot()
    def run(self) -> None:
        summary = run_conversion(
            self._source,
            self._out_dir,
            standardize=self._standardize,
            progress_cb=lambda done, total, label: self.progress.emit(done, total, label),
        )
        self.finished.emit(summary)


class PlanScreen(QtWidgets.QWidget):
    def __init__(
        self,
        source: Path,
        on_back_to_tools: Callable[[], None],
        on_new_folder: Callable[[], None],
    ):
        super().__init__()
        self.setObjectName("screen")
        self.source = source
        self.on_new_folder = on_new_folder
        self.out_dir = default_output(source)
        self.summary: PlanSummary = summarize_plan(
            plan_actions(source, self.out_dir, force=False)
        )
        self._thread: QtCore.QThread | None = None
        self._worker: ConversionWorker | None = None

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.header = Header(
            active_step=2,
            context_html=f'Folder&nbsp;<span style="color:{theme.PINE}">{source.name}</span>',
            on_back_to_tools=on_back_to_tools,
            steps=CONVERTER_STEPS,
        )
        outer.addWidget(self.header)

        center = QtWidgets.QVBoxLayout()
        center.setContentsMargins(48, 0, 48, 0)
        center.setSpacing(16)
        center.addStretch()
        outer.addLayout(center, 1)

        title = QtWidgets.QLabel("Ready to convert")
        title.setObjectName("h1")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        center.addWidget(title)

        self.summary_label = QtWidgets.QLabel(
            f"{self.summary.tiff_count} TIFFs to convert\n"
            f"{self.summary.copy_count} other files to copy\n"
            f"{_format_size(self.summary.total_bytes)} total"
        )
        self.summary_label.setObjectName("sub")
        self.summary_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        center.addWidget(self.summary_label)

        center.addSpacing(10)

        dest = QtWidgets.QHBoxLayout()
        dest.setSpacing(10)
        self.path_label = QtWidgets.QLabel(str(self.out_dir))
        self.path_label.setObjectName("savePath")
        change_button = QtWidgets.QPushButton("Change…")
        change_button.setObjectName("ghost")
        change_button.clicked.connect(self._change_folder)
        dest.addStretch()
        dest.addWidget(QtWidgets.QLabel("Save to:"))
        dest.addWidget(self.path_label)
        dest.addWidget(change_button)
        dest.addStretch()
        center.addLayout(dest)

        self.standardize_checkbox = QtWidgets.QCheckBox(
            "Standardize pages (letter / legal)"
        )
        self.standardize_checkbox.setChecked(True)
        center.addWidget(
            self.standardize_checkbox, alignment=QtCore.Qt.AlignmentFlag.AlignCenter
        )

        center.addSpacing(10)
        self.convert_button = QtWidgets.QPushButton("Convert  →")
        self.convert_button.setObjectName("primary")
        self.convert_button.clicked.connect(self._on_convert_clicked)
        center.addWidget(
            self.convert_button, alignment=QtCore.Qt.AlignmentFlag.AlignCenter
        )

        self.result_label = QtWidgets.QLabel()
        self.result_label.setObjectName("success")
        self.result_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.result_label.setVisible(False)
        center.addSpacing(6)
        center.addWidget(self.result_label)

        self.failures_label = QtWidgets.QLabel()
        self.failures_label.setObjectName("warn")
        self.failures_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.failures_label.setWordWrap(True)
        self.failures_label.setVisible(False)
        center.addWidget(self.failures_label)

        self.new_folder_button = QtWidgets.QPushButton("Convert another folder  →")
        self.new_folder_button.setObjectName("primary")
        self.new_folder_button.clicked.connect(lambda: self.on_new_folder())
        self.new_folder_button.setVisible(False)
        center.addSpacing(4)
        center.addWidget(
            self.new_folder_button, alignment=QtCore.Qt.AlignmentFlag.AlignCenter
        )

        center.addStretch()

    def shutdown(self) -> None:
        """Stop the conversion thread before this screen is destroyed.

        There is no cancel, so this blocks until the in-flight conversion
        finishes — destroying a running QThread crashes Qt.
        """
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()

    def closeEvent(self, event):  # noqa: N802 (Qt override)
        self.shutdown()
        super().closeEvent(event)

    def _change_folder(self) -> None:
        chosen = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Choose output folder", str(self.out_dir)
        )
        if chosen:
            self.out_dir = Path(chosen)
            self.path_label.setText(str(self.out_dir))
            self.summary = summarize_plan(plan_actions(self.source, self.out_dir, force=False))
            self.summary_label.setText(
                f"{self.summary.tiff_count} TIFFs to convert\n"
                f"{self.summary.copy_count} other files to copy\n"
                f"{_format_size(self.summary.total_bytes)} total"
            )

    def do_convert(self) -> RunSummary:
        """Synchronous convert (used by tests and as the worker's core call)."""
        return run_conversion(
            self.source,
            self.out_dir,
            standardize=self.standardize_checkbox.isChecked(),
        )

    @QtCore.Slot()
    def _clear_thread_refs(self) -> None:
        self._thread = None
        self._worker = None

    def _on_convert_clicked(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            return
        self.convert_button.setEnabled(False)
        self.result_label.setVisible(False)
        self.failures_label.setVisible(False)

        self._thread = QtCore.QThread(self)
        self._worker = ConversionWorker(
            self.source, self.out_dir, self.standardize_checkbox.isChecked()
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_thread_refs)
        self._thread.start()

    @QtCore.Slot(int, int, str)
    def _on_progress(self, done: int, total: int, label: str) -> None:
        self.header.set_progress(done, total, f"{done}/{total}  {label}")

    @QtCore.Slot(object)
    def _on_finished(self, summary: RunSummary) -> None:
        self.result_label.setText(
            f"✓ {summary.converted} converted · "
            f"{summary.copied} copied · {len(summary.failures)} failed"
        )
        self.result_label.setVisible(True)
        if summary.failures:
            names = ", ".join(src.name for src, _ in summary.failures)
            self.failures_label.setText(f"Failed: {names}")
            self.failures_label.setVisible(True)
        self.new_folder_button.setVisible(True)
        self.convert_button.setEnabled(True)
