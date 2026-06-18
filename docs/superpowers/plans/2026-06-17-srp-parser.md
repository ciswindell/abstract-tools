# SRP Parser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "SRP Parser" tool to the Abstract Tools suite that reads a BLM Serial Register Page (SRP) Excel export plus an Abstract Worksheet, and writes a cleaned "SRP Case Actions" sheet and a verbatim "SRP" sheet into the worksheet, overwriting it in place.

**Architecture:** A pure pandas/openpyxl engine under `src/abstract_tools/srp/` (extract → transform → excel_build, tied together by `run_srp_merge`), and a PySide6 UI under `src/abstract_tools/ui/srp_parser/` (two labeled drag-and-drop zones → background-thread merge → inline result). The engine is a clean reimplementation of the over-engineered `aa-merge-srp` source, not a verbatim port.

**Tech Stack:** Python ≥3.12, PySide6, pandas (new), openpyxl, pytest + pytest-qt.

## Global Constraints

- Python ≥3.12; modern typing (`X | None`, `list[...]`); frozen dataclasses for value objects.
- GUI is PySide6; long-running work runs off the UI thread via `QThread` (never `multiprocessing`); any tool/screen owning a thread implements `shutdown()` (quit + wait).
- New Qt widget types MUST carry theme styling (an unstyled widget is a defect).
- Bundled resources resolve through `resource_path()`; new resources go under `src/abstract_tools/resources/`.
- Tests assert real behavior; no real customer data — fixtures are synthetic `.xlsx` built in-test.
- Run tests headless: `QT_QPA_PLATFORM=offscreen python -m pytest`.
- Conventional Commit prefixes (`feat:`, `fix:`, `chore:`, `docs:`, `build:`).
- **Recorded deviation (explicit user instruction):** the worksheet is overwritten in place with **no confirmation prompt and no backup**. Do not add a confirm dialog or backup copy.
- Work happens on the `dev` branch.

---

### Task 1: Engine — config + Case Actions extraction

**Files:**
- Create: `src/abstract_tools/srp/__init__.py` (empty for now)
- Create: `src/abstract_tools/srp/config.py`
- Create: `src/abstract_tools/srp/extract.py`
- Test: `tests/test_srp_extract.py`

**Interfaces:**
- Produces:
  - `config.COLUMN_RENAMES: dict[str, str]`, `config.COLUMN_ORDER: list[str]`, `config.COLUMN_WIDTHS: dict[str, int]`, `config.DATE_COLUMNS: list[str]`, `config.DATE_FORMAT: str`, `config.SHEET_NAME: str`, `config.TABLE_HEADERS: list[str]`
  - `extract.read_srp(path: Path) -> pandas.DataFrame`
  - `extract.extract_case_actions(srp_df: pandas.DataFrame) -> pandas.DataFrame` — raises `ValueError` if the CASE ACTIONS table is absent

- [ ] **Step 1: Write `config.py`** (no test of its own; it is data consumed by later steps)

```python
# src/abstract_tools/srp/config.py
"""Static layout/formatting config for the SRP Case Actions sheet.

Shared by the transform step (column order, date columns) and the Excel
build step (widths, date number-format, sheet name).
"""

# Source SRP column name -> exported column name.
COLUMN_RENAMES: dict[str, str] = {
    "Action Date": "Action Date",
    "Date Filed": "Received Date",
    "Action Name": "Document Type",
    "Action Status": "Action Status",
    "Action Information": "Runsheet Remarks",
}

# Final column order of the exported "SRP Case Actions" sheet.
COLUMN_ORDER: list[str] = [
    "Document Type",
    "Received Date",
    "Document Date",
    "Effective Date",
    "Action Date",
    "Grantor",
    "Grantee",
    "Legal Description",
    "Runsheet Remarks",
    "Abstract Remarks",
    "Internal Remarks",
    "Action Status",
]

COLUMN_WIDTHS: dict[str, int] = {
    "Document Type": 35,
    "Received Date": 12,
    "Document Date": 12,
    "Effective Date": 12,
    "Action Date": 12,
    "Grantor": 10,
    "Grantee": 10,
    "Legal Description": 10,
    "Runsheet Remarks": 45,
    "Abstract Remarks": 10,
    "Internal Remarks": 10,
    "Action Status": 20,
}

DATE_COLUMNS: list[str] = [
    "Received Date",
    "Document Date",
    "Effective Date",
    "Action Date",
]

DATE_FORMAT: str = "m/d/yyyy"
SHEET_NAME: str = "SRP Case Actions"

# Section markers found in a raw SRP sheet, used as table boundaries.
TABLE_HEADERS: list[str] = [
    "Serial Register Page",
    "CASE CUSTOMERS",
    "RECORD TITLE ",
    "OPERATING RIGHTS ",
    "LAND RECORDS",
    "CASE ACTIONS",
    "CASE TRANSACTIONS",
    "ASSOCIATED AGREEMENT OR LEASE (RECAPITULATION TABLE) INFO",
    "ASSOCIATED BONDS",
    "LEGACY CASE REMARKS",
]
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_srp_extract.py
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_srp_extract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'abstract_tools.srp.extract'`.

