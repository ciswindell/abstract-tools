# AA State Abstract Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a double-click Windows desktop tool that merges a lease folder's PDFs, lets a user segment them into documents, and exports a bookmarked combined PDF plus an Excel index.

**Architecture:** Pure-Python core (ingest → document model → PDF/Excel exporters) that is fully unit-tested headlessly, with a thin PySide6/Qt UI layer (three screens) on top. PyMuPDF does all PDF work and per-page provenance tracking; openpyxl writes the Excel index. PyInstaller packages a single `.exe`, built on a `windows-latest` GitHub Actions runner.

**Tech Stack:** Python 3.12, PySide6, PyMuPDF (`pymupdf`/`fitz`), openpyxl, pytest, pytest-qt, PyInstaller.

## Global Constraints

- Distribution target is **Windows**; the `.exe` is built via GitHub Actions on `windows-latest` (PyInstaller cannot cross-compile from Linux).
- Python version: **3.12**.
- **TDD throughout:** failing test first, then minimal code. Commit after each green task.
- Tests use **synthetic in-test PDF fixtures only** (built with PyMuPDF). The `example/` folder is **never** used in automated tests and is gitignored.
- Output filenames exactly: `<lease> File Documents.pdf` and `<lease> File Documents.xlsx`, where `<lease>` is the lease folder's name.
- Excel sheet name is exactly `Index`. Columns in this exact order: `Source`, `Assignment Number`, `Document Group`, `Bookmark Formula`, `Index#`, `Document Type`, `Received Date`, `Document Date`, `Effective Date`, `Adjudicated Date`, `Grantor`, `Grantee`, `Legal Description`, `Remarks`, `Abstract Remarks`, `Internal Remarks`, `Action Status`.
- Bookmark Formula cell for data row `r`: `=E{r}&"-"&F{r}&"-"&IF(G{r}="","NA",TEXT(G{r},"m/d/yyyy"))`.
- PDF bookmark label text: `<Index#>-<DocumentType>-<ReceivedDate>` where DocumentType defaults to `Unknown` and a missing ReceivedDate renders `NA` (e.g. `1-Unknown-NA`).
- Merge order: subfolder (Assignment) numeric ascending, then file number numeric ascending within each; non-numeric names fall back to case-insensitive alphabetical.
- A document's `Source` and `Assignment` are inherited from its first page. Multiple documents from one source PDF share that Source number.
- The very first merged page is always a First Page and cannot be demoted to Continuation.

**Excel approach note:** The exporter copies a bundled template, `src/aa_tool/resources/Template File Documents.xlsx` (already committed — a cleaned copy of the real template: header row + column widths + frozen header, no data rows), then fills one row per document starting at row 2. This preserves the staff's exact column order, widths, and frozen header. The template is loaded via a resource-path helper that works both from source and from inside the PyInstaller bundle.

---

### Task 1: Project scaffolding and synthetic PDF fixtures

**Files:**
- Create: `requirements.txt`
- Create: `pyproject.toml`
- Create: `src/aa_tool/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Test: `tests/test_fixtures.py`

**Interfaces:**
- Consumes: nothing.
- Produces: pytest fixture `make_pdf(tmp_path)` → a factory `make_pdf(name: str, pages: int, parent: Path | None = None) -> Path` that writes a synthetic PDF with the given page count (each page shows its own page number) and returns its path.

- [ ] **Step 1: Create `requirements.txt`**

```
PySide6==6.7.*
pymupdf==1.24.*
openpyxl==3.1.*
pytest==8.*
pytest-qt==4.*
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "aa-state-abstract-tool"
version = "0.1.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 3: Create empty `src/aa_tool/__init__.py` and `tests/__init__.py`**

Both files are empty.

- [ ] **Step 4: Write the fixture factory in `tests/conftest.py`**

```python
from pathlib import Path

import fitz  # PyMuPDF
import pytest


@pytest.fixture
def make_pdf(tmp_path):
    """Factory that writes a synthetic multi-page PDF and returns its path."""

    def _make(name: str, pages: int, parent: Path | None = None) -> Path:
        folder = parent if parent is not None else tmp_path
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / name
        doc = fitz.open()
        for i in range(pages):
            page = doc.new_page()
            page.insert_text((72, 72), f"{path.stem} page {i + 1}")
        doc.save(path)
        doc.close()
        return path

    return _make
```

- [ ] **Step 5: Write the failing test `tests/test_fixtures.py`**

```python
import fitz


def test_make_pdf_creates_pdf_with_page_count(make_pdf):
    path = make_pdf("368481.pdf", 3)
    assert path.exists()
    with fitz.open(path) as doc:
        assert doc.page_count == 3
```

- [ ] **Step 6: Run the test**

Run: `python -m pytest tests/test_fixtures.py -v`
Expected: PASS (this verifies the toolchain and fixtures; install deps first with `pip install -r requirements.txt` inside a venv).

- [ ] **Step 7: Commit**

```bash
git add requirements.txt pyproject.toml src/aa_tool/__init__.py tests/__init__.py tests/conftest.py tests/test_fixtures.py
git commit -m "chore: project scaffolding and synthetic PDF fixtures"
```

---

### Task 2: Ingest — scan a lease folder into ordered sources

**Files:**
- Create: `src/aa_tool/ingest.py`
- Test: `tests/test_ingest.py`

**Interfaces:**
- Consumes: `make_pdf` fixture.
- Produces:
  - `@dataclass(frozen=True) SourcePdf(path: Path, file_number: str, assignment: str, page_count: int)`
  - `@dataclass IngestResult(lease_number: str, sources: list[SourcePdf], skipped: list[tuple[Path, str]])`
  - `scan_lease_folder(folder: Path) -> IngestResult`

- [ ] **Step 1: Write the failing test for ordering and provenance**

