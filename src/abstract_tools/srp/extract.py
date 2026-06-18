# src/abstract_tools/srp/extract.py
"""Read a raw SRP workbook and slice out the CASE ACTIONS table.

A Serial Register Page sheet is a stack of labeled sub-tables. We locate the
CASE ACTIONS marker row, take everything until the next marker, drop empty
rows/columns, and promote the first remaining row to column headers.
"""

from pathlib import Path

import pandas as pd

from abstract_tools.srp.config import TABLE_HEADERS

_CASE_ACTIONS = "CASE ACTIONS"


def read_srp(path: Path) -> pd.DataFrame:
    """Read the SRP workbook's first sheet as a header-less DataFrame."""
    return pd.read_excel(path, header=None, na_values=["NaN", "nan", "NAN", ""])


def _marker_row(df: pd.DataFrame, marker: str) -> int:
    """Row index whose any cell equals `marker`, or -1 if not present."""
    for i in range(len(df)):
        if df.iloc[i].eq(marker).any():
            return i
    return -1


def extract_case_actions(srp_df: pd.DataFrame) -> pd.DataFrame:
    """Return the CASE ACTIONS sub-table with its header row applied.

    Raises ValueError if the SRP has no CASE ACTIONS table.
    """
    start = _marker_row(srp_df, _CASE_ACTIONS)
    if start < 0:
        raise ValueError("CASE ACTIONS table not found on the SRP")

    block = srp_df.iloc[start + 1:].reset_index(drop=True)

    # Cut at the nearest following section marker.
    cut = len(block)
    for marker in TABLE_HEADERS:
        if marker == _CASE_ACTIONS:
            continue
        idx = _marker_row(block, marker)
        if idx >= 0:
            cut = min(cut, idx)
    block = block.iloc[:cut]

    block = block.dropna(how="all", axis=0).dropna(how="all", axis=1)
    block.columns = block.iloc[0]
    return block.iloc[1:].reset_index(drop=True)