- [ ] **Step 4: Write `extract.py`**

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_srp_extract.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add src/abstract_tools/srp/__init__.py src/abstract_tools/srp/config.py \
        src/abstract_tools/srp/extract.py tests/test_srp_extract.py
git commit -m "feat: add SRP Case Actions extraction engine"
```

---

### Task 2: Engine — transform (clean Case Actions)

**Files:**
- Create: `src/abstract_tools/srp/transform.py`
- Test: `tests/test_srp_transform.py`

**Interfaces:**
- Consumes: `extract.extract_case_actions(...)` output (raw table with source columns `Action Date`, `Date Filed`, `Action Name`, `Action Status`, `Action Information`); `config.*`.
- Produces: `transform.clean_case_actions(raw_table: pandas.DataFrame) -> pandas.DataFrame` — final export frame with exactly `config.COLUMN_ORDER` columns, multi-row remarks merged, dates parsed, Action Date back-filled from Received Date, sorted by Received Date ascending (blanks last). Raises `ValueError` if required source columns are absent.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_srp_transform.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'abstract_tools.srp.transform'`.

- [ ] **Step 3: Write `transform.py`**

```python
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
```

Note: dates are kept as `Timestamp`/`NaT` here (not filled to `""`); the Excel step writes Timestamps as real dates and treats `NaT` as blank. `test_action_date_filled_from_received_date` relies on this.

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_srp_transform.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/abstract_tools/srp/transform.py tests/test_srp_transform.py
git commit -m "feat: add SRP Case Actions transform/cleaning"
```

---

### Task 3: Engine — Excel build + `run_srp_merge`

**Files:**
- Create: `src/abstract_tools/srp/excel_build.py`
- Modify: `src/abstract_tools/srp/__init__.py` (expose `run_srp_merge`)
- Test: `tests/test_srp_excel_build.py`

**Interfaces:**
- Consumes: `extract.read_srp`, `extract.extract_case_actions`, `transform.clean_case_actions`, `config.*`.
- Produces:
  - `excel_build.run_srp_merge(srp_path: Path, worksheet_path: Path) -> None` — overwrites `worksheet_path` in place with two added sheets.
  - `abstract_tools.srp.run_srp_merge` re-exported from `__init__.py`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_srp_excel_build.py
from pathlib import Path

from openpyxl import Workbook, load_workbook

from abstract_tools.srp import run_srp_merge
from abstract_tools.srp.config import DATE_FORMAT


def _make_srp(path: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.append(["Serial Register Page"])
    ws.append(["CASE ACTIONS"])
    ws.append(["Action Date", "Date Filed", "Action Name", "Action Status",
               "Action Information"])
    ws.append(["2020-01-05", "2020-01-01", "Lease Issued", "Active", "Info A"])
    ws.append(["2019-06-10", "2019-06-01", "Application", "Closed", "Info B"])
    wb.save(path)
    return path


def _make_worksheet(path: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Abstract"
    ws["A1"] = "KEEP ME"
    wb.save(path)
    return path


def test_merge_adds_both_sheets_in_order(tmp_path):
    srp = _make_srp(tmp_path / "srp.xlsx")
    worksheet = _make_worksheet(tmp_path / "abstract.xlsx")

    run_srp_merge(srp, worksheet)

    wb = load_workbook(worksheet)
    assert wb.sheetnames == ["Abstract", "SRP Case Actions", "SRP"]
    # Original content preserved.
    assert wb["Abstract"]["A1"].value == "KEEP ME"
    # Case Actions header row.
    assert wb["SRP Case Actions"]["A1"].value == "Document Type"


def test_case_actions_date_cells_formatted(tmp_path):
    srp = _make_srp(tmp_path / "srp.xlsx")
    worksheet = _make_worksheet(tmp_path / "abstract.xlsx")
    run_srp_merge(srp, worksheet)

    ws = load_workbook(worksheet)["SRP Case Actions"]
    # Column B is "Received Date"; row 2 is the first data row.
    assert ws["B2"].number_format == DATE_FORMAT


def test_rerun_overwrites_without_duplicating_sheets(tmp_path):
    srp = _make_srp(tmp_path / "srp.xlsx")
    worksheet = _make_worksheet(tmp_path / "abstract.xlsx")
    run_srp_merge(srp, worksheet)
    run_srp_merge(srp, worksheet)  # second run must not error or duplicate

    wb = load_workbook(worksheet)
    assert wb.sheetnames == ["Abstract", "SRP Case Actions", "SRP"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_srp_excel_build.py -v`