```python
from pathlib import Path

from aa_tool.ingest import scan_lease_folder


def test_scan_orders_by_assignment_then_file_number(make_pdf, tmp_path):
    lease = tmp_path / "B11294"
    make_pdf("368495.pdf", 6, parent=lease / "0")
    make_pdf("368481.pdf", 1, parent=lease / "0")
    make_pdf("368521.pdf", 1, parent=lease / "1")

    result = scan_lease_folder(lease)

    assert result.lease_number == "B11294"
    ordered = [(s.assignment, s.file_number, s.page_count) for s in result.sources]
    assert ordered == [
        ("0", "368481", 1),
        ("0", "368495", 6),
        ("1", "368521", 1),
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ingest.py::test_scan_orders_by_assignment_then_file_number -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aa_tool.ingest'`.

- [ ] **Step 3: Write `src/aa_tool/ingest.py`**

```python
from dataclasses import dataclass, field
from pathlib import Path

import fitz


@dataclass(frozen=True)
class SourcePdf:
    path: Path
    file_number: str
    assignment: str
    page_count: int


@dataclass
class IngestResult:
    lease_number: str
    sources: list[SourcePdf]
    skipped: list[tuple[Path, str]] = field(default_factory=list)


def _numeric_key(name: str):
    """Sort numerically when possible, else case-insensitive alphabetical.

    Returns (is_non_numeric, numeric_value, lowercased_name) so all-numeric
    names sort ahead of and independently from non-numeric ones.
    """
    try:
        return (0, int(name), "")
    except ValueError:
        return (1, 0, name.lower())


def scan_lease_folder(folder: Path) -> IngestResult:
    folder = Path(folder)
    sources: list[SourcePdf] = []
    skipped: list[tuple[Path, str]] = []

    subfolders = sorted(
        (p for p in folder.iterdir() if p.is_dir()),
        key=lambda p: _numeric_key(p.name),
    )
    for sub in subfolders:
        files = sorted(
            (p for p in sub.iterdir() if p.is_file()),
            key=lambda p: _numeric_key(p.stem),
        )
        for f in files:
            if f.suffix.lower() != ".pdf":
                skipped.append((f, "not a PDF"))
                continue
            try:
                with fitz.open(f) as doc:
                    page_count = doc.page_count
            except Exception as exc:  # noqa: BLE001 - report any unreadable file
                skipped.append((f, f"unreadable: {exc}"))
                continue
            sources.append(
                SourcePdf(
                    path=f,
                    file_number=f.stem,
                    assignment=sub.name,
                    page_count=page_count,
                )
            )

    return IngestResult(lease_number=folder.name, sources=sources, skipped=skipped)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ingest.py::test_scan_orders_by_assignment_then_file_number -v`
Expected: PASS.

- [ ] **Step 5: Write the failing test for skipping non-PDF and unreadable files**

```python
def test_scan_skips_non_pdf_and_unreadable(make_pdf, tmp_path):
    lease = tmp_path / "B11294"
    make_pdf("368481.pdf", 1, parent=lease / "0")
    (lease / "0" / "notes.txt").write_text("hello")
    (lease / "0" / "broken.pdf").write_bytes(b"not really a pdf")

    result = scan_lease_folder(lease)

    assert [s.file_number for s in result.sources] == ["368481"]
    skipped_names = sorted(p.name for p, _ in result.skipped)
    assert skipped_names == ["broken.pdf", "notes.txt"]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_ingest.py -v`
Expected: both tests PASS. (No new code needed — the implementation already handles this.)

- [ ] **Step 7: Commit**

```bash
git add src/aa_tool/ingest.py tests/test_ingest.py
git commit -m "feat: ingest lease folder into ordered sources with skip reporting"
```

---

### Task 3: Document model — merged pages, boundaries, documents

**Files:**
- Create: `src/aa_tool/model.py`
- Test: `tests/test_model.py`

