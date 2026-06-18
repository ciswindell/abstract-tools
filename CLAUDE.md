# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Authority — read the constitution first

The project **constitution** at **`.specify/memory/constitution.md`** is the authoritative
source of all principles, conventions, and constraints for this repository, and it
**takes precedence over this file**. Read it and follow it before writing or changing any
code. (An explicit instruction from the user still overrides the constitution.)

This file holds only operational quick-reference and a short architecture map — the
*rules* live in the constitution. Amend principles via the Spec Kit workflow
(`/speckit-constitution`), not by editing this file.

## What this is

A suite of internal **Windows desktop tools** (PySide6/Qt) for land/title work, shipped to staff as a single double-clickable `.exe`. The Python package is `abstract_tools` (pip name `abstract-tools`), living under `src/`. Two tools ship today, both under the "NM State Land Office" category:

- **NMSLO Segmentor** — merges a lease folder's PDFs, lets a user mark the first page of each document, and exports a bookmarked combined PDF plus an Excel index.
- **Batch TIFF to PDF Converter** — mirrors a folder tree, converting each TIFF to a PDF and copying non-TIFFs across unchanged.

## Commands

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

QT_QPA_PLATFORM=offscreen python -m pytest          # run all tests headless (Qt needs this on Linux)
QT_QPA_PLATFORM=offscreen python -m pytest tests/test_model.py            # single file
QT_QPA_PLATFORM=offscreen python -m pytest tests/test_model.py::test_name # single test

python main.py                                      # launch the app locally
```

`QT_QPA_PLATFORM=offscreen` is required to run the GUI tests in a headless environment; omit it only when launching the app on a real display.

## Building the Windows .exe

Built in CI, never locally for distribution. Push a `v*` tag (or run the **Build Windows EXE** Actions workflow manually); it runs the tests, then `pyinstaller --noconfirm abstract_tools.spec`, and uploads `Abstract Tools.exe` as the `abstract-tools` artifact. Staff run it with no Python install.

When a tool adds a bundled resource or a dynamically-imported dependency, update `abstract_tools.spec` — `datas` for resource files, `hiddenimports` for libraries loaded at runtime (e.g. `PIL.TiffImagePlugin`/`PIL.JpegImagePlugin`/`PIL.PdfImagePlugin`, `pypdf`). See constitution principle IV (Verify the Real Artifact).

## Architecture (orientation map)

### Multi-tool shell

`tools.py` is the **tool registry**: each tool is a frozen `Tool` dataclass (`id`, `name`, `description`, `category`, `icon`, and a `build(on_back_to_tools) -> QWidget` callback) appended to the `TOOLS` list. `HomeBoard` renders them grouped by category; `MainWindow` (a `QStackedWidget`) calls the selected tool's `build` callback and swaps the returned widget in. Before removing a tool widget, `MainWindow` calls `shutdown()` on it if the method exists (the teardown contract for tools that own background threads).

### Tool structure

Each tool is a subpackage under `src/abstract_tools/ui/<tool>/` whose `tool.py` exposes a `QWidget` taking the `on_back_to_tools` callback. The widget holds its own internal `QStackedWidget` of screens (open → work → export/result) and manages swapping/cleanup between them. The shared `ui/header.py` `Header` renders the back link, context label, and step chips (`steps=` overrides the default segmentor steps).

### NMSLO Segmentor pipeline (the reference data flow)

`ingest.scan_lease_folder()` walks a lease folder's subfolders (numeric-aware sort), producing `SourcePdf`s into an `IngestResult` (with a `skipped` list for non-PDF/unreadable files) → `model.SegmentationModel` flattens all source pages into a merged sequence and tracks per-page first-page/boundary flags, exposing `documents()` which groups pages into `Document`s. A source PDF's *first* page is always a document boundary (enforced in `set_continuation`). → `export.run_export()` fans out to `pdf_export.export_pdf` (bookmarked combined PDF via PyMuPDF/`fitz`) and `excel_export.export_excel` (index, seeded from the bundled Excel template).

### Resources & theme

All bundled assets (Excel template, fonts, SVG icons) are loaded through `resources.resource_path()`, which resolves both from source (`src/abstract_tools/resources/`) and from a PyInstaller one-file bundle (`sys._MEIPASS`). `ui/theme.py` is a single shared QSS stylesheet ("archival paper" palette + bundled fonts) applied app-wide; widgets are styled by `objectName` (e.g. `"primary"`, `"h1"`, `"screen"`, `"header"`), so new widgets pick up styling by setting the matching object name.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
<!-- SPECKIT END -->