Expected: FAIL — `ImportError: cannot import name 'run_srp_merge'`.

- [ ] **Step 3: Write `excel_build.py`**

```python
# src/abstract_tools/srp/excel_build.py
"""Write the cleaned Case Actions sheet and a verbatim SRP-sheet copy into the
Abstract Worksheet, saving over the original file.
"""

from copy import copy
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter

from abstract_tools.srp.config import (
    COLUMN_WIDTHS,
    DATE_COLUMNS,
    DATE_FORMAT,
    SHEET_NAME,
)
from abstract_tools.srp.extract import extract_case_actions, read_srp
from abstract_tools.srp.transform import clean_case_actions

_SRP_SHEET = "SRP"


def _write_case_actions(ws, df: pd.DataFrame) -> None:
    """Write the DataFrame plus column widths, wrapping, date format, filter."""
    for col_idx, name in enumerate(df.columns, start=1):
        ws.cell(row=1, column=col_idx, value=name)
    for row_idx, row in enumerate(df.itertuples(index=False), start=2):
        for col_idx, value in enumerate(row, start=1):
            # NaT/blank dates come through as empty; write "" rather than a marker.
            cell_value = "" if value is pd.NaT or pd.isna(value) else value
            ws.cell(row=row_idx, column=col_idx, value=cell_value)

    for col_idx, name in enumerate(df.columns, start=1):
        letter = get_column_letter(col_idx)
        ws.column_dimensions[letter].width = COLUMN_WIDTHS.get(name, 15)
        for row_idx in range(1, len(df) + 2):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            if row_idx > 1 and name in DATE_COLUMNS:
                cell.number_format = DATE_FORMAT

    if len(df) > 0:
        last = get_column_letter(len(df.columns))
        ws.auto_filter.ref = f"A1:{last}{len(df) + 1}"
    ws.freeze_panes = "A2"


def _copy_sheet(source, target) -> None:
    """Copy values + formatting from one worksheet to another."""
    for row in source.iter_rows():
        for cell in row:
            if cell.value is None and not cell.has_style:
                continue
            tgt = target.cell(row=cell.row, column=cell.column)
            tgt.value = cell.value
            if cell.has_style:
                tgt.font = copy(cell.font)
                tgt.border = copy(cell.border)
                tgt.fill = copy(cell.fill)
                tgt.number_format = cell.number_format
                tgt.protection = copy(cell.protection)
                tgt.alignment = copy(cell.alignment)

    for merged in source.merged_cells.ranges:
        target.merge_cells(str(merged))
    for letter, dim in source.column_dimensions.items():
        if dim.width:
            target.column_dimensions[letter].width = dim.width
    for idx, dim in source.row_dimensions.items():
        if dim.height:
            target.row_dimensions[idx].height = dim.height


def run_srp_merge(srp_path: Path, worksheet_path: Path) -> None:
    """Add 'SRP Case Actions' and 'SRP' sheets to the worksheet, in place."""
    case_actions = clean_case_actions(extract_case_actions(read_srp(srp_path)))

    workbook = load_workbook(worksheet_path)
    for name in (SHEET_NAME, _SRP_SHEET):
        if name in workbook.sheetnames:
            del workbook[name]

    _write_case_actions(workbook.create_sheet(SHEET_NAME), case_actions)

    srp_source = load_workbook(srp_path, data_only=False).active
    _copy_sheet(srp_source, workbook.create_sheet(_SRP_SHEET))

    workbook.save(worksheet_path)
```

- [ ] **Step 4: Update `__init__.py` to expose the entry point**

```python
# src/abstract_tools/srp/__init__.py
"""SRP Parser engine: read a BLM Serial Register Page export and merge a
cleaned Case Actions sheet plus a verbatim SRP copy into an Abstract Worksheet.
"""

from abstract_tools.srp.excel_build import run_srp_merge

__all__ = ["run_srp_merge"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_srp_excel_build.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Run the whole engine suite**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_srp_extract.py tests/test_srp_transform.py tests/test_srp_excel_build.py -v`
Expected: PASS (10 passed).

- [ ] **Step 7: Commit**

```bash
git add src/abstract_tools/srp/excel_build.py src/abstract_tools/srp/__init__.py \
        tests/test_srp_excel_build.py
git commit -m "feat: add SRP merge into Abstract Worksheet (excel_build)"
```

---

### Task 4: Dependency, packaging, and icon

