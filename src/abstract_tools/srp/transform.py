# src/abstract_tools/srp/transform.py
"""Clean the raw CASE ACTIONS table into the export-ready frame.

A record spans one "Action Name" row plus any following rows that carry only
continuation text in "Action Information". We collapse each record to a single
row, joining the continuation text, then rename/reorder columns, parse dates,
back-fill Action Date from Received Date, and sort by Received Date.
"""

import pandas as pd

from abstract_tools.srp.config import (
    COLUMN_ORDER,
    COLUMN_RENAMES,
    DATE_COLUMNS,
)

_REQUIRED_SOURCE = set(COLUMN_RENAMES)  # Action Date, Date Filed, Action Name, ...


def _merge_records(table: pd.DataFrame) -> pd.DataFrame:
    """Collapse continuation rows; join their Action Information with newlines."""
    # Each non-null Action Name starts a new record; continuation rows inherit
    # the running record number via cumulative-sum forward fill.
    record = table["Action Name"].notna().cumsum()
    table = table[record > 0]
    record = record[record > 0]

    def _join(values: pd.Series) -> str:
        return "\n".join(str(v).strip() for v in values if pd.notna(v))

    agg = {col: "first" for col in table.columns}
    agg["Action Information"] = _join
    return table.groupby(record, sort=False).agg(agg).reset_index(drop=True)


def clean_case_actions(raw_table: pd.DataFrame) -> pd.DataFrame:
    """Return the export-ready Case Actions frame (columns == COLUMN_ORDER)."""
    missing = _REQUIRED_SOURCE - set(raw_table.columns)
    if missing:
        raise ValueError(
            f"SRP Case Actions is missing expected columns: {sorted(missing)}"
        )

    df = _merge_records(raw_table).rename(columns=COLUMN_RENAMES)

    for col in COLUMN_ORDER:
        if col not in df.columns:
            df[col] = ""
    df = df[COLUMN_ORDER]

    for col in DATE_COLUMNS:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    # Back-fill a blank Action Date from Received Date, but only when a
    # Received Date actually exists for that row.
    has_received = df["Received Date"].notna()
    df.loc[has_received, "Action Date"] = df.loc[has_received, "Action Date"].fillna(
        df.loc[has_received, "Received Date"]
    )

    df = df.sort_values("Received Date", na_position="last")
    return df.reset_index(drop=True)
