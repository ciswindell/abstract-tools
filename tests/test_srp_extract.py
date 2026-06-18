from pathlib import Path

from openpyxl import Workbook

from abstract_tools.srp.extract import extract_case_actions, read_srp


def _make_srp(path: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.append(["Serial Register Page"])
    ws.append(["CASE ACTIONS"])
    ws.append(["Action Date", "Date Filed", "Action Name", "Action Status",
               "Action Information"])
    ws.append(["2020-01-05", "2020-01-01", "Lease Issued", "Active", "Info A"])
    ws.append([None, None, None, None, "cont A"])
    ws.append(["2019-06-10", "2019-06-01", "Application", "Closed", "Info B"])
    ws.append(["CASE TRANSACTIONS"])
    ws.append(["other", "table", "rows"])
    wb.save(path)
    return path


def test_extract_returns_case_actions_table(tmp_path):
    srp = _make_srp(tmp_path / "srp.xlsx")
    table = extract_case_actions(read_srp(srp))
    assert "Action Name" in list(table.columns)
    # 3 data rows (2 records + 1 continuation), CASE TRANSACTIONS excluded.
    assert len(table) == 3
    assert "table" not in table.values


def test_extract_missing_table_raises(tmp_path):
    wb = Workbook()
    wb.active.append(["Serial Register Page"])
    wb.active.append(["LAND RECORDS"])
    path = tmp_path / "no_actions.xlsx"
    wb.save(path)
    import pytest
    with pytest.raises(ValueError, match="CASE ACTIONS"):
        extract_case_actions(read_srp(path))