**Files:**
- Modify: `requirements.txt`
- Modify: `abstract_tools.spec` (add pandas/numpy `hiddenimports`)
- Create: `src/abstract_tools/resources/icons/srp_parser.svg`
- Modify: `tests/test_icons.py` (add a render test)

**Interfaces:**
- Produces: bundled icon resource `icons/srp_parser.svg`.

- [ ] **Step 1: Add pandas to `requirements.txt`**

Add this line after the `openpyxl==3.1.*` line:

```
pandas==2.2.*
```

- [ ] **Step 2: Add pandas/numpy hiddenimports to `abstract_tools.spec`**

In `abstract_tools.spec`, replace the `hiddenimports=[...]` list so it reads:

```python
    hiddenimports=[
        "PIL.TiffImagePlugin",
        "PIL.JpegImagePlugin",
        "PIL.PdfImagePlugin",
        "pypdf",
        # The SRP Parser reads/writes Excel via pandas, whose numeric backend
        # PyInstaller's static scan can miss.
        "pandas",
        "numpy",
    ],
```

(The `icons/*.svg` glob already in `datas` bundles the new SVG — no datas change needed.)

- [ ] **Step 3: Create the icon** `src/abstract_tools/resources/icons/srp_parser.svg`

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#1d5c54" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
  <rect x="4" y="3" width="13" height="18" rx="1.5"/>
  <path d="M7 8h7M7 12h7M7 16h4"/>
  <path d="M16.5 15.5l2 2 3.5-3.5"/>
</svg>
```

- [ ] **Step 4: Write the failing icon test**

Add to `tests/test_icons.py`:

```python
def test_srp_parser_icon_renders(qtbot):
    pm = svg_pixmap("icons/srp_parser.svg", 48)
    assert not pm.isNull()
    assert pm.width() == 48
```

- [ ] **Step 5: Run the icon test**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_icons.py -v`
Expected: PASS (existing tests + the new one).

- [ ] **Step 6: Install the new dependency and confirm the suite still imports**

Run: `pip install -r requirements.txt && QT_QPA_PLATFORM=offscreen python -m pytest tests/test_srp_extract.py -q`
Expected: pandas installs into the venv; the engine test still passes.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt abstract_tools.spec \
        src/abstract_tools/resources/icons/srp_parser.svg tests/test_icons.py
