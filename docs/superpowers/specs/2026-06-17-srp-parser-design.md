# SRP Parser — Design

**Date:** 2026-06-17
**Status:** Approved

## Summary

Add a third tool to the Abstract Tools desktop app: an **SRP Parser**, under a
new home-board category **"Bureau of Land Management"**. It adapts the existing
standalone Streamlit app (`aa-merge-srp`) into a GUI tool that lives inside the
suite alongside the NMSLO Segmentor and the Batch TIFF to PDF Converter.

The tool reads a BLM **Serial Register Page (SRP)** Excel export plus an
**Abstract Worksheet**, and writes two sheets into the worksheet, overwriting it
in place:

- **"SRP Case Actions"** — the SRP's *Case Actions* table, cleaned (columns
  renamed, multi-row remarks merged, dates filled and sorted), and formatted
  (column widths, wrapped text, frozen header, autofilter, date number-format).
- **"SRP"** — a verbatim, formatting-preserving copy of the original SRP sheet.

## Reimplementation, not a verbatim port

The source app works but is heavily over-engineered for the job: a chain of
factory classes (`SRPSource` → `SRPDataTableFactory` → `SRPDataFactory`), a
dependency-injected service layer (`SRPDataExportService`, `ExcelFormatService`),
result-wrapper objects (`SRPProcessingResult`, `SRPExportResult`), and
try/except-log-reraise on nearly every method. It also carries dead weight:
commented-out table extractions, tkinter file-dialog `__main__` blocks, a
`BytesIO`/Streamlit upload path, and an `SRPData` dataclass with ~15 fields of
which only `CaseActions` (plus a couple of authority fields) is used.

This design **reimplements the engine cleanly** rather than porting it
verbatim. Decisions:

- **Keep pandas** as the parsing tool (chosen over a from-scratch openpyxl
  rewrite — reuses the genuinely tricky table-slicing and remark-merge logic).
- **Collapse the ceremony**: no service/DI layer, no factory chain, no result
  wrappers. A handful of small functions and one or two value dataclasses.
- **Delete the dead code**: commented tables, tkinter, `BytesIO`/Streamlit,
  unused `SRPData` fields, blanket try/except-log-reraise (let real errors
  propagate to one handler at the UI boundary).
- **Modernize to repo rules**: `X | None` typing, frozen dataclasses for value
  objects, Python ≥3.12 idioms.

The behavior of the cleaned engine must match the original on the same inputs;
the tests below pin that behavior.

## User flow

1. **Drop screen** — two side-by-side labeled drop zones: **"Drop SRP file
   here"** and **"Drop Abstract Worksheet here"**. Each zone also accepts a
   click to open a file browser, and accepts only `.xlsx`. A dropped/selected
   file shows its name in the zone. A **Process** button enables once both
   files are present.
2. **Processing** — work runs off the UI thread; the header shows progress and
   the UI stays responsive.
