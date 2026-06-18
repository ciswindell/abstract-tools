from collections.abc import Callable
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from abstract_tools import tools as tools_module
from abstract_tools import update_check
from abstract_tools import version as app_version
from abstract_tools.ui import theme
from abstract_tools.ui.home_board import HomeBoard
from abstract_tools.ui.update_banner import UpdateBanner
from abstract_tools.update_check import UpdateInfo


class _CheckWorker(QtCore.QObject):
    found = QtCore.Signal(object)  # UpdateInfo
    done = QtCore.Signal()

    def __init__(self, checker: Callable[[], UpdateInfo | None]):
        super().__init__()
        self._checker = checker

    @QtCore.Slot()
    def run(self) -> None:
        info = self._checker()
        if info is not None:
            self.found.emit(info)
        self.done.emit()


class _DownloadWorker(QtCore.QObject):
    done = QtCore.Signal(object)  # Path
    failed = QtCore.Signal()

    def __init__(self, downloader: Callable[[UpdateInfo], Path], info: UpdateInfo):
        super().__init__()
        self._downloader = downloader
        self._info = info

    @QtCore.Slot()
    def run(self) -> None:
        try:
            saved = self._downloader(self._info)
            self.done.emit(saved)
        except Exception:
            self.failed.emit()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(
        self,
        update_checker: Callable[[], UpdateInfo | None] | None = None,
        downloader: Callable[[UpdateInfo], Path] | None = None,
    ):
        super().__init__()
        self.setWindowTitle(f"Abstract Tools {app_version.display_version()}")
        self.resize(1200, 820)

        self._update_checker = update_checker or update_check.check_for_update
        self._downloader = downloader or self._real_download

        self.stack = QtWidgets.QStackedWidget()
        self.banner = UpdateBanner()
        self.banner.download_requested.connect(self._on_download_requested)

        container = QtWidgets.QWidget()
        col = QtWidgets.QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self.banner)
        col.addWidget(self.stack, 1)
        self.setCentralWidget(container)

        self._tools = {t.id: t for t in tools_module.TOOLS}
        self.board = HomeBoard(tools_module.TOOLS, on_launch=self.launch_tool)
        self.stack.addWidget(self.board)
        self._current_tool = None

        self._check_thread: QtCore.QThread | None = None
        self._check_worker: _CheckWorker | None = None
        self._download_thread: QtCore.QThread | None = None
        self._download_worker: _DownloadWorker | None = None

    # --- update check -------------------------------------------------
    def start_update_check(self) -> None:
        thread = QtCore.QThread(self)
        worker = _CheckWorker(self._update_checker)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.found.connect(self._on_update_found)
        # Clear the Python refs before thread.quit so we never hold a stale
        # wrapper once deleteLater fires; done fires from the worker thread
        # and is delivered to the main thread via the queued connection.
        worker.done.connect(self._clear_check_thread)
        worker.done.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._check_thread = thread
        self._check_worker = worker
        thread.start()

    @QtCore.Slot()
    def _clear_check_thread(self) -> None:
        self._check_thread = None
        self._check_worker = None

    @QtCore.Slot(object)
    def _on_update_found(self, info: UpdateInfo) -> None:
        self.banner.show_update(info)

    def _on_download_requested(self, info: UpdateInfo) -> None:
        self.banner.download_button.setEnabled(False)
        self.banner.set_status(f"Downloading version {info.latest_version}…")
        thread = QtCore.QThread(self)
        worker = _DownloadWorker(self._downloader, info)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.done.connect(self._on_download_done)
        worker.failed.connect(self._on_download_failed)
        # Clear the Python refs before thread.quit (same stale-wrapper guard).
        worker.done.connect(self._clear_download_thread)
        worker.failed.connect(self._clear_download_thread)
        worker.done.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._download_thread = thread
        self._download_worker = worker
        thread.start()

    @QtCore.Slot()
    def _clear_download_thread(self) -> None:
        self._download_thread = None
        self._download_worker = None

    @QtCore.Slot(object)
    def _on_download_done(self, saved: Path) -> None:
        self.banner.set_status(
            "Saved to your Downloads folder — close this app and open the new file."
        )

    @QtCore.Slot()
    def _on_download_failed(self) -> None:
        self.banner.download_button.setEnabled(True)
        self.banner.set_status("Download failed — please try again or contact Chris.")

    def _real_download(self, info: UpdateInfo) -> Path:
        return update_check.download_release(
            info.download_url,
            update_check.downloads_dir(),
            f"Abstract Tools {info.latest_version}.exe",
        )

    # --- window lifecycle ---------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Wait for any in-flight background threads before closing.

        Destroying a running QThread crashes Qt, so we quit+wait.
        The _clear_*_thread slots zero out the refs when threads finish
        naturally, so by the time closeEvent fires the refs are either
        None (thread already done) or a live QThread that needs waiting.
        No try/except gymnastics needed — the stale-wrapper race is
        eliminated by clearing the ref in finished-connected slots.
        """
        for thread in (self._check_thread, self._download_thread):
            if thread is not None and thread.isRunning():
                thread.quit()
                thread.wait()
        super().closeEvent(event)

    # --- tool switching (unchanged behaviour) -------------------------
    def launch_tool(self, tool_id: str) -> None:
        tool = self._tools[tool_id]
        widget = tool.build(self.show_board)
        if self._current_tool is not None:
            self.stack.removeWidget(self._current_tool)
            if hasattr(self._current_tool, "shutdown"):
                self._current_tool.shutdown()
            self._current_tool.deleteLater()
        self._current_tool = widget
        self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)

    def show_board(self) -> None:
        self.stack.setCurrentWidget(self.board)
        if self._current_tool is not None:
            self.stack.removeWidget(self._current_tool)
            if hasattr(self._current_tool, "shutdown"):
                self._current_tool.shutdown()
            self._current_tool.deleteLater()
            self._current_tool = None


def main() -> None:
    import sys

    app = QtWidgets.QApplication(sys.argv)
    theme.apply_theme(app)
    window = MainWindow()
    window.show()
    window.start_update_check()
    sys.exit(app.exec())
