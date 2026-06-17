from datetime import date

from aa_tool.labels import build_bookmark_label


def test_label_with_blank_date_renders_na():
    assert build_bookmark_label(1) == "1-Unknown-NA"


def test_label_with_date_renders_m_d_yyyy():
    assert build_bookmark_label(5, "Deed", date(2020, 3, 7)) == "5-Deed-3/7/2020"
