# tests/test_srp_transform.py
import pandas as pd
import pytest

from abstract_tools.srp.config import COLUMN_ORDER
from abstract_tools.srp.transform import clean_case_actions


def _raw():
    # Columns as produced by extract (original SRP headers).
    return pd.DataFrame(
        [
            ["2020-01-05", "2020-01-01", "Lease Issued", "Active", "Info A"],
            [None, None, None, None, "cont A"],
            ["2019-06-10", "2019-06-01", "Application", "Closed", "Info B"],
            [None, "2021-03-01", "Amendment", "Active", "Info C"],
        ],
        columns=["Action Date", "Date Filed", "Action Name", "Action Status",
                 "Action Information"],
    )


def test_columns_match_config_order():
    out = clean_case_actions(_raw())
    assert list(out.columns) == COLUMN_ORDER


def test_continuation_rows_merge_into_remarks():
    out = clean_case_actions(_raw())
    lease = out[out["Document Type"] == "Lease Issued"].iloc[0]
    assert lease["Runsheet Remarks"] == "Info A\ncont A"
    # 3 records (the continuation row folded into Lease Issued).
    assert len(out) == 3


def test_sorted_by_received_date_ascending():
    out = clean_case_actions(_raw())
    assert list(out["Document Type"])[:2] == ["Application", "Lease Issued"]


def test_action_date_filled_from_received_date():
    out = clean_case_actions(_raw())
    amendment = out[out["Document Type"] == "Amendment"].iloc[0]
    assert amendment["Action Date"] == pd.Timestamp("2021-03-01")


def test_missing_source_columns_raise():
    bad = pd.DataFrame([["x"]], columns=["Action Name"])
    with pytest.raises(ValueError, match="expected columns"):
        clean_case_actions(bad)


def test_existing_action_date_not_overwritten():
    raw = pd.DataFrame(
        [["2022-05-05", "2022-05-01", "Renewal", "Active", "Info"]],
        columns=["Action Date", "Date Filed", "Action Name", "Action Status",
                 "Action Information"],
    )
    out = clean_case_actions(raw)
    row = out.iloc[0]
    assert row["Action Date"] == pd.Timestamp("2022-05-05")
    assert row["Received Date"] == pd.Timestamp("2022-05-01")