**Interfaces:**
- Consumes: `SourcePdf` from `aa_tool.ingest`.
- Produces:
  - `@dataclass(frozen=True) MergedPage(global_index: int, source: SourcePdf, source_page_index: int)`
  - `@dataclass Document(index: int, pages: list[MergedPage])` with read-only properties `source: str` (first page's `source.file_number`), `assignment: str` (first page's `source.assignment`), `first_global_index: int` (first page's `global_index`).
  - `class SegmentationModel(sources: list[SourcePdf])` with: attribute `pages: list[MergedPage]`; method `is_first_page(global_index: int) -> bool`; `set_first_page(global_index: int) -> None`; `set_continuation(global_index: int) -> None` (raises `ValueError` for global_index 0); `documents() -> list[Document]`.

- [ ] **Step 1: Write the failing test for pre-seeded boundaries and documents**

```python
from aa_tool.ingest import SourcePdf
from aa_tool.model import SegmentationModel


def _src(num, assignment, pages):
    from pathlib import Path
    return SourcePdf(Path(f"{num}.pdf"), num, assignment, pages)


def test_preseeds_boundary_at_each_source_start():
    sources = [_src("368481", "0", 2), _src("368495", "0", 3)]
    model = SegmentationModel(sources)

    assert len(model.pages) == 5
    # First page of each source is a boundary; interior pages are not.
    assert [model.is_first_page(i) for i in range(5)] == [True, False, True, False, False]

    docs = model.documents()
    assert [(d.index, d.source, d.assignment, d.first_global_index) for d in docs] == [
        (1, "368481", "0", 0),
        (2, "368495", "0", 2),
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_model.py::test_preseeds_boundary_at_each_source_start -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aa_tool.model'`.

- [ ] **Step 3: Write `src/aa_tool/model.py`**

```python
from dataclasses import dataclass

from aa_tool.ingest import SourcePdf


@dataclass(frozen=True)
class MergedPage:
    global_index: int
    source: SourcePdf
    source_page_index: int


@dataclass
class Document:
    index: int
    pages: list[MergedPage]

    @property
    def source(self) -> str:
        return self.pages[0].source.file_number

    @property
    def assignment(self) -> str:
        return self.pages[0].source.assignment

    @property
    def first_global_index(self) -> int:
        return self.pages[0].global_index


class SegmentationModel:
    def __init__(self, sources: list[SourcePdf]):
        self.pages: list[MergedPage] = []
        self._is_first: list[bool] = []
        gi = 0
        for source in sources:
            for spi in range(source.page_count):
                self.pages.append(MergedPage(gi, source, spi))
                self._is_first.append(spi == 0)
                gi += 1
        if self._is_first:
            self._is_first[0] = True  # first page is always a boundary

    def is_first_page(self, global_index: int) -> bool:
        return self._is_first[global_index]

    def set_first_page(self, global_index: int) -> None:
        self._is_first[global_index] = True

    def set_continuation(self, global_index: int) -> None:
        if global_index == 0:
            raise ValueError("The first page cannot be a continuation page")
        self._is_first[global_index] = False

    def documents(self) -> list[Document]:
        docs: list[Document] = []
        for page, first in zip(self.pages, self._is_first):
            if first:
                docs.append(Document(index=len(docs) + 1, pages=[page]))
            else:
                docs[-1].pages.append(page)
        return docs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_model.py::test_preseeds_boundary_at_each_source_start -v`
Expected: PASS.

- [ ] **Step 5: Write the failing test for splitting and merging boundaries**

```python
import pytest

from aa_tool.ingest import SourcePdf
from aa_tool.model import SegmentationModel
from pathlib import Path


def test_split_inside_source_and_merge_across_sources():
    sources = [SourcePdf(Path("368495.pdf"), "368495", "0", 4),
               SourcePdf(Path("368521.pdf"), "368521", "1", 1)]
    model = SegmentationModel(sources)

    # Split 368495 into two documents at its page index 2 (global 2).
    model.set_first_page(2)
    # Merge 368521 into the previous document (document spans two sources).
    model.set_continuation(4)

    docs = model.documents()
    assert [(d.index, d.source, d.assignment, [p.global_index for p in d.pages]) for d in docs] == [
        (1, "368495", "0", [0, 1]),
        (2, "368495", "0", [2, 3, 4]),
    ]


def test_first_page_cannot_be_continuation():
    sources = [SourcePdf(Path("368495.pdf"), "368495", "0", 2)]
    model = SegmentationModel(sources)
    with pytest.raises(ValueError):
        model.set_continuation(0)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_model.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add src/aa_tool/model.py tests/test_model.py
git commit -m "feat: segmentation document model with boundaries"
```

---

### Task 4: Bookmark label builder

**Files:**
- Create: `src/aa_tool/labels.py`
- Test: `tests/test_labels.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `build_bookmark_label(index: int, doc_type: str = "Unknown", received_date: "datetime.date | None" = None) -> str`.

- [ ] **Step 1: Write the failing test**

```python
from datetime import date

from aa_tool.labels import build_bookmark_label


def test_label_with_blank_date_renders_na():
    assert build_bookmark_label(1) == "1-Unknown-NA"


def test_label_with_date_renders_m_d_yyyy():
    assert build_bookmark_label(5, "Deed", date(2020, 3, 7)) == "5-Deed-3/7/2020"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_labels.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aa_tool.labels'`.

- [ ] **Step 3: Write `src/aa_tool/labels.py`**

```python
from datetime import date


def build_bookmark_label(
    index: int, doc_type: str = "Unknown", received_date: date | None = None
) -> str:
    if received_date is None:
        received = "NA"
    else:
        received = f"{received_date.month}/{received_date.day}/{received_date.year}"
    return f"{index}-{doc_type}-{received}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_labels.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/aa_tool/labels.py tests/test_labels.py
git commit -m "feat: bookmark label builder"
```

---

### Task 5: PDF exporter — merge sources and add bookmarks

**Files:**
- Create: `src/aa_tool/pdf_export.py`
- Test: `tests/test_pdf_export.py`

**Interfaces:**
- Consumes: `SourcePdf` (ingest), `Document` (model), `build_bookmark_label` (labels).
- Produces: `export_pdf(sources: list[SourcePdf], documents: list[Document], out_path: Path) -> None`.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import fitz

from aa_tool.ingest import scan_lease_folder
from aa_tool.model import SegmentationModel
from aa_tool.pdf_export import export_pdf


def test_export_pdf_merges_and_bookmarks(make_pdf, tmp_path):
    lease = tmp_path / "B11294"
    make_pdf("368481.pdf", 2, parent=lease / "0")
    make_pdf("368495.pdf", 3, parent=lease / "0")

    result = scan_lease_folder(lease)
    model = SegmentationModel(result.sources)
    model.set_first_page(3)  # split second source into two documents
    docs = model.documents()

    out = tmp_path / "B11294 File Documents.pdf"
    export_pdf(result.sources, docs, out)

    with fitz.open(out) as merged:
        assert merged.page_count == 5
        toc = merged.get_toc()
    # [level, title, 1-based page]
    assert toc == [
        [1, "1-Unknown-NA", 1],
        [1, "2-Unknown-NA", 3],
        [1, "3-Unknown-NA", 4],
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pdf_export.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aa_tool.pdf_export'`.

- [ ] **Step 3: Write `src/aa_tool/pdf_export.py`**

```python
from pathlib import Path

import fitz

from aa_tool.ingest import SourcePdf
from aa_tool.labels import build_bookmark_label
from aa_tool.model import Document


def export_pdf(
    sources: list[SourcePdf], documents: list[Document], out_path: Path
) -> None:
    merged = fitz.open()
    try:
        for source in sources:
            with fitz.open(source.path) as src:
                merged.insert_pdf(src)

        toc = [
            [1, build_bookmark_label(doc.index), doc.first_global_index + 1]
            for doc in documents
        ]
        merged.set_toc(toc)
        merged.save(str(out_path))
    finally:
        merged.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pdf_export.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/aa_tool/pdf_export.py tests/test_pdf_export.py
git commit -m "feat: PDF exporter merges sources and writes bookmarks"
```

---

### Task 6: Resource-path helper and Excel exporter (copies bundled template)

**Files:**
- Create: `src/aa_tool/resources.py`
- Create: `src/aa_tool/excel_export.py`
- Existing (already committed): `src/aa_tool/resources/Template File Documents.xlsx`
- Test: `tests/test_resources.py`
- Test: `tests/test_excel_export.py`

**Interfaces:**
- Consumes: `Document` (model); the bundled template file.
- Produces:
  - `resource_path(name: str) -> Path` in `aa_tool.resources` — returns the absolute path to a bundled resource, working both from source (`src/aa_tool/resources/<name>`) and from a PyInstaller one-file bundle (`sys._MEIPASS/aa_tool/resources/<name>`).
  - module constant `COLUMNS: list[str]` (the 17 headers in order, for column-index reference).
  - `TEMPLATE_NAME = "Template File Documents.xlsx"`.
  - `export_excel(documents: list[Document], out_path: Path) -> None` — copies the bundled template, fills one row per document starting at row 2, saves to `out_path`.

- [ ] **Step 1: Write the failing test for `resource_path` `tests/test_resources.py`**

```python
from aa_tool.resources import resource_path


def test_resource_path_points_at_bundled_template():
    path = resource_path("Template File Documents.xlsx")
    assert path.exists()
    assert path.name == "Template File Documents.xlsx"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_resources.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aa_tool.resources'`.

Note: `aa_tool.resources` is a *module* (`resources.py`); the bundled file lives in the `resources/` *directory* beside it. Both can coexist — Python imports the `.py` file, and the helper reads from the directory by path.

- [ ] **Step 3: Write `src/aa_tool/resources.py`**

```python
import sys
from pathlib import Path


def resource_path(name: str) -> Path:
    """Absolute path to a bundled resource.

    Works from source (src/aa_tool/resources/<name>) and from a PyInstaller
    one-file bundle, where data files are unpacked under sys._MEIPASS.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base is not None:
        return Path(base) / "aa_tool" / "resources" / name
    return Path(__file__).resolve().parent / "resources" / name
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_resources.py -v`
Expected: PASS.

- [ ] **Step 5: Write the failing test for the Excel exporter `tests/test_excel_export.py`**

```python
from pathlib import Path

from openpyxl import load_workbook

from aa_tool.ingest import SourcePdf
from aa_tool.model import Document, MergedPage
from aa_tool.excel_export import export_excel, COLUMNS


def _doc(index, file_number, assignment):
    src = SourcePdf(Path(f"{file_number}.pdf"), file_number, assignment, 1)
    page = MergedPage(index - 1, src, 0)
    return Document(index=index, pages=[page])


def test_export_excel_uses_template_headers_and_fills_rows(tmp_path):
    docs = [_doc(1, "368481", "0"), _doc(2, "368495", "0"), _doc(3, "368495", "0")]
    out = tmp_path / "B11294 File Documents.xlsx"
    export_excel(docs, out)

    wb = load_workbook(out)
    ws = wb["Index"]
    # Headers come from the bundled template, in the exact order.
    assert [c.value for c in ws[1]] == COLUMNS
    assert ws.title == "Index"
    # Frozen header preserved from template.
    assert ws.freeze_panes == "A2"
    # Row 2 (first document)
    assert ws.cell(row=2, column=1).value == 368481          # Source (numeric)
    assert ws.cell(row=2, column=2).value == 0               # Assignment Number
    assert ws.cell(row=2, column=4).value == '=E2&"-"&F2&"-"&IF(G2="","NA",TEXT(G2,"m/d/yyyy"))'
    assert ws.cell(row=2, column=5).value == 1               # Index#
    assert ws.cell(row=2, column=6).value == "Unknown"       # Document Type
    assert ws.cell(row=2, column=7).value is None            # Received Date blank
    # Row 4 (third document, same source repeats)
    assert ws.cell(row=4, column=1).value == 368495
    assert ws.cell(row=4, column=5).value == 3
    # No stray data rows beyond the documents.
    assert ws.max_row == 4
```

- [ ] **Step 6: Run test to verify it fails**

Run: `python -m pytest tests/test_excel_export.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aa_tool.excel_export'`.

- [ ] **Step 7: Write `src/aa_tool/excel_export.py`**

```python
from pathlib import Path

from openpyxl import load_workbook

from aa_tool.model import Document
from aa_tool.resources import resource_path

TEMPLATE_NAME = "Template File Documents.xlsx"

COLUMNS = [
    "Source",
    "Assignment Number",
    "Document Group",
    "Bookmark Formula",
    "Index#",
    "Document Type",
    "Received Date",
    "Document Date",
    "Effective Date",
    "Adjudicated Date",
    "Grantor",
    "Grantee",
    "Legal Description",
    "Remarks",
    "Abstract Remarks",
    "Internal Remarks",
    "Action Status",
]


def _as_number(value: str):
    """Return an int when the string is all digits, else the original string."""
    return int(value) if value.isdigit() else value


def export_excel(documents: list[Document], out_path: Path) -> None:
    wb = load_workbook(resource_path(TEMPLATE_NAME))
    ws = wb["Index"]

    for doc in documents:
        r = doc.index + 1  # header occupies row 1
        ws.cell(row=r, column=1, value=_as_number(doc.source))
        ws.cell(row=r, column=2, value=_as_number(doc.assignment))
        ws.cell(
            row=r,
            column=4,
            value=f'=E{r}&"-"&F{r}&"-"&IF(G{r}="","NA",TEXT(G{r},"m/d/yyyy"))',
        )
        ws.cell(row=r, column=5, value=doc.index)
        ws.cell(row=r, column=6, value="Unknown")

    wb.save(out_path)
```

- [ ] **Step 8: Run test to verify it passes**

Run: `python -m pytest tests/test_excel_export.py tests/test_resources.py -v`
Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add src/aa_tool/resources.py src/aa_tool/excel_export.py tests/test_resources.py tests/test_excel_export.py
git commit -m "feat: Excel exporter copies bundled template; resource-path helper"
```

---

### Task 7: Page render helper (PDF page → PNG bytes)

**Files:**
- Create: `src/aa_tool/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: nothing (takes a path + page index).
- Produces: `render_page_png(path: Path, page_index: int, zoom: float = 1.5) -> bytes`.

- [ ] **Step 1: Write the failing test**

```python
from aa_tool.render import render_page_png


def test_render_returns_png_bytes(make_pdf):
    path = make_pdf("368481.pdf", 1)
    data = render_page_png(path, 0)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"  # PNG signature
    assert len(data) > 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_render.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aa_tool.render'`.

- [ ] **Step 3: Write `src/aa_tool/render.py`**

```python
from pathlib import Path

import fitz


def render_page_png(path: Path, page_index: int, zoom: float = 1.5) -> bytes:
    with fitz.open(path) as doc:
        page = doc[page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        return pix.tobytes("png")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_render.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/aa_tool/render.py tests/test_render.py
git commit -m "feat: PDF page render helper"
```

---

### Task 8: Export orchestration — filenames and summary

**Files:**
- Create: `src/aa_tool/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: `IngestResult` (ingest), `Document` (model), `export_pdf`, `export_excel`.
- Produces:
  - `@dataclass ExportSummary(document_count: int, page_count: int, source_count: int, assignments: list[str], pdf_path: Path, xlsx_path: Path)`
  - `build_summary(result: IngestResult, documents: list[Document]) -> tuple[int, int, int, list[str]]` returning (document_count, page_count, source_count, sorted unique assignments).
  - `run_export(result: IngestResult, documents: list[Document], out_dir: Path) -> ExportSummary` which writes both files named `<lease> File Documents.pdf/.xlsx` into `out_dir` and returns the summary.

- [ ] **Step 1: Write the failing test**

```python
from aa_tool.ingest import scan_lease_folder
from aa_tool.model import SegmentationModel
from aa_tool.export import run_export


def test_run_export_writes_named_files_and_summary(make_pdf, tmp_path):
    lease = tmp_path / "B11294"
    make_pdf("368481.pdf", 1, parent=lease / "0")
    make_pdf("368495.pdf", 3, parent=lease / "0")
    make_pdf("368521.pdf", 1, parent=lease / "1")

    result = scan_lease_folder(lease)
    model = SegmentationModel(result.sources)
    docs = model.documents()

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    summary = run_export(result, docs, out_dir)

    assert (out_dir / "B11294 File Documents.pdf").exists()
    assert (out_dir / "B11294 File Documents.xlsx").exists()
    assert summary.document_count == 3
    assert summary.page_count == 5
    assert summary.source_count == 3
    assert summary.assignments == ["0", "1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_export.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aa_tool.export'`.

- [ ] **Step 3: Write `src/aa_tool/export.py`**

```python
from dataclasses import dataclass
from pathlib import Path

from aa_tool.excel_export import export_excel
from aa_tool.ingest import IngestResult
from aa_tool.model import Document
from aa_tool.pdf_export import export_pdf


@dataclass
class ExportSummary:
    document_count: int
    page_count: int
    source_count: int
    assignments: list[str]
    pdf_path: Path
    xlsx_path: Path


def build_summary(result: IngestResult, documents: list[Document]):
    page_count = sum(s.page_count for s in result.sources)
    assignments = sorted({s.assignment for s in result.sources})
    return (len(documents), page_count, len(result.sources), assignments)


def run_export(
    result: IngestResult, documents: list[Document], out_dir: Path
) -> ExportSummary:
    out_dir = Path(out_dir)
    base = f"{result.lease_number} File Documents"
    pdf_path = out_dir / f"{base}.pdf"
    xlsx_path = out_dir / f"{base}.xlsx"

    export_pdf(result.sources, documents, pdf_path)
    export_excel(documents, xlsx_path)

    doc_count, page_count, source_count, assignments = build_summary(result, documents)
    return ExportSummary(
        document_count=doc_count,
        page_count=page_count,
        source_count=source_count,
        assignments=assignments,
        pdf_path=pdf_path,
        xlsx_path=xlsx_path,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_export.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/aa_tool/export.py tests/test_export.py
git commit -m "feat: export orchestration with named files and summary"
```

---

### Task 9: Qt app shell and folder-picker screen

**Files:**
- Create: `src/aa_tool/ui/__init__.py`
- Create: `src/aa_tool/ui/main_window.py`
- Create: `main.py`
- Test: `tests/test_ui_main_window.py`

**Interfaces:**
- Consumes: `scan_lease_folder` (ingest), `SegmentationModel` (model).
- Produces:
  - `class MainWindow(QtWidgets.QMainWindow)` with a `QtWidgets.QStackedWidget` and method `load_lease(folder: Path) -> None` that runs ingest, builds a `SegmentationModel`, and shows the segmentation screen (added in Task 10). For this task, `load_lease` stores `self.ingest_result` and `self.model` and switches to a placeholder segmentation page.
  - `main()` entry function that creates the `QApplication`, shows `MainWindow`, and runs the event loop.

- [ ] **Step 1: Write the failing test (uses pytest-qt; runs headless via offscreen platform)**

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aa_tool.ui.main_window import MainWindow


def test_load_lease_builds_model(qtbot, make_pdf, tmp_path):
    lease = tmp_path / "B11294"
    make_pdf("368481.pdf", 2, parent=lease / "0")

    window = MainWindow()
    qtbot.addWidget(window)
    window.load_lease(lease)

    assert window.ingest_result.lease_number == "B11294"
    assert len(window.model.pages) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_ui_main_window.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aa_tool.ui.main_window'`.

- [ ] **Step 3: Create empty `src/aa_tool/ui/__init__.py`, then write `src/aa_tool/ui/main_window.py`**

```python
from pathlib import Path

from PySide6 import QtWidgets

from aa_tool.ingest import scan_lease_folder
from aa_tool.model import SegmentationModel


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AA State Abstract Tool")
        self.resize(1100, 800)

        self.stack = QtWidgets.QStackedWidget()
        self.setCentralWidget(self.stack)

        self.ingest_result = None
        self.model: SegmentationModel | None = None

        self._build_folder_screen()

    def _build_folder_screen(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.addStretch()
        label = QtWidgets.QLabel("Choose a lease folder to begin.")
        label.setAlignment(QtWidgets.Qt.AlignmentFlag.AlignCenter)
        button = QtWidgets.QPushButton("Choose lease folder…")
        button.clicked.connect(self._choose_folder)
        layout.addWidget(label)
        layout.addWidget(button, alignment=QtWidgets.Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        self.folder_index = self.stack.addWidget(page)

        # Placeholder; replaced in Task 10 by the real segmentation screen.
        self._segmentation_placeholder = QtWidgets.QLabel("Segmentation screen")
        self.segmentation_index = self.stack.addWidget(self._segmentation_placeholder)

    def _choose_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose lease folder")
        if folder:
            self.load_lease(Path(folder))

    def load_lease(self, folder: Path) -> None:
        self.ingest_result = scan_lease_folder(folder)
        self.model = SegmentationModel(self.ingest_result.sources)
        self.stack.setCurrentIndex(self.segmentation_index)


def main() -> None:
    import sys

    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
```

- [ ] **Step 4: Write `main.py` (PyInstaller entry point)**

```python
from aa_tool.ui.main_window import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_ui_main_window.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/aa_tool/ui/__init__.py src/aa_tool/ui/main_window.py main.py tests/test_ui_main_window.py
git commit -m "feat: Qt app shell and lease folder picker"
```

---

### Task 10: Segmentation screen

**Files:**
- Create: `src/aa_tool/ui/segmentation_screen.py`
- Modify: `src/aa_tool/ui/main_window.py` (replace the placeholder with the real screen)
- Test: `tests/test_ui_segmentation.py`

**Interfaces:**
- Consumes: `SegmentationModel`, `MergedPage` (model); `render_page_png` (render).
- Produces:
  - `class SegmentationScreen(QtWidgets.QWidget)` constructed with `(model: SegmentationModel, on_continue: Callable[[], None])`. Public methods used by tests: `select_page(global_index: int) -> None`; `mark_first_page() -> None`; `mark_continuation() -> None`; `refresh_list() -> None`. Attributes: `page_list` (`QtWidgets.QListWidget`), `first_button`, `continuation_button`, `continue_button` (`QtWidgets.QPushButton`).
  - The list shows one row per page labeled `p{n} · {source.file_number}` with a "DOC k" suffix on first pages. `first_button` is disabled when the selected page is already a first page; `continuation_button` is disabled when the page is a first page OR is global index 0.

- [ ] **Step 1: Write the failing test for button enable/disable logic and reclassification**

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from aa_tool.ingest import SourcePdf
from aa_tool.model import SegmentationModel
from aa_tool.ui.segmentation_screen import SegmentationScreen


def _model():
    sources = [SourcePdf(Path("368495.pdf"), "368495", "0", 4)]
    return SegmentationModel(sources)


def test_buttons_reflect_selected_page(qtbot):
    model = _model()
    screen = SegmentationScreen(model, on_continue=lambda: None)
    qtbot.addWidget(screen)

    screen.select_page(0)  # first page of source, and global 0
    assert screen.first_button.isEnabled() is False
    assert screen.continuation_button.isEnabled() is False

    screen.select_page(1)  # interior continuation page
    assert screen.first_button.isEnabled() is True
    assert screen.continuation_button.isEnabled() is False

    screen.mark_first_page()  # promote page 1 to a document start
    assert model.is_first_page(1) is True
    assert screen.first_button.isEnabled() is False
    assert screen.continuation_button.isEnabled() is True

    screen.mark_continuation()  # demote it back
    assert model.is_first_page(1) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_ui_segmentation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aa_tool.ui.segmentation_screen'`.

- [ ] **Step 3: Write `src/aa_tool/ui/segmentation_screen.py`**

```python
from collections.abc import Callable

from PySide6 import QtCore, QtGui, QtWidgets

from aa_tool.model import SegmentationModel
from aa_tool.render import render_page_png


class SegmentationScreen(QtWidgets.QWidget):
    def __init__(self, model: SegmentationModel, on_continue: Callable[[], None]):
        super().__init__()
        self.model = model
        self.on_continue = on_continue
        self.selected_index = 0

        root = QtWidgets.QHBoxLayout(self)

        self.page_list = QtWidgets.QListWidget()
        self.page_list.currentRowChanged.connect(self._on_row_changed)
        root.addWidget(self.page_list, 1)

        right = QtWidgets.QVBoxLayout()
        root.addLayout(right, 3)

        button_bar = QtWidgets.QHBoxLayout()
        self.prev_button = QtWidgets.QPushButton("◀ Prev")
        self.next_button = QtWidgets.QPushButton("Next ▶")
        self.first_button = QtWidgets.QPushButton("✚ First Page")
        self.continuation_button = QtWidgets.QPushButton("↳ Continuation Page")
        self.prev_button.clicked.connect(lambda: self.select_page(self.selected_index - 1))
        self.next_button.clicked.connect(lambda: self.select_page(self.selected_index + 1))
        self.first_button.clicked.connect(self.mark_first_page)
        self.continuation_button.clicked.connect(self.mark_continuation)
        button_bar.addWidget(self.prev_button)
        button_bar.addWidget(self.next_button)
        button_bar.addStretch()
        button_bar.addWidget(self.first_button)
        button_bar.addWidget(self.continuation_button)
        right.addLayout(button_bar)

        self.preview = QtWidgets.QLabel()
        self.preview.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(400)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.preview)
        right.addWidget(scroll, 1)

        self.continue_button = QtWidgets.QPushButton("Continue to export ▶")
        self.continue_button.clicked.connect(lambda: self.on_continue())
        right.addWidget(self.continue_button, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        # Keyboard shortcuts mirror the buttons.
        QtGui.QShortcut(QtGui.QKeySequence("F"), self, self.mark_first_page)
        QtGui.QShortcut(QtGui.QKeySequence("C"), self, self.mark_continuation)

        self.refresh_list()
        if self.model.pages:
            self.select_page(0)

    def refresh_list(self) -> None:
        self.page_list.blockSignals(True)
        self.page_list.clear()
        doc_number = 0
        for page in self.model.pages:
            first = self.model.is_first_page(page.global_index)
            if first:
                doc_number += 1
            text = f"p{page.global_index + 1} · {page.source.file_number}"
            if first:
                text += f"   [DOC {doc_number}]"
            self.page_list.addItem(text)
        self.page_list.blockSignals(False)

    def _on_row_changed(self, row: int) -> None:
        if row >= 0:
            self.select_page(row)

    def select_page(self, global_index: int) -> None:
        if not self.model.pages:
            return
        global_index = max(0, min(global_index, len(self.model.pages) - 1))
        self.selected_index = global_index
        self.page_list.setCurrentRow(global_index)
        self._update_buttons()
        self._update_preview()

    def _update_buttons(self) -> None:
        first = self.model.is_first_page(self.selected_index)
        self.first_button.setEnabled(not first)
        self.continuation_button.setEnabled(first and self.selected_index != 0)

    def _update_preview(self) -> None:
        page = self.model.pages[self.selected_index]
        png = render_page_png(page.source.path, page.source_page_index)
        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(png)
        self.preview.setPixmap(pixmap)

    def mark_first_page(self) -> None:
        if self.first_button.isEnabled():
            self.model.set_first_page(self.selected_index)
            self.refresh_list()
            self.select_page(self.selected_index)

    def mark_continuation(self) -> None:
        if self.continuation_button.isEnabled():
            self.model.set_continuation(self.selected_index)
            self.refresh_list()
            self.select_page(self.selected_index)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_ui_segmentation.py -v`
Expected: PASS.

- [ ] **Step 5: Wire the real screen into `MainWindow.load_lease`**

In `src/aa_tool/ui/main_window.py`, add the import at the top:

```python
from aa_tool.ui.segmentation_screen import SegmentationScreen
```

Replace the body of `load_lease` with:

```python
    def load_lease(self, folder: Path) -> None:
        self.ingest_result = scan_lease_folder(folder)
        self.model = SegmentationModel(self.ingest_result.sources)
        screen = SegmentationScreen(self.model, on_continue=self._show_export_screen)
        self.segmentation_index = self.stack.addWidget(screen)
        self.stack.setCurrentIndex(self.segmentation_index)

    def _show_export_screen(self) -> None:
        pass  # replaced in Task 11
```

(You may delete the `self._segmentation_placeholder` lines from `_build_folder_screen`.)

- [ ] **Step 6: Run the full suite to confirm nothing regressed**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add src/aa_tool/ui/segmentation_screen.py src/aa_tool/ui/main_window.py tests/test_ui_segmentation.py
git commit -m "feat: segmentation screen with page list, preview, and classify buttons"
```

---

### Task 11: Export screen and end-to-end wiring

**Files:**
- Create: `src/aa_tool/ui/export_screen.py`
- Modify: `src/aa_tool/ui/main_window.py` (`_show_export_screen`)
- Test: `tests/test_ui_export_screen.py`

**Interfaces:**
- Consumes: `SegmentationModel`, `IngestResult`, `build_summary`, `run_export`.
- Produces:
  - `class ExportScreen(QtWidgets.QWidget)` constructed with `(ingest_result, model, on_back: Callable[[], None])`. Attributes: `summary_label` (`QtWidgets.QLabel` whose text contains the document/page/source counts), `out_dir` (`Path`, defaults to the lease folder's parent of the first source, i.e. the lease folder), `export_button`, `back_button`. Method `do_export() -> ExportSummary` writes both files via `run_export` and returns the summary.

- [ ] **Step 1: Write the failing test**

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aa_tool.ingest import scan_lease_folder
from aa_tool.model import SegmentationModel
from aa_tool.ui.export_screen import ExportScreen


def test_export_screen_summary_and_export(qtbot, make_pdf, tmp_path):
    lease = tmp_path / "B11294"
    make_pdf("368481.pdf", 1, parent=lease / "0")
    make_pdf("368495.pdf", 3, parent=lease / "0")

    result = scan_lease_folder(lease)
    model = SegmentationModel(result.sources)

    screen = ExportScreen(result, model, on_back=lambda: None)
    qtbot.addWidget(screen)
    assert "2 documents" in screen.summary_label.text()

    screen.out_dir = tmp_path / "out"
    (tmp_path / "out").mkdir()
    summary = screen.do_export()

    assert summary.pdf_path.exists()
    assert summary.xlsx_path.exists()
    assert summary.pdf_path.name == "B11294 File Documents.pdf"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_ui_export_screen.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aa_tool.ui.export_screen'`.

- [ ] **Step 3: Write `src/aa_tool/ui/export_screen.py`**

```python
from collections.abc import Callable
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from aa_tool.export import ExportSummary, build_summary, run_export
from aa_tool.ingest import IngestResult
from aa_tool.model import SegmentationModel


class ExportScreen(QtWidgets.QWidget):
    def __init__(
        self,
        ingest_result: IngestResult,
        model: SegmentationModel,
        on_back: Callable[[], None],
    ):
        super().__init__()
        self.ingest_result = ingest_result
        self.model = model
        self.on_back = on_back
        self.out_dir = self._default_out_dir()

        layout = QtWidgets.QVBoxLayout(self)

        documents = self.model.documents()
        doc_count, page_count, source_count, assignments = build_summary(
            ingest_result, documents
        )
        self.summary_label = QtWidgets.QLabel(
            f"{doc_count} documents · {page_count} pages merged · "
            f"{source_count} source files · assignments {', '.join(assignments)}"
        )
        layout.addWidget(self.summary_label)

        skipped = ingest_result.skipped
        if skipped:
            warn = QtWidgets.QLabel(
                "Skipped files: " + ", ".join(p.name for p, _ in skipped)
            )
            warn.setStyleSheet("color: #7a5c00;")
            layout.addWidget(warn)

        button_bar = QtWidgets.QHBoxLayout()
        self.back_button = QtWidgets.QPushButton("◀ Back to segmenting")
        self.back_button.clicked.connect(lambda: self.on_back())
        self.export_button = QtWidgets.QPushButton("Export PDF + Excel ▶")
        self.export_button.clicked.connect(self._on_export_clicked)
        button_bar.addWidget(self.back_button)
        button_bar.addStretch()
        button_bar.addWidget(self.export_button)
        layout.addStretch()
        layout.addLayout(button_bar)

    def _default_out_dir(self) -> Path:
        if self.ingest_result.sources:
            # lease folder = the grandparent of any source file (folder/<assignment>/<file>)
            return self.ingest_result.sources[0].path.parent.parent
        return Path.cwd()

    def do_export(self) -> ExportSummary:
        documents = self.model.documents()
        return run_export(self.ingest_result, documents, self.out_dir)

    def _on_export_clicked(self) -> None:
        chosen = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Choose output folder", str(self.out_dir)
        )
        if chosen:
            self.out_dir = Path(chosen)
        summary = self.do_export()
        QtWidgets.QMessageBox.information(
            self,
            "Export complete",
            f"Saved:\n{summary.pdf_path.name}\n{summary.xlsx_path.name}",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_ui_export_screen.py -v`
Expected: PASS.

- [ ] **Step 5: Wire `_show_export_screen` in `src/aa_tool/ui/main_window.py`**

Add the import:

```python
from aa_tool.ui.export_screen import ExportScreen
```

Replace `_show_export_screen` with:

```python
    def _show_export_screen(self) -> None:
        screen = ExportScreen(
            self.ingest_result, self.model, on_back=self._back_to_segmentation
        )
        self.export_index = self.stack.addWidget(screen)
        self.stack.setCurrentIndex(self.export_index)

    def _back_to_segmentation(self) -> None:
        self.stack.setCurrentIndex(self.segmentation_index)
```

- [ ] **Step 6: Run the full suite**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest -v`
Expected: all PASS.

- [ ] **Step 7: Manual smoke test (Linux dev box)**

Run: `python main.py`
Verify: choose a lease folder (use the local `example/input_lease_files/B11294` ad hoc), confirm the page list, preview, First/Continuation buttons, and that Export writes the two correctly-named files.

- [ ] **Step 8: Commit**

```bash
git add src/aa_tool/ui/export_screen.py src/aa_tool/ui/main_window.py tests/test_ui_export_screen.py
git commit -m "feat: export screen and end-to-end wiring"
```

---

### Task 12: PyInstaller spec and GitHub Actions Windows build

**Files:**
- Create: `aa_tool.spec`
- Create: `.github/workflows/build-windows.yml`
- Create: `README.md`

**Interfaces:**
- Consumes: `main.py` entry point.
- Produces: a downloadable `AA State Abstract Tool.exe` artifact on CI.

- [ ] **Step 1: Create the PyInstaller spec `aa_tool.spec`**

```python
# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=["src"],
    binaries=[],
    # Bundle the Excel template into aa_tool/resources/ inside the one-file build,
    # matching the layout resource_path() expects under sys._MEIPASS.
    datas=[
        ("src/aa_tool/resources/Template File Documents.xlsx", "aa_tool/resources"),
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="AA State Abstract Tool",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    onefile=True,
)
```

- [ ] **Step 2: Create `.github/workflows/build-windows.yml`**

```yaml
name: Build Windows EXE

on:
  push:
    tags: ["v*"]
  workflow_dispatch:

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt pyinstaller
      - name: Run tests
        env:
          QT_QPA_PLATFORM: offscreen
        run: python -m pytest -q
      - name: Build executable
        run: pyinstaller --noconfirm aa_tool.spec
      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: aa-state-abstract-tool
          path: "dist/AA State Abstract Tool.exe"
```

- [ ] **Step 3: Create `README.md`**

```markdown
# AA State Abstract Tool

Internal Windows desktop tool for segmenting and indexing New Mexico State
Land Office lease files. Merges a lease folder's PDFs, lets a user mark the
first page of each document, and exports a bookmarked combined PDF plus an
Excel index.

## Develop (Linux/macOS/Windows)

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
QT_QPA_PLATFORM=offscreen python -m pytest      # run tests headless
python main.py                                  # launch the app
```

## Build the Windows .exe

Push a tag (`git tag v0.1.0 && git push --tags`) or run the
**Build Windows EXE** workflow manually from the Actions tab. Download the
`aa-state-abstract-tool` artifact — it contains `AA State Abstract Tool.exe`,
which staff run by double-clicking. No Python install required.
```

- [ ] **Step 4: Verify the spec builds locally is not possible on Linux (expected)**

Note: do NOT attempt to build the `.exe` on Linux. Verify only that `python main.py` launches. The real `.exe` build happens on the `windows-latest` runner. After pushing, confirm the workflow succeeds and the artifact downloads and runs on a Windows machine.

- [ ] **Step 5: Commit**

```bash
git add aa_tool.spec .github/workflows/build-windows.yml README.md
git commit -m "build: PyInstaller spec, Windows CI workflow, and README"
```

---

## Self-Review

**Spec coverage check:**
- Purpose / merge → Tasks 2, 5, 8. ✓
- Segmentation (pre-marked boundaries, First/Continuation, preview, buttons above preview, shortcuts) → Tasks 3, 7, 10. ✓
- Three screens (pick / segment / export) → Tasks 9, 10, 11. ✓
- Output PDF naming + bookmarks + NA label → Tasks 4, 5, 8. ✓
- Output Excel naming + columns + formula + Unknown/blank → Task 6 (copies bundled template `src/aa_tool/resources/Template File Documents.xlsx`, bundled into the exe via Task 12 spec `datas`). ✓
- Source/Assignment provenance, repeated source numbers → Tasks 2, 3, 6 (tested). ✓
- Ordering rules + skip non-PDF/unreadable + missing subfolders → Task 2 (tested); skipped surfaced in Task 11. ✓
- PySide6 / PyMuPDF / openpyxl / PyInstaller → Tasks 6–12. ✓
- GitHub Actions windows-latest build → Task 12. ✓
- TDD + synthetic fixtures, no example data in tests → Task 1 + every test. ✓

**Type consistency check:** `SourcePdf`, `IngestResult`, `MergedPage`, `Document`, `SegmentationModel`, `ExportSummary` names and signatures are consistent across tasks. `build_summary` returns a 4-tuple consumed identically in Task 8 and Task 11. `run_export` / `export_pdf` / `export_excel` / `render_page_png` / `build_bookmark_label` signatures match their call sites.

**Placeholder scan:** No TBDs; every code step contains complete code. UI tasks include real tests via the offscreen Qt platform plus one manual smoke test.