git commit -m "build: add pandas dependency and SRP Parser icon"
```

---

### Task 5: Theme styling + `FileDropZone` widget

**Files:**
- Modify: `src/abstract_tools/ui/theme.py` (add drop-zone QSS)
- Create: `src/abstract_tools/ui/srp_parser/__init__.py` (empty)
- Create: `src/abstract_tools/ui/srp_parser/drop_zone.py`
- Test: `tests/test_srp_drop_zone.py`

**Interfaces:**
- Produces: `drop_zone.FileDropZone(QtWidgets.QFrame)` —
  - `__init__(self, label: str)`
  - signal `selected = QtCore.Signal(object)` emitting a `pathlib.Path`
  - attribute `path: Path | None` (current selection)
  - method `set_path(self, path: Path) -> None` (used by drop, browse, and tests)
  - accepts only `.xlsx`; dragging a valid file in or clicking to browse sets the path and emits `selected`.

- [ ] **Step 1: Add theme styling**

In `src/abstract_tools/ui/theme.py`, inside the `STYLESHEET` f-string (before its closing `"""`), add:

```css
QFrame#dropZone {{
    background: {CARD}; border: 2px dashed {LINE};
    border-radius: 12px; min-height: 150px;
}}
QFrame#dropZone:hover {{ border-color: {PINE}; }}
QFrame#dropZoneActive {{
    background: {CARD}; border: 2px dashed {PINE};
    border-radius: 12px; min-height: 150px;
}}
QLabel#dropZoneTitle {{ color: {INK_SOFT}; font-size: 14px; }}
QLabel#dropZoneName {{ color: {PINE}; font-weight: 600; }}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_srp_drop_zone.py
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from abstract_tools.ui.srp_parser.drop_zone import FileDropZone


def test_set_path_updates_state_and_emits(qtbot, tmp_path):
    f = tmp_path / "thing.xlsx"
    f.write_text("x")
    zone = FileDropZone("Drop SRP file here")
    qtbot.addWidget(zone)

    received = []
    zone.selected.connect(lambda p: received.append(p))
    zone.set_path(f)

    assert zone.path == f
    assert received == [f]
    # The filename shows somewhere in the zone's labels.
    from PySide6 import QtWidgets
    texts = [lbl.text() for lbl in zone.findChildren(QtWidgets.QLabel)]
    assert any("thing.xlsx" in t for t in texts)


def test_initial_state_has_no_path(qtbot):
    zone = FileDropZone("Drop SRP file here")
    qtbot.addWidget(zone)
    assert zone.path is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_srp_drop_zone.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'abstract_tools.ui.srp_parser.drop_zone'`.

- [ ] **Step 4: Write `drop_zone.py`**

```python
# src/abstract_tools/ui/srp_parser/drop_zone.py
"""A labeled drag-and-drop target for a single .xlsx file (also click-to-browse)."""

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets


def _xlsx_path(url: QtCore.QUrl) -> Path | None:
    if not url.isLocalFile():
        return None
    path = Path(url.toLocalFile())
    return path if path.suffix.lower() == ".xlsx" else None


class FileDropZone(QtWidgets.QFrame):
    """Drop one .xlsx here, or click to browse. Emits `selected` with the Path."""

    selected = QtCore.Signal(object)  # Path

    def __init__(self, label: str):
        super().__init__()
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.path: Path | None = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(6)
        layout.addStretch()

        self._title = QtWidgets.QLabel(label)
        self._title.setObjectName("dropZoneTitle")
        self._title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title)

        self._name = QtWidgets.QLabel("")
        self._name.setObjectName("dropZoneName")
        self._name.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._name.setWordWrap(True)
        layout.addWidget(self._name)

        layout.addStretch()

    def set_path(self, path: Path) -> None:
        self.path = path
        self._name.setText(path.name)
        self.selected.emit(path)

    def _set_active(self, active: bool) -> None:
        self.setObjectName("dropZoneActive" if active else "dropZone")
        self.style().unpolish(self)
        self.style().polish(self)

    # --- drag and drop ---
    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        if len(urls) == 1 and _xlsx_path(urls[0]) is not None:
            self._set_active(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        self._set_active(False)

    def dropEvent(self, event: QtGui.QDropEvent) -> None:  # noqa: N802
        self._set_active(False)
        path = _xlsx_path(event.mimeData().urls()[0])
        if path is not None:
            self.set_path(path)
            event.acceptProposedAction()

    # --- click to browse ---
    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        start = str(self.path.parent) if self.path else str(Path.home())
        chosen, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Choose .xlsx file", start, "Excel files (*.xlsx)"
        )
        if chosen:
            self.set_path(Path(chosen))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_srp_drop_zone.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add src/abstract_tools/ui/theme.py \
        src/abstract_tools/ui/srp_parser/__init__.py \
        src/abstract_tools/ui/srp_parser/drop_zone.py tests/test_srp_drop_zone.py
git commit -m "feat: add FileDropZone widget and drop-zone theme styling"
```

---

### Task 6: Drop screen + background worker

**Files:**
- Create: `src/abstract_tools/ui/srp_parser/drop_screen.py`
- Test: `tests/test_srp_drop_screen.py`

**Interfaces:**
- Consumes: `FileDropZone`, `Header`, `theme`, `abstract_tools.srp.run_srp_merge`.
- Produces: `drop_screen.DropScreen(QtWidgets.QWidget)` —
  - `__init__(self, on_back_to_tools: Callable[[], None])`
  - `SRP_STEPS = ["1 · Drop files", "2 · Result"]`
  - attributes `srp_zone: FileDropZone`, `worksheet_zone: FileDropZone`, `process_button: QPushButton`
  - `do_merge(self) -> None` — synchronous merge of the two selected files (used by tests; raises on engine error)
  - `shutdown(self) -> None` — quit + wait on the worker thread
  - the Process button enables only when both zones have a path.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_srp_drop_screen.py
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from openpyxl import Workbook, load_workbook

from abstract_tools.ui.srp_parser.drop_screen import DropScreen


def _make_srp(path: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.append(["Serial Register Page"])
    ws.append(["CASE ACTIONS"])
    ws.append(["Action Date", "Date Filed", "Action Name", "Action Status",
               "Action Information"])
    ws.append(["2020-01-05", "2020-01-01", "Lease Issued", "Active", "Info A"])
    wb.save(path)
    return path


def _make_worksheet(path: Path) -> Path:
    wb = Workbook()
    wb.active.title = "Abstract"
    wb.save(path)
    return path


def test_process_disabled_until_both_files_present(qtbot, tmp_path):
    screen = DropScreen(on_back_to_tools=lambda: None)
    qtbot.addWidget(screen)
    assert not screen.process_button.isEnabled()

    screen.srp_zone.set_path(_make_srp(tmp_path / "srp.xlsx"))
    assert not screen.process_button.isEnabled()

    screen.worksheet_zone.set_path(_make_worksheet(tmp_path / "abs.xlsx"))
    assert screen.process_button.isEnabled()


def test_do_merge_writes_sheets(qtbot, tmp_path):
    srp = _make_srp(tmp_path / "srp.xlsx")
    worksheet = _make_worksheet(tmp_path / "abs.xlsx")
    screen = DropScreen(on_back_to_tools=lambda: None)
    qtbot.addWidget(screen)
    screen.srp_zone.set_path(srp)
    screen.worksheet_zone.set_path(worksheet)

    screen.do_merge()

    wb = load_workbook(worksheet)
    assert "SRP Case Actions" in wb.sheetnames
    assert "SRP" in wb.sheetnames


def test_shutdown_without_run_is_noop(qtbot):
    screen = DropScreen(on_back_to_tools=lambda: None)
    qtbot.addWidget(screen)
    screen.shutdown()  # no worker started — must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_srp_drop_screen.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'abstract_tools.ui.srp_parser.drop_screen'`.

- [ ] **Step 3: Write `drop_screen.py`**

```python
# src/abstract_tools/ui/srp_parser/drop_screen.py
"""SRP Parser main screen: two drop zones, a Process button, and inline result."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from abstract_tools.srp import run_srp_merge
from abstract_tools.ui import theme
from abstract_tools.ui.header import Header
from abstract_tools.ui.srp_parser.drop_zone import FileDropZone

