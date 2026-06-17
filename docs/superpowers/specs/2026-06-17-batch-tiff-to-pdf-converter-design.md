# Batch TIFF to PDF Converter — Design

**Date:** 2026-06-17
**Status:** Approved

## Summary

Add a second tool to the Abstract Tools desktop app: a **Batch TIFF to PDF
Converter**. It adapts the existing standalone CLI converter
(`ciswindell-tools/tiff-batch-to-pdf` `tiff_batch_to_pdf.py`) into a GUI tool
that lives inside the app alongside the NMSLO Segmentor, under the **NM State
Land Office** group on the home board.

The tool converts a folder tree of TIFFs to PDFs (one PDF per TIFF, multi-page
TIFFs preserved), mirrors the source folder structure into a `<source>
converted/` sibling, copies non-TIFF files verbatim, and verifies page counts
per file.

## User flow

1. **Open screen** — "Choose a folder of TIFFs" button.
2. **Plan screen** — the app scans the chosen folder and shows:
   - number of TIFFs to convert
   - number of other files to copy
   - total source size
   - output destination (defaults to `<source> converted/`, editable via a
     "Change…" button, mirroring the Segmentor export screen)
   - a **"Standardize pages (letter/legal)"** checkbox, **on by default**
   - a **Convert** button
3. **Converting** — a progress bar in the header fills as files complete. The
   UI stays responsive (work runs off the UI thread).
4. **Result** — inline summary: ✓ N converted, N copied, N failed. If any
   conversions failed, the failed filenames are listed inline. A "Convert
   another folder" button resets to the open screen.

### Behavior details

- Already-converted files (matching output PDF with matching page count) are
  **skipped automatically**, so re-running on the same folder is safe and fast.
- Folder structure is mirrored; non-TIFF files are copied as-is.
- **No log files are written** — the output folder stays clean. All results are
  shown in the UI only.

## Code structure

### `src/aa_tool/tiff_convert.py` (new — pure engine, no Qt)

Adapted from the existing CLI script. Reused verbatim (carries hard-won fixes
for old-style JPEG-compressed and multi-page scanned TIFFs):

- `_standardize_page` — place a scan on an exact letter/legal canvas
- `count_tiff_pages`, `count_pdf_pages`, `should_skip`
- `_convert_pillow`, `convert_one`
- `Action`, `_is_tiff`, `plan_actions`
- `Result`, `run_action`

Changed / added:

- A **thread-pool runner** (`concurrent.futures.ThreadPoolExecutor`) replacing
  the multiprocessing pool + tqdm. It takes a `progress_cb(done, total, label)`
  callback and returns a summary dataclass with counts and a list of failures.
  Thread pool is chosen over multiprocessing because multiprocessing is fragile
  inside a PyInstaller-packaged Windows GUI (child processes can relaunch the
  app); Pillow releases the GIL during decode/encode, so threads still
  parallelize the heavy work.
- A `plan_summary` helper returning counts + total bytes for the plan screen.

Dropped: `argparse`/`main`, all log-file writing (`make_log_paths`, run/failure
logs), `print_summary`, dry-run printing, `check_system_deps`, and the
`only_failures` retry plumbing.

### `src/aa_tool/ui/tiff_converter/` (new tool package)

Mirrors `src/aa_tool/ui/nmslo_segmentor/`:

- `tool.py` — `TiffConverterTool(QtWidgets.QWidget)` with a `QStackedWidget`:
  open screen → plan/result screen. Same shape as `NmsloSegmentorTool`
  (`on_back_to_tools`, `_swap_in`, restart).
- `plan_screen.py` — the plan + editable destination + standardize checkbox +
  Convert button + inline result + "Convert another folder".
- A small **QThread worker** so conversion runs off the UI thread and reports
  progress via signals into the header's existing progress pill
  (`Header.set_progress`).

## Shared changes

- **`src/aa_tool/ui/header.py`** — add an optional `steps: list[str] | None`
  parameter, defaulting to the current Segmentor steps so existing callers are
  unaffected. The converter passes `["1 · Open", "2 · Convert"]`.
- **`src/aa_tool/tools.py`** — register `TIFF_CONVERTER_TOOL`:
  - name: "Batch TIFF to PDF Converter"
  - category: "NM State Land Office"
  - icon: `icons/tiff_converter.svg`
- **`src/aa_tool/resources/icons/tiff_converter.svg`** — new icon.
- **`requirements.txt`** — add `Pillow` and `pypdf`.

## Tests (matching existing style)

- `tests/test_tiff_convert.py` — engine:
  - `plan_actions` mirrors a sample tree (TIFFs → Convert, others → Copy, dirs →
    MakeDir)
  - a real TIFF→PDF round-trip with correct output page count
  - `should_skip` returns True only for a matching existing PDF
  - standardize on/off both produce valid PDFs
  - the thread runner returns a summary with counts and surfaces an induced
    failure
- `tests/test_tiff_converter_tool.py` — UI:
  - open screen builds
  - choosing a folder advances to the plan screen with correct counts
  - tool registration is wired up
- Extend `tests/test_tools.py` and `tests/test_icons.py` for the new registered
  tool and icon.

## Scope (YAGNI — explicitly out for v1)

- Mid-run Cancel button
- Retry-failures flow
- Force re-convert and worker-count controls (baked to sensible defaults:
  standardize on, skip already-done, auto worker count)
