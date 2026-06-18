import os
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from abstract_tools.ui.main_window import MainWindow
from abstract_tools.update_check import UpdateInfo


def test_starts_on_board_then_launches_and_returns(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    # Starts on the board.
    assert window.stack.currentWidget() is window.board

    window.launch_tool("nmslo_segmentor")
    assert window.stack.currentWidget() is window._current_tool

    window.show_board()
    assert window.stack.currentWidget() is window.board


def test_banner_appears_when_update_found(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.banner.isHidden()
    window._on_update_found(UpdateInfo("1.3.0", "https://example.test/app.exe", "n"))
    assert not window.banner.isHidden()
    assert "1.3.0" in window.banner.text_label.text()


def test_download_request_uses_injected_downloader(tmp_path, qtbot):
    saved = tmp_path / "Abstract Tools 1.3.0.exe"
    saved.write_bytes(b"x")

    def fake_downloader(info):
        return saved

    window = MainWindow(downloader=fake_downloader)
    qtbot.addWidget(window)
    info = UpdateInfo("1.3.0", "https://example.test/app.exe", "n")
    window._on_update_found(info)
    window._on_download_requested(info)
    qtbot.waitUntil(lambda: "Downloads" in window.banner.text_label.text(), timeout=3000)
    assert "Downloads" in window.banner.text_label.text()


def test_download_failure_re_enables_button(qtbot):
    def bad_downloader(info):
        raise RuntimeError("boom")

    window = MainWindow(downloader=bad_downloader)
    qtbot.addWidget(window)
    info = UpdateInfo("1.3.0", "https://example.test/app.exe", "n")
    window._on_update_found(info)
    window._on_download_requested(info)
    qtbot.waitUntil(lambda: window.banner.download_button.isEnabled(), timeout=3000)
    assert "failed" in window.banner.text_label.text().lower()


def test_close_while_check_thread_running_does_not_crash(qtbot):
    """closeEvent must quit+wait any in-flight check thread without raising."""
    gate = threading.Event()

    def blocking_checker():
        gate.wait()  # holds the thread open until we release it
        return None

    window = MainWindow(update_checker=blocking_checker)
    qtbot.addWidget(window)
    window.start_update_check()

    # Wait until the thread has actually started running.
    qtbot.waitUntil(
        lambda: window._check_thread is not None and window._check_thread.isRunning(),
        timeout=3000,
    )

    # Release the checker so wait() returns promptly, then close.
    gate.set()
    window.close()  # must not raise

    # The thread has been joined (wait() returned); it is no longer running.
    # The Python ref may still be non-None until the queued clear slot fires,
    # so we only assert the thread is not running rather than None.
    if window._check_thread is not None:
        assert not window._check_thread.isRunning()


def test_close_after_check_thread_finished_does_not_crash(qtbot):
    """closeEvent must not raise when the thread already finished and was deleteLater'd."""

    def instant_checker():
        return None  # returns immediately; thread finishes on its own

    window = MainWindow(update_checker=instant_checker)
    qtbot.addWidget(window)
    window.start_update_check()

    # Wait until the _clear_check_thread slot has zeroed the ref
    # (means finished fired and deleteLater was scheduled).
    qtbot.waitUntil(lambda: window._check_thread is None, timeout=3000)

    # Closing now exercises the "already finished" path — must not raise.
    window.close()