3. **Result** — inline (no modal):
   - success → "Worksheet updated" with **Open file** / **Open folder** buttons
     and a "Parse another" reset.
   - failure → the error shown inline (e.g. "Case Actions table not found on the
     SRP"), with a reset to try again.

### Behavior details

- **Overwrite in place, no prompt, no backup.** On Process, the worksheet is
  modified and saved over the original path immediately. See *Recorded
  deviation* below.
- The two labeled zones make file roles explicit, so there is no auto-detection
  and no swap step.
- openpyxl loads, modifies, and re-saves the worksheet; anything openpyxl does
  not round-trip (charts, macros, some advanced formatting) may be lost from the
  original. This matched the source app's engine; overwriting the real source
  (rather than a download) is what makes it irreversible.

## Code structure

### `src/abstract_tools/srp/` (new — pure engine, no Qt)

Mirrors how the Segmentor keeps its engine out of `ui/` (`model.py`,
`ingest.py`, `export.py`). Grouped in a `srp/` subpackage to avoid colliding
with the source app's `srp_parser` name and to keep the engine cohesive.

- `extract.py` — read the SRP `.xlsx` into a dataframe and slice out the Case
  Actions table (the `SRPTableExtractor` header-boundary logic, simplified). The
  authority fields (report date, serial number, legacy serial number) are
  **dropped**: the source app extracts them but never writes them to the output,
  so they are dead weight and the cleaned engine omits them.
- `transform.py` — clean the Case Actions table: rename columns, merge
  multi-row "Action Information" into single entries, fill missing Action Date
  from Received Date, sort by Received Date. Exposes a small frozen value object
  for the result (e.g. `SrpCaseActions` wrapping the dataframe).
- `excel_build.py` — openpyxl: load the worksheet, add the "SRP Case Actions"
  sheet (formatted per a small config) and the "SRP" sheet (verbatim copy with
  formatting), save over the original path. Folds in today's
  `_copy_sheet_with_formatting`, `_add_dataframe_to_sheet`, and the
  `CaseActionsSheetConfig` column widths / date columns / order.
- `__init__.py` — exposes one entry function
  `run_srp_merge(srp_path: Path, worksheet_path: Path) -> None` (analogous to
  `export.run_export()`) that ties extract → transform → build → save.

### `src/abstract_tools/ui/srp_parser/` (new tool package)

Mirrors `src/abstract_tools/ui/tiff_converter/`:

- `tool.py` — `SrpParserTool(QtWidgets.QWidget)` taking `on_back_to_tools`, with
  an internal `QStackedWidget`: drop screen → result screen. Same shape as the
  other tools (`shutdown()`, restart).
- `drop_screen.py` — the two drop zones, Process button, inline result, and
  "Parse another".
- `FileDropZone` — a new reusable styled widget (drag-and-drop + click-to-browse,
  `.xlsx` only). As a new Qt widget type it gets theme QSS (Principle V).
- A **QThread worker** so `run_srp_merge` runs off the UI thread and reports
  progress/result via signals; `shutdown()` quits and waits.

## Shared changes

- **`src/abstract_tools/tools.py`** — register `SRP_PARSER_TOOL`:
  - name: "SRP Parser"
  - category: "Bureau of Land Management"
  - icon: `icons/srp_parser.svg`
- **`src/abstract_tools/ui/header.py`** — pass SRP steps
  (e.g. `["1 · Drop files", "2 · Result"]`) via the existing `steps=` parameter;
  no header changes needed.
- **`src/abstract_tools/resources/icons/srp_parser.svg`** — new icon.
- **`requirements.txt`** — add `pandas`.
- **`abstract_tools.spec`** — add `pandas`/`numpy` `hiddenimports` (pandas pulls
  dynamic imports; Principle IV), and the new SVG to `datas`.

## Tests (test-first, RED → GREEN, matching existing style)

Fixtures are synthetic `.xlsx` files built in-test — **no real customer data**.

- `tests/test_srp_extract.py` — extraction finds the Case Actions table; the
  "table not found on the SRP" path raises a clear error.
- `tests/test_srp_transform.py` — column renames; multi-row "Action
  Information" merge into one cell; missing Action Date filled from Received
  Date only when Received Date exists; sort by Received Date with blanks last.
- `tests/test_srp_excel_build.py` — given a fixture worksheet + SRP, the saved
  output has both new sheets in the right order, "SRP Case Actions" headers and
  date formatting are correct, and the worksheet's original sheets are
  preserved.
- `tests/test_srp_parser_tool.py` — UI (pytest-qt, offscreen): drop screen
  builds; supplying both files enables Process; result screen states render;
  `shutdown()` is safe.
- Extend `tests/test_tools.py` and `tests/test_icons.py` for the new registered
  tool and icon.

## Packaging verification (Principle IV)

After green tests, build the Windows `.exe` in CI and click through it: drop a
real SRP + worksheet, confirm both sheets are written and the worksheet opens in
Excel. pandas is the first numeric-stack dependency in the bundle, so the
`.exe`-level check is mandatory, not optional.

## Recorded deviation

The constitution (Development Workflow & Quality Gates) requires hard-to-reverse
actions to be confirmed before execution. By **explicit user instruction**, this
tool overwrites the original Abstract Worksheet **with no confirmation prompt
and no backup**. Governance permits this: an explicit user instruction overrides
the constitution. Recorded here so review treats it as intentional, not a defect.

## Scope (YAGNI — explicitly out for v1)

- Parsing any SRP table other than Case Actions (the others are commented out in
  the source and stay out).
- Save-As / choose-output-location, backup copies, overwrite confirmation.
- Auto-detecting which dropped file is which (the two labeled zones make it
  explicit).
- Docker, the Streamlit/web UI, multi-file batch processing.
