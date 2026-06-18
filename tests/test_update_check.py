import json

from abstract_tools import update_check as uc


def _release_json(tag="1.3.0", asset_name="Abstract Tools.exe"):
    return json.dumps(
        {
            "tag_name": tag,
            "body": "Fixed the thing.",
            "assets": [
                {"name": asset_name,
                 "browser_download_url": f"https://example.test/{asset_name}"}
            ],
        }
    )


def test_returns_updateinfo_when_remote_is_newer():
    info = uc.check_for_update("1.2.0", http_get=lambda url: _release_json("1.3.0"))
    assert info is not None
    assert info.latest_version == "1.3.0"
    assert info.download_url == "https://example.test/Abstract Tools.exe"
    assert info.release_notes == "Fixed the thing."


def test_returns_none_when_up_to_date():
    assert uc.check_for_update("1.3.0", http_get=lambda url: _release_json("1.3.0")) is None


def test_returns_none_when_no_exe_asset():
    body = _release_json("9.9.9", asset_name="notes.txt")
    assert uc.check_for_update("1.0.0", http_get=lambda url: body) is None


def test_dev_build_skips_check():
    called = False

    def spy(url):
        nonlocal called
        called = True
        return _release_json("9.9.9")

    assert uc.check_for_update("0.0.0+dev", http_get=spy) is None
    assert called is False


def test_network_or_parse_errors_return_none():
    def boom(url):
        raise OSError("offline")

    assert uc.check_for_update("1.0.0", http_get=boom) is None
    assert uc.check_for_update("1.0.0", http_get=lambda url: "not json") is None
