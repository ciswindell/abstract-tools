import os

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