SRP_STEPS = ["1 · Drop files", "2 · Result"]


@dataclass(frozen=True)
class MergeResult:
    ok: bool
    error: str = ""


class MergeWorker(QtCore.QObject):
    """Runs run_srp_merge off the UI thread, relaying success or error."""

    finished = QtCore.Signal(object)  # MergeResult

    def __init__(self, srp_path: Path, worksheet_path: Path):
        super().__init__()
        self._srp_path = srp_path
        self._worksheet_path = worksheet_path

    @QtCore.Slot()
    def run(self) -> None:
        try:
            run_srp_merge(self._srp_path, self._worksheet_path)
            self.finished.emit(MergeResult(ok=True))
        except Exception as exc:  # surfaced inline on the screen
            self.finished.emit(MergeResult(ok=False, error=str(exc)))


class DropScreen(QtWidgets.QWidget):
    def __init__(self, on_back_to_tools: Callable[[], None]):
        super().__init__()
        self.setObjectName("screen")
        self._thread: QtCore.QThread | None = None
        self._worker: MergeWorker | None = None

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.header = Header(
            active_step=1,
            context_html="SRP Parser",
            on_back_to_tools=on_back_to_tools,
            steps=SRP_STEPS,
        )
        outer.addWidget(self.header)

        center = QtWidgets.QVBoxLayout()
        center.setContentsMargins(48, 0, 48, 0)
        center.setSpacing(16)
        center.addStretch()
        outer.addLayout(center, 1)

        title = QtWidgets.QLabel("Add SRP data to an Abstract Worksheet")
        title.setObjectName("h1")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        center.addWidget(title)

        zones = QtWidgets.QHBoxLayout()
        zones.setSpacing(16)
        self.srp_zone = FileDropZone("Drop SRP file here\n(or click to browse)")
        self.worksheet_zone = FileDropZone(
            "Drop Abstract Worksheet here\n(or click to browse)"
        )
        self.srp_zone.selected.connect(self._on_zone_selected)
        self.worksheet_zone.selected.connect(self._on_zone_selected)
        zones.addWidget(self.srp_zone)
        zones.addWidget(self.worksheet_zone)
        center.addLayout(zones)

        center.addSpacing(8)
        self.process_button = QtWidgets.QPushButton("Process  →")
        self.process_button.setObjectName("primary")
        self.process_button.setEnabled(False)
        self.process_button.clicked.connect(self._on_process_clicked)
        center.addWidget(
            self.process_button, alignment=QtCore.Qt.AlignmentFlag.AlignCenter
        )

        self.result_label = QtWidgets.QLabel()
        self.result_label.setObjectName("success")
        self.result_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.result_label.setWordWrap(True)
        self.result_label.setVisible(False)
        center.addSpacing(6)
        center.addWidget(self.result_label)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(10)
        actions.addStretch()
        self.open_file_button = QtWidgets.QPushButton("Open worksheet")
        self.open_file_button.setObjectName("ghost")
        self.open_file_button.clicked.connect(self._open_file)
        self.open_folder_button = QtWidgets.QPushButton("Open folder")
        self.open_folder_button.setObjectName("ghost")
        self.open_folder_button.clicked.connect(self._open_folder)
        self.again_button = QtWidgets.QPushButton("Parse another  →")
        self.again_button.setObjectName("primary")
        self.again_button.clicked.connect(self._reset)
        for b in (self.open_file_button, self.open_folder_button, self.again_button):
            b.setVisible(False)
            actions.addWidget(b)
        actions.addStretch()
        center.addSpacing(4)
        center.addLayout(actions)

        center.addStretch()

    # --- enable logic ---
    @QtCore.Slot(object)
    def _on_zone_selected(self, _path: Path) -> None:
        self.process_button.setEnabled(
            self.srp_zone.path is not None and self.worksheet_zone.path is not None
        )

    # --- synchronous core (tests + worker share the engine call) ---
    def do_merge(self) -> None:
        run_srp_merge(self.srp_zone.path, self.worksheet_zone.path)

    # --- background run ---
    def _on_process_clicked(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            return
        self.process_button.setEnabled(False)
        self.result_label.setVisible(False)

        self._thread = QtCore.QThread(self)
        self._worker = MergeWorker(self.srp_zone.path, self.worksheet_zone.path)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_thread_refs)
        self._thread.start()

    @QtCore.Slot()
    def _clear_thread_refs(self) -> None:
        self._thread = None
        self._worker = None

    @QtCore.Slot(object)
    def _on_finished(self, result: MergeResult) -> None:
        if result.ok:
            self.result_label.setObjectName("success")
            self.result_label.setText("✓ Worksheet updated")
            self.open_file_button.setVisible(True)
            self.open_folder_button.setVisible(True)
            self.again_button.setVisible(True)
        else:
            self.result_label.setObjectName("warn")
            self.result_label.setText(f"Could not process: {result.error}")
            self.process_button.setEnabled(True)
        self.result_label.style().unpolish(self.result_label)
        self.result_label.style().polish(self.result_label)
        self.result_label.setVisible(True)

    # --- result actions ---
    def _open_file(self) -> None:
        path = self.worksheet_zone.path
        if path:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))

    def _open_folder(self) -> None:
        path = self.worksheet_zone.path
        if path:
            QtGui.QDesktopServices.openUrl(
                QtCore.QUrl.fromLocalFile(str(path.parent))
            )

    def _reset(self) -> None:
        for zone in (self.srp_zone, self.worksheet_zone):
            zone.path = None
            zone._name.setText("")
        self.process_button.setEnabled(False)
        for b in (self.open_file_button, self.open_folder_button, self.again_button):
            b.setVisible(False)
        self.result_label.setVisible(False)

    # --- teardown ---
    def shutdown(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()

    def closeEvent(self, event):  # noqa: N802 (Qt override)
        self.shutdown()
        super().closeEvent(event)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_srp_drop_screen.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/abstract_tools/ui/srp_parser/drop_screen.py tests/test_srp_drop_screen.py
git commit -m "feat: add SRP Parser drop screen with background merge worker"
```

---

### Task 7: Tool widget + registry wiring

**Files:**
- Create: `src/abstract_tools/ui/srp_parser/tool.py`
- Modify: `src/abstract_tools/tools.py` (register `SRP_PARSER_TOOL`)
- Test: `tests/test_srp_parser_tool.py`
- Modify: `tests/test_tools.py` (assert SRP registration)

**Interfaces:**
- Consumes: `DropScreen`.
- Produces:
  - `tool.SrpParserTool(QtWidgets.QWidget)` — `__init__(self, on_back_to_tools)`, hosts a `DropScreen`, implements `shutdown()`.
  - `tools.SRP_PARSER_TOOL` appended to `tools.TOOLS` (id `srp_parser`, category `Bureau of Land Management`, icon `icons/srp_parser.svg`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_srp_parser_tool.py
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

from abstract_tools.ui.srp_parser.tool import SrpParserTool


def test_tool_builds_with_two_drop_zones(qtbot):
    tool = SrpParserTool(on_back_to_tools=lambda: None)
    qtbot.addWidget(tool)
    from abstract_tools.ui.srp_parser.drop_zone import FileDropZone
    assert len(tool.findChildren(FileDropZone)) == 2


def test_back_to_tools_callback_wired(qtbot):
    called = []
    tool = SrpParserTool(on_back_to_tools=lambda: called.append(True))
    qtbot.addWidget(tool)
    back = [b for b in tool.findChildren(QtWidgets.QPushButton)
            if b.objectName() == "backToTools"]
    assert back
    back[0].click()
    assert called == [True]


def test_shutdown_is_safe(qtbot):
    tool = SrpParserTool(on_back_to_tools=lambda: None)
    qtbot.addWidget(tool)
    tool.shutdown()  # nothing running — must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_srp_parser_tool.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'abstract_tools.ui.srp_parser.tool'`.

- [ ] **Step 3: Write `tool.py`**

```python
# src/abstract_tools/ui/srp_parser/tool.py
from collections.abc import Callable

from PySide6 import QtWidgets

from abstract_tools.ui.srp_parser.drop_screen import DropScreen


class SrpParserTool(QtWidgets.QWidget):
    """Root widget for the SRP Parser tool."""

    def __init__(self, on_back_to_tools: Callable[[], None]):
        super().__init__()
        self.setObjectName("screen")

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.screen = DropScreen(on_back_to_tools=on_back_to_tools)
        outer.addWidget(self.screen)

    def shutdown(self) -> None:
        self.screen.shutdown()

    def closeEvent(self, event):  # noqa: N802 (Qt override)
        self.shutdown()
        super().closeEvent(event)
```

- [ ] **Step 4: Run the tool test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_srp_parser_tool.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Register the tool in `tools.py`**

In `src/abstract_tools/tools.py`, add the import alongside the existing tool imports:

```python
from abstract_tools.ui.srp_parser.tool import SrpParserTool
```

Then add the tool definition after `TIFF_CONVERTER_TOOL` and include it in `TOOLS`:

```python
SRP_PARSER_TOOL = Tool(
    id="srp_parser",
    name="SRP Parser",
    description=(
        "Read a BLM Serial Register Page export and add a cleaned Case Actions "
        "sheet plus a verbatim SRP copy to an Abstract Worksheet."
    ),
    category="Bureau of Land Management",
    icon="icons/srp_parser.svg",
    build=lambda on_back: SrpParserTool(on_back),
)

TOOLS: list[Tool] = [SEGMENTOR_TOOL, TIFF_CONVERTER_TOOL, SRP_PARSER_TOOL]
```

- [ ] **Step 6: Add the registration test**

Add to `tests/test_tools.py`:

```python
def test_srp_parser_registered_under_blm():
    from abstract_tools.tools import TOOLS

    by_id = {t.id: t for t in TOOLS}
    tool = by_id["srp_parser"]
    assert tool.name == "SRP Parser"
    assert tool.category == "Bureau of Land Management"
    assert tool.icon == "icons/srp_parser.svg"
```

- [ ] **Step 7: Run the full test suite**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest -q`
Expected: PASS (all existing tests + the new SRP tests).

- [ ] **Step 8: Commit**

```bash
git add src/abstract_tools/ui/srp_parser/tool.py src/abstract_tools/tools.py \
        tests/test_srp_parser_tool.py tests/test_tools.py
git commit -m "feat: register SRP Parser tool under Bureau of Land Management"
```

---

## Final verification (Principle IV — Verify the Real Artifact)

Not a code task, but required before calling the feature done:

- [ ] **Run the app from source** and click into SRP Parser: drop a real SRP `.xlsx` and a real Abstract Worksheet into the two zones, click Process, confirm the result shows "Worksheet updated" and the worksheet (opened from the button) has the two new sheets.

Run: `python main.py`

- [ ] **Build and click through the packaged `.exe`** (in CI via the "Build Windows EXE" workflow / `v*` tag, or locally with `pyinstaller --noconfirm abstract_tools.spec`). pandas is the first numeric-stack dependency in the bundle, so confirm the `.exe` launches and an SRP merge succeeds inside the packaged app — do not rely on the source run alone. If `import pandas`/`numpy` fails in the bundle, confirm the `hiddenimports` from Task 4 are present.

---

## Self-Review

**Spec coverage:**
- New tool under "Bureau of Land Management" → Task 7. ✓
- Two labeled drag-and-drop zones, click-to-browse, `.xlsx` only → Task 5 (`FileDropZone`), Task 6 (screen). ✓
- Overwrite in place, no prompt/no backup → Task 3 (`run_srp_merge` saves over path), Global Constraints. ✓
- Clean reimplementation (no factory/service/result-wrapper ceremony, dead code dropped, modern typing) → Tasks 1–3. ✓
- Engine under `src/abstract_tools/srp/`, UI under `src/abstract_tools/ui/srp_parser/` → Tasks 1–3 / 5–7. ✓
- "SRP Case Actions" (cleaned, formatted) + "SRP" (verbatim copy) sheets → Task 3. ✓
- pandas added; pandas/numpy hiddenimports; new icon → Task 4. ✓
- Background thread + `shutdown()` → Task 6 / 7. ✓
- New widget carries theme styling → Task 5. ✓
- Test-first throughout; `.exe` verification → all tasks + Final verification. ✓
- Authority fields dropped (dead in output) → handled by Task 1 extracting only Case Actions. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. ✓

**Type consistency:** `run_srp_merge(srp_path, worksheet_path)`, `clean_case_actions`, `extract_case_actions`, `read_srp`, `FileDropZone.set_path/selected/path`, `DropScreen.do_merge/shutdown/process_button/srp_zone/worksheet_zone`, `MergeResult(ok, error)` are used consistently across tasks. ✓
