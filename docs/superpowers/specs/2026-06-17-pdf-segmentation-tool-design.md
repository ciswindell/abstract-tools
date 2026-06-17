# AA State Abstract Tool — Design Spec

**Date:** 2026-06-17
**Status:** Approved design, pending implementation plan

## Purpose

An internal Windows desktop tool for processing New Mexico State Land Office lease files. Staff receive a lease file as a folder of PDFs, where each PDF may itself contain several distinct documents. The tool merges those PDFs into one combined PDF, lets a user visually segment it into individual documents, and produces:

1. A **bookmarked combined PDF** (`<lease> File Documents.pdf`) with a bookmark at the first page of every segmented document.
2. An **Excel index** (`<lease> File Documents.xlsx`), one row per segmented document, pre-filled with the data the tool can determine; staff fill in the rest later.

The defining value the tool adds is a reliable **Source** reference on every document row — the file number of the original PDF it came from — so staff can trace any segmented document back to its origin and validate that all source PDFs were included.

## Input structure

```
B11294/                 <- lease folder; folder name = lease number
  0/                    <- subfolder = "Assignment Number" (numeric; not always consecutive, e.g. 3 may be absent)
    368481.pdf          <- file = a "Source"; filename = source file number
    368495.pdf          <- a single PDF may contain multiple documents (e.g. 6 pages -> 3 documents)
    ...
  1/
    368521.pdf
    368522.pdf
  2/ 4/ 5/ ...
```

## Outputs

### Combined PDF — `<lease> File Documents.pdf`
- All source PDFs merged in order: **subfolder (Assignment) numeric ascending, then file number numeric ascending within each subfolder.**
- A bookmark at the first page of every segmented document.
- Bookmark label is computed at export time as `Index# - DocumentType - ReceivedDate`, where DocumentType defaults to `Unknown` and a blank ReceivedDate renders as `NA` (e.g. `1-Unknown-NA`). Bookmarks reflect the state at export; staff refine type/date later in Excel.

### Excel index — `<lease> File Documents.xlsx`
Produced by copying the existing `Template File Documents.xlsx` (sheet "Index") to preserve its exact columns, header, and formatting, then filling one row per segmented document.

Columns (order, as in the template): Source, Assignment Number, Document Group, Bookmark Formula, Index#, Document Type, Received Date, Document Date, Effective Date, Adjudicated Date, Grantor, Grantee, Legal Description, Remarks, Abstract Remarks, Internal Remarks, Action Status.

Tool fills:

| Column | Value |
|---|---|
| Source | originating PDF's file number (same number repeats across rows when one PDF holds multiple documents) |
| Assignment Number | the subfolder number the PDF came from |
| Index# | sequential 1, 2, 3 … across the whole merged file |
| Bookmark Formula | `=E{r}&"-"&F{r}&"-"&IF(G{r}="","NA",TEXT(G{r},"m/d/yyyy"))` (renders `NA` when Received Date is blank) |
| Document Type | `Unknown` |
| Received Date | left blank (cell empty; the formula shows `NA`) |
| All other columns | left blank for staff to complete later |

## User journey (three screens)

1. **Pick lease folder** — user browses to a lease folder (e.g. `B11294`); the folder name is the lease number used for output filenames. One lease per run.
2. **Segmentation screen** — left: scrollable page list, each row tagged with its Source file number and a green bar + "DOC n" badge where a bookmark will land. Right: large preview of the selected page. Above the preview: **Prev / Next** (navigate) and **First Page / Continuation Page** buttons, only the applicable one enabled for the selected page. Keyboard shortcuts mirror the buttons (e.g. F = First Page, C = Continuation, arrows = navigate). Selecting a row only previews it; classifying is a separate explicit button action.
   - Every source PDF's first page is **pre-marked as a First Page** (a new file is at minimum a new document). The user adds First-Page splits inside multi-document PDFs and can demote a boundary to Continuation when one document spans two source files.
3. **Review & export** — summary chips (document count, pages merged, source-file count, assignments present), a save-location picker (defaults to the lease folder), and **Export PDF + Excel**. No detailed table on this screen — the full index lives in the Excel file.

## Internal architecture

Five focused, independently testable units:

- **Ingest** — scans the lease folder; lists subfolders as Assignments (numeric order, alphabetical fallback with a note for non-numeric names) and the PDFs inside each as Sources (same ordering); records page counts. Skips unreadable or non-PDF files and surfaces a visible warning listing what was skipped.
- **Document model** — builds the ordered list of merged pages, each carrying its Source file number and Assignment. Pre-seeds a boundary at each source's first page. Converts the per-page First/Continuation flags into the ordered list of documents (each document = its first page plus following continuation pages, inheriting that first page's Source and Assignment).
- **Segmentation UI** (PySide6/Qt) — renders the screen and reads/writes the document model as the user classifies pages.
- **PDF exporter** (PyMuPDF) — merges the sources in computed order, places a bookmark at each document's first page with the computed label, saves `<lease> File Documents.pdf`.
- **Excel exporter** (openpyxl) — copies the template workbook, fills one row per document, saves `<lease> File Documents.xlsx`.

## Technology

- **Language:** Python.
- **GUI:** PySide6 / Qt (LGPL; free for internal/commercial use). Chosen for clean native handling of image previews, scrolling thumbnail lists, and enabled/disabled buttons on the image-heavy segmentation screen.
- **PDF:** PyMuPDF (fitz) — renders page previews/thumbnails, merges PDFs, writes bookmarks, and tracks per-page provenance (which source file each merged page came from) to populate the Source column reliably.
- **Excel:** openpyxl — copies and fills the existing template to guarantee output matches staff expectations.
- **Packaging:** PyInstaller, producing a single double-click Windows `.exe`. No Python install required on staff machines.

### Why not Django / browser-based
A browser sandboxes local file access, breaking the "point at the lease folder" workflow (staff would have to upload files), and packaging a local web server for double-click use adds moving parts with no benefit for a single-user local tool. A native Qt window has full local file access and a simpler distribution story.

## Build & distribution

PyInstaller cannot cross-compile — it bundles the interpreter and libraries for the OS it runs on. Since development is on Linux but the target is Windows:

- A **GitHub Actions workflow** runs PyInstaller on a `windows-latest` runner to build the `.exe` natively.
- The workflow triggers on push/tag and uploads the `.exe` as a downloadable artifact (and optionally attaches it to a GitHub Release for a clean staff download link).
- Development and testing happen locally on Linux (PDF/Excel logic and the Qt UI both run on Linux); Windows is only needed for the final packaging step, handled by GitHub. The project will be a git repo pushed to GitHub.

## Edge-case decisions

- **Ordering:** numeric by subfolder then file number; alphabetical fallback with a note if a name is non-numeric.
- **Unreadable / non-PDF files:** skipped with a visible warning listing them — nothing silently dropped.
- **Missing subfolder numbers** (e.g. absent `3`): process whatever folders exist; the export summary notes which assignments were present.
- **Multi-document source PDFs:** all resulting documents carry the same Source number (by design, enabling traceback).

## Out of scope (YAGNI)

- Batch processing of multiple lease folders in one run (one lease per run).
- Staff data entry of document type/date/grantor/etc. within the tool (done later in Excel).
- Re-syncing PDF bookmark labels after staff edit the Excel.
