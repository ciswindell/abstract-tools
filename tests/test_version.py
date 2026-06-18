from abstract_tools import version as v


def test_is_newer_handles_numeric_ordering():
    assert v.is_newer("1.10.0", "1.9.0") is True   # the classic string-sort trap
    assert v.is_newer("2.0.0", "1.9.9") is True
    assert v.is_newer("1.2.3", "1.2.3") is False
    assert v.is_newer("1.2.2", "1.2.3") is False


def test_is_newer_tolerates_leading_v_and_suffixes():
    assert v.is_newer("v1.4.0", "1.3.0") is True
    assert v.is_newer("1.4.0", "v1.4.0") is False
    assert v.is_newer("1.4.0+build7", "1.4.0") is False


def test_dev_build_detection_and_display():
    assert v.is_dev_build("0.0.0+dev") is True
    assert v.is_dev_build("1.2.3") is False
    assert v.display_version("0.0.0+dev") == "dev"
    assert v.display_version("1.2.3") == "v1.2.3"
    assert v.display_version("v1.2.3") == "v1.2.3"


def test_is_dev_build_with_plus_dev_suffix():
    # Locks in the intended behaviour: "+dev" in text is the sole check.
    assert v.is_dev_build("1.2.3+dev") is True
