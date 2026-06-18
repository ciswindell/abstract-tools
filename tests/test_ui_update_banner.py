# tests/test_ui_update_banner.py
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from abstract_tools.ui.update_banner import UpdateBanner
from abstract_tools.update_check import UpdateInfo


def _info():
    return UpdateInfo("1.3.0", "https://example.test/app.exe", "notes")


def test_show_update_sets_text_and_visibility(qtbot):
    banner = UpdateBanner()
    qtbot.addWidget(banner)
    banner.show()
    banner.show_update(_info())
    assert banner.isVisibleTo(banner.parent()) or banner.isVisible()
    assert "1.3.0" in banner.text_label.text()
    assert banner.info == _info()


def test_download_button_emits_info(qtbot):
    banner = UpdateBanner()
    qtbot.addWidget(banner)
    banner.show_update(_info())
    with qtbot.waitSignal(banner.download_requested, timeout=1000) as blocker:
        banner.download_button.click()
    assert blocker.args[0] == _info()


def test_dismiss_hides_and_emits(qtbot):
    banner = UpdateBanner()
    qtbot.addWidget(banner)
    banner.show_update(_info())
    with qtbot.waitSignal(banner.dismissed, timeout=1000):
        banner.close_button.click()
    assert banner.isHidden()
