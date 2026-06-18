import pytest

from abstract_tools import update_check as uc


def test_download_writes_file_atomically(tmp_path):
    dest = uc.download_release(
        "https://example.test/app.exe",
        tmp_path,
        "Abstract Tools 1.3.0.exe",
        get_bytes=lambda url: b"PE\x00\x00fake-exe",
    )
    assert dest == tmp_path / "Abstract Tools 1.3.0.exe"
    assert dest.read_bytes() == b"PE\x00\x00fake-exe"
    # no leftover temp file
    assert list(tmp_path.glob("*.part")) == []


def test_download_cleans_up_and_raises_on_failure(tmp_path):
    def boom(url):
        raise OSError("connection reset")

    with pytest.raises(OSError):
        uc.download_release("https://example.test/app.exe", tmp_path,
                            "Abstract Tools 1.3.0.exe", get_bytes=boom)
    assert list(tmp_path.iterdir()) == []  # nothing left behind


def test_downloads_dir_is_a_path():
    from pathlib import Path
    assert isinstance(uc.downloads_dir(), Path)
