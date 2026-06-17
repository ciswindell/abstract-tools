# Abstract Tools Home Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the app into a multi-tool suite with a home board of agency-grouped tool cards, with the existing lease flow refactored into the first registered tool (NMSLO Segmentor).

**Architecture:** A tool registry (data) feeds a HomeBoard (renders cards by category) hosted by a generic MainWindow shell that swaps between the board and a launched tool. The NMSLO Segmentor becomes a self-contained `NmsloSegmentorTool` widget in its own package, reached from the board and exited via a "← Back to Tools" header link.

**Tech Stack:** Python 3.12, PySide6 (incl. PySide6.QtSvg), PyMuPDF, openpyxl, pytest, pytest-qt.

## Global Constraints

- Branch base: `dev`. Work on a feature branch off `dev`.
- Suite name is **Abstract Tools**; the first tool is the **NMSLO Segmentor** (do not expand the NMSLO acronym in code or UI copy).
- Sections on the board are by **source agency** (category); the NMSLO Segmentor's category is exactly `"NM State Land Office"`.
- The per-tool package is named per-agency: `src/aa_tool/ui/nmslo_segmentor/` (future agencies get their own packages).
- Reuse the existing paper theme in `theme.py` (palette constants `PAPER`, `CARD`, `PINE`, etc.; fonts Hanken Grotesk / Spline Sans Mono). No new color scheme.
- The "← Back to Tools" link sits at the far left of the tool top bar (single row, no extra height), then a divider, then the tool/lease context, then the step indicator, then the optional progress pill.
- TDD throughout; tests use synthetic in-test fixtures only (the `make_pdf` conftest factory); the real `example/` data is never used in tests.
- Qt tests run headless: `QT_QPA_PLATFORM=offscreen python -m pytest`. Use the existing `venv` (`source venv/bin/activate`).
- Commit after each green task with a conventional-commit message; use `git -c user.name="Chris" -c user.email="chris@landmaninnovations.com" commit` if git identity is unset.

## File structure (target)

```
src/aa_tool/
  tools.py                         # NEW: Tool dataclass, tools_by_category(), TOOLS registry
  ui/
    icons.py                       # NEW: svg_pixmap() helper (QtSvg)
    home_board.py                  # NEW: HomeBoard widget
    main_window.py                 # CHANGED: generic shell (board + launched tool)
    header.py                      # CHANGED: + back-to-tools link + context_html
    theme.py                       # CHANGED: + board/card/back-link styles
    nmslo_segmentor/
      __init__.py                  # NEW (empty)
      tool.py                      # NEW: NmsloSegmentorTool (open screen + orchestration)
      segmentation_screen.py       # MOVED from ui/
      export_screen.py             # MOVED from ui/
  resources/icons/segmentor.svg    # NEW
```

---

### Task 1: SVG icon helper + segmentor icon

**Files:**
- Create: `src/aa_tool/ui/icons.py`
- Create: `src/aa_tool/resources/icons/segmentor.svg`
- Modify: `aa_tool.spec` (bundle icons)
- Test: `tests/test_icons.py`

**Interfaces:**
- Consumes: `resource_path` from `aa_tool.resources`.
- Produces: `svg_pixmap(name: str, size: int) -> QtGui.QPixmap` — renders a bundled SVG (under `resources/`) to a square transparent pixmap of `size`×`size` device-independent pixels.

- [ ] **Step 1: Create the icon `src/aa_tool/resources/icons/segmentor.svg`**

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#1d5c54" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
  <rect x="5" y="3" width="14" height="18" rx="2"/>
  <path d="M9 8h6M9 12h6M9 16h3"/>
  <path d="M2 12h4" stroke-dasharray="1.5 1.5"/>
</svg>
```

- [ ] **Step 2: Write the failing test `tests/test_icons.py`**

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aa_tool.ui.icons import svg_pixmap


def test_svg_pixmap_renders_square_non_null(qtbot):
    pm = svg_pixmap("icons/segmentor.svg", 48)
    assert not pm.isNull()
    assert pm.width() == 48
    assert pm.height() == 48
```

- [ ] **Step 3: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_icons.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aa_tool.ui.icons'`.

- [ ] **Step 4: Write `src/aa_tool/ui/icons.py`**

```python
from PySide6 import QtCore, QtGui, QtSvg

from aa_tool.resources import resource_path


def svg_pixmap(name: str, size: int) -> QtGui.QPixmap:
    """Render a bundled SVG resource to a transparent square pixmap."""
    renderer = QtSvg.QSvgRenderer(str(resource_path(name)))
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    renderer.render(painter)
    painter.end()
    return QtGui.QPixmap.fromImage(image)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_icons.py -v`
Expected: PASS.

- [ ] **Step 6: Bundle icons in `aa_tool.spec`**

In the `datas=[...]` list of `Analysis(...)`, add a third entry so it reads:

```python
    datas=[
        ("src/aa_tool/resources/Template File Documents.xlsx", "aa_tool/resources"),
        ("src/aa_tool/resources/fonts/*.ttf", "aa_tool/resources/fonts"),
        ("src/aa_tool/resources/icons/*.svg", "aa_tool/resources/icons"),
    ],
```

- [ ] **Step 7: Commit**

```bash
git add src/aa_tool/ui/icons.py "src/aa_tool/resources/icons/segmentor.svg" aa_tool.spec tests/test_icons.py
git commit -m "feat: SVG icon helper and NMSLO Segmentor icon"
```

---

### Task 2: Tool dataclass + grouping helper

**Files:**
- Create: `src/aa_tool/tools.py`
- Test: `tests/test_tools.py`

**Interfaces:**
- Consumes: nothing (pure).
- Produces:
  - `@dataclass(frozen=True) Tool(id: str, name: str, description: str, category: str, icon: str, build: Callable[[Callable[[], None]], "QtWidgets.QWidget"])`
  - `tools_by_category(tools: list[Tool]) -> dict[str, list[Tool]]` — groups by `category`, preserving first-seen category order and within-category order.

(The real `TOOLS` registry is added in Task 7, once `NmsloSegmentorTool` exists.)

- [ ] **Step 1: Write the failing test `tests/test_tools.py`**

```python
from aa_tool.tools import Tool, tools_by_category


def _tool(id, category):
    return Tool(id=id, name=id, description="", category=category, icon="", build=lambda cb: None)


def test_groups_by_category_preserving_order():
    tools = [
        _tool("a", "NM State Land Office"),
        _tool("b", "BLM"),
        _tool("c", "NM State Land Office"),
    ]
    grouped = tools_by_category(tools)
    assert list(grouped.keys()) == ["NM State Land Office", "BLM"]
    assert [t.id for t in grouped["NM State Land Office"]] == ["a", "c"]
    assert [t.id for t in grouped["BLM"]] == ["b"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aa_tool.tools'`.

- [ ] **Step 3: Write `src/aa_tool/tools.py`**

```python
from collections.abc import Callable
from dataclasses import dataclass

from PySide6 import QtWidgets


@dataclass(frozen=True)
class Tool:
    id: str
    name: str
    description: str
    category: str  # source agency, e.g. "NM State Land Office"
    icon: str      # bundled resource name, e.g. "icons/segmentor.svg"
    # build(on_back_to_tools) -> the tool's root widget
    build: Callable[[Callable[[], None]], QtWidgets.QWidget]


def tools_by_category(tools: list[Tool]) -> dict[str, list[Tool]]:
    grouped: dict[str, list[Tool]] = {}
    for tool in tools:
        grouped.setdefault(tool.category, []).append(tool)
    return grouped
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tools.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/aa_tool/tools.py tests/test_tools.py
git commit -m "feat: Tool registry dataclass and category grouping"
```

---

### Task 3: HomeBoard widget

**Files:**
- Create: `src/aa_tool/ui/home_board.py`
- Modify: `src/aa_tool/ui/theme.py` (board/card styles)
- Test: `tests/test_ui_home_board.py`

**Interfaces:**
- Consumes: `Tool`, `tools_by_category` (`aa_tool.tools`); `svg_pixmap` (`aa_tool.ui.icons`); theme palette.
- Produces: `HomeBoard(tools: list[Tool], on_launch: Callable[[str], None])` — a `QWidget` (objectName `"screen"`). Renders a top bar, hero, and one section per category with a card per tool. Exposes `cards: dict[str, QtWidgets.QWidget]` (tool id → clickable card). Clicking a card calls `on_launch(tool.id)`.

- [ ] **Step 1: Add board styles to `src/aa_tool/ui/theme.py`**

Append these rules to the end of the `STYLESHEET` string (before the closing `"""`):

```css
/* ---- Home board ---- */
QWidget#boardTop {{ background: {CARD}; border-bottom: 1px solid {LINE}; }}
QLabel#boardBrand {{ font-family: "{SANS}"; font-size: 19px; font-weight: 800; letter-spacing: -0.3px; }}
QLabel#boardHero {{ font-family: "{SANS}"; font-size: 34px; font-weight: 800; letter-spacing: -0.8px; }}
QLabel#boardHeroSub {{ font-size: 15px; color: {INK_SOFT}; }}
QLabel#secHead {{ font-size: 13px; font-weight: 700; color: {INK_SOFT}; }}
QFrame#secRule {{ background: {LINE}; max-height: 1px; min-height: 1px; }}
QFrame#toolCard {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 14px; }}
QFrame#toolCard:hover {{ border-color: {PINE}; }}
QLabel#toolCardName {{ font-size: 16px; font-weight: 700; }}
QLabel#toolCardDesc {{ font-size: 13px; color: {INK_SOFT}; }}
QLabel#toolCardIcon {{ background: #e7efe9; border-radius: 11px; }}
```

- [ ] **Step 2: Write the failing test `tests/test_ui_home_board.py`**

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aa_tool.tools import Tool
from aa_tool.ui.home_board import HomeBoard


def _tool(id, category):
    return Tool(id=id, name=id.title(), description="desc", category=category,
                icon="icons/segmentor.svg", build=lambda cb: None)


def test_board_renders_card_per_tool_and_launches(qtbot):
    launched = []
    tools = [_tool("nmslo_segmentor", "NM State Land Office")]
    board = HomeBoard(tools, on_launch=launched.append)
    qtbot.addWidget(board)

    assert set(board.cards.keys()) == {"nmslo_segmentor"}

    # Clicking the card launches by tool id.
    board.cards["nmslo_segmentor"].mousePressEvent(None)
    assert launched == ["nmslo_segmentor"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_ui_home_board.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aa_tool.ui.home_board'`.

- [ ] **Step 4: Write `src/aa_tool/ui/home_board.py`**

```python
from collections.abc import Callable

from PySide6 import QtCore, QtWidgets

from aa_tool.tools import Tool, tools_by_category
from aa_tool.ui.icons import svg_pixmap


class _ToolCard(QtWidgets.QFrame):
    def __init__(self, tool: Tool, on_launch: Callable[[str], None]):
        super().__init__()
        self.setObjectName("toolCard")
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._tool_id = tool.id
        self._on_launch = on_launch

        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(22, 22, 22, 22)
        v.setSpacing(12)

        icon = QtWidgets.QLabel()
        icon.setObjectName("toolCardIcon")
        icon.setFixedSize(46, 46)
        icon.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(svg_pixmap(tool.icon, 24))
        v.addWidget(icon)

        name = QtWidgets.QLabel(tool.name)
        name.setObjectName("toolCardName")
        v.addWidget(name)

        desc = QtWidgets.QLabel(tool.description)
        desc.setObjectName("toolCardDesc")
        desc.setWordWrap(True)
        v.addWidget(desc)
        v.addStretch()

    def mousePressEvent(self, event):  # noqa: N802 (Qt override)
        self._on_launch(self._tool_id)


class HomeBoard(QtWidgets.QWidget):
    def __init__(self, tools: list[Tool], on_launch: Callable[[str], None]):
        super().__init__()
        self.setObjectName("screen")
        self.cards: dict[str, QtWidgets.QWidget] = {}

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        top = QtWidgets.QWidget()
        top.setObjectName("boardTop")
        top_row = QtWidgets.QHBoxLayout(top)
        top_row.setContentsMargins(28, 14, 28, 14)
        brand = QtWidgets.QLabel("Abstract Tools")
        brand.setObjectName("boardBrand")
        top_row.addWidget(brand)
        top_row.addStretch()
        outer.addWidget(top)

        scroll = QtWidgets.QScrollArea()
        scroll.setObjectName("screen")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        inner = QtWidgets.QWidget()
        inner.setObjectName("screen")
        body = QtWidgets.QVBoxLayout(inner)
        body.setContentsMargins(28, 30, 28, 60)
        body.setSpacing(0)

        hero = QtWidgets.QLabel("Tools")
        hero.setObjectName("boardHero")
        hero.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        sub = QtWidgets.QLabel("Select a tool to get started")
        sub.setObjectName("boardHeroSub")
        sub.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        body.addWidget(hero)
        body.addWidget(sub)
        body.addSpacing(24)

        for category, group in tools_by_category(tools).items():
            head_row = QtWidgets.QHBoxLayout()
            head_row.setSpacing(12)
            label = QtWidgets.QLabel(category)
            label.setObjectName("secHead")
            rule = QtWidgets.QFrame()
            rule.setObjectName("secRule")
            head_row.addWidget(label)
            head_row.addWidget(rule, 1)
            body.addSpacing(12)
            body.addLayout(head_row)
            body.addSpacing(14)

            grid = QtWidgets.QGridLayout()
            grid.setSpacing(16)
            for i, tool in enumerate(group):
                card = _ToolCard(tool, on_launch)
                self.cards[tool.id] = card
                grid.addWidget(card, i // 3, i % 3)
            # Keep cards left-aligned at their natural width in a 3-col grid.
            for col in range(3):
                grid.setColumnStretch(col, 1)
            body.addLayout(grid)

        body.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_ui_home_board.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/aa_tool/ui/home_board.py src/aa_tool/ui/theme.py tests/test_ui_home_board.py
git commit -m "feat: HomeBoard renders agency-grouped tool cards"
```

---

### Task 4: Header — Back-to-Tools link + context (additive)

**Files:**
- Modify: `src/aa_tool/ui/header.py`
- Modify: `src/aa_tool/ui/theme.py` (back-link + divider styles)
- Test: `tests/test_ui_header.py`

**Interfaces:**
- Consumes: theme palette.
- Produces: `Header(active_step: int, context_html: str = "", on_back_to_tools: "Callable[[], None] | None" = None, lease: str | None = None)`.
  - When `on_back_to_tools` is set, a left-aligned `back_button` (objectName `"backToTools"`, text `"←  Back to Tools"`) appears, then a divider, then the context.
  - `context_html` is rendered as rich text in the brand label. If empty, falls back to `lease` (`"Lease …"`) or `"Abstract Tools"` (preserves current callers until they migrate in Task 6).
  - Keeps `set_progress(value, maximum, text)` unchanged.

- [ ] **Step 1: Add styles to `src/aa_tool/ui/theme.py`**

Append to the `STYLESHEET` (before the closing `"""`):

```css
/* ---- Back to Tools link ---- */
QPushButton#backToTools {{
    background: transparent; border: none; color: {PINE};
    font-weight: 700; font-size: 14px; padding: 0; text-align: left;
}}
QPushButton#backToTools:hover {{ color: {PINE_DEEP}; }}
QFrame#hdrDivider {{ background: {LINE}; max-width: 1px; min-width: 1px; }}
```

- [ ] **Step 2: Write the failing test `tests/test_ui_header.py`**

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aa_tool.ui.header import Header


def test_back_to_tools_link_invokes_callback(qtbot):
    called = []
    header = Header(active_step=2, context_html="NMSLO Segmentor",
                    on_back_to_tools=lambda: called.append(True))
    qtbot.addWidget(header)
    header.back_button.click()
    assert called == [True]


def test_no_back_link_without_callback(qtbot):
    header = Header(active_step=1)
    qtbot.addWidget(header)
    assert header.back_button is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_ui_header.py -v`
Expected: FAIL (`Header` has no `back_button`, or signature mismatch).

- [ ] **Step 4: Rewrite `src/aa_tool/ui/header.py`**

```python
"""Shared top bar. On a tool screen it shows a Back-to-Tools link, the tool or
lease context, a step indicator, and an optional progress pill.
"""

from collections.abc import Callable

from PySide6 import QtCore, QtWidgets

_STEPS = ["1 · Open", "2 · Segment", "3 · Export"]


class Header(QtWidgets.QWidget):
    def __init__(
        self,
        active_step: int,
        context_html: str = "",
        on_back_to_tools: Callable[[], None] | None = None,
        lease: str | None = None,
    ):
        super().__init__()
        self.setObjectName("header")

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(22, 11, 22, 11)
        layout.setSpacing(16)

        self.back_button = None
        if on_back_to_tools is not None:
            self.back_button = QtWidgets.QPushButton("←  Back to Tools")
            self.back_button.setObjectName("backToTools")
            self.back_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            self.back_button.clicked.connect(lambda: on_back_to_tools())
            layout.addWidget(self.back_button)
            divider = QtWidgets.QFrame()
            divider.setObjectName("hdrDivider")
            divider.setFixedHeight(22)
            layout.addWidget(divider)

        brand = QtWidgets.QLabel()
        brand.setObjectName("brand")
        if context_html:
            brand.setText(context_html)
        elif lease:
            brand.setText(f"Lease&nbsp;{lease}")
        else:
            brand.setText("Abstract Tools")
        layout.addWidget(brand)

        for i, label in enumerate(_STEPS, start=1):
            chip = QtWidgets.QLabel(label)
            chip.setObjectName("stepActive" if i == active_step else "step")
            layout.addWidget(chip)

        layout.addStretch()

        self._pill_wrap = QtWidgets.QWidget()
        pill_row = QtWidgets.QHBoxLayout(self._pill_wrap)
        pill_row.setContentsMargins(0, 0, 0, 0)
        pill_row.setSpacing(8)
        self._bar = QtWidgets.QProgressBar()
        self._bar.setObjectName("pill")
        self._bar.setTextVisible(False)
        self._pill_text = QtWidgets.QLabel()
        self._pill_text.setObjectName("pillText")
        pill_row.addWidget(self._bar)
        pill_row.addWidget(self._pill_text)
        self._pill_wrap.setVisible(False)
        layout.addWidget(self._pill_wrap)

    def set_progress(self, value: int, maximum: int, text: str) -> None:
        self._bar.setMaximum(max(maximum, 1))
        self._bar.setValue(value)
        self._pill_text.setText(text)
        self._pill_wrap.setVisible(True)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_ui_header.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full suite to confirm existing screens still work**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest -q`
Expected: all PASS (existing screens still call `Header(active_step=..., lease=...)`, which the `lease` fallback preserves).

- [ ] **Step 7: Commit**

```bash
git add src/aa_tool/ui/header.py src/aa_tool/ui/theme.py tests/test_ui_header.py
git commit -m "feat: Header gains Back-to-Tools link and context_html"
```

---

### Task 5: Move segmentor screens into the nmslo_segmentor package

**Files:**
- Create: `src/aa_tool/ui/nmslo_segmentor/__init__.py` (empty)
- Move: `src/aa_tool/ui/segmentation_screen.py` → `src/aa_tool/ui/nmslo_segmentor/segmentation_screen.py`
- Move: `src/aa_tool/ui/export_screen.py` → `src/aa_tool/ui/nmslo_segmentor/export_screen.py`
- Modify: `src/aa_tool/ui/main_window.py` (import paths)
- Modify: `tests/test_ui_segmentation.py`, `tests/test_ui_export_screen.py` (import paths)

**Interfaces:**
- Consumes: existing screen classes (unchanged behavior).
- Produces: same classes at new import paths `aa_tool.ui.nmslo_segmentor.segmentation_screen` / `.export_screen`.

- [ ] **Step 1: Move the files and add the package init**

```bash
mkdir -p src/aa_tool/ui/nmslo_segmentor
touch src/aa_tool/ui/nmslo_segmentor/__init__.py
git mv src/aa_tool/ui/segmentation_screen.py src/aa_tool/ui/nmslo_segmentor/segmentation_screen.py
git mv src/aa_tool/ui/export_screen.py src/aa_tool/ui/nmslo_segmentor/export_screen.py
```

- [ ] **Step 2: Update imports in `src/aa_tool/ui/main_window.py`**

Change:
```python
from aa_tool.ui.export_screen import ExportScreen
from aa_tool.ui.segmentation_screen import SegmentationScreen
```
to:
```python
from aa_tool.ui.nmslo_segmentor.export_screen import ExportScreen
from aa_tool.ui.nmslo_segmentor.segmentation_screen import SegmentationScreen
```

- [ ] **Step 3: Update imports in the two test files**

In `tests/test_ui_segmentation.py` change `from aa_tool.ui.segmentation_screen import SegmentationScreen` to `from aa_tool.ui.nmslo_segmentor.segmentation_screen import SegmentationScreen`.

In `tests/test_ui_export_screen.py` change `from aa_tool.ui.export_screen import ExportScreen` to `from aa_tool.ui.nmslo_segmentor.export_screen import ExportScreen`.

- [ ] **Step 4: Run the full suite**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest -q`
Expected: all PASS (pure move; no behavior change).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: move segmentor screens into nmslo_segmentor package"
```

---

### Task 6: Extract NmsloSegmentorTool from MainWindow

**Files:**
- Create: `src/aa_tool/ui/nmslo_segmentor/tool.py`
- Modify: `src/aa_tool/ui/nmslo_segmentor/segmentation_screen.py` (constructor + Header call)
- Modify: `src/aa_tool/ui/nmslo_segmentor/export_screen.py` (constructor + Header call)
- Modify: `src/aa_tool/ui/main_window.py` (host the tool; remove segmentor orchestration)
- Modify: `tests/test_ui_segmentation.py`, `tests/test_ui_export_screen.py` (new constructor arg)
- Create: `tests/test_nmslo_segmentor_tool.py`
- Modify: `tests/test_ui_main_window.py` (drop moved tests for now; minimal smoke)

**Interfaces:**
- Consumes: `scan_lease_folder` (ingest), `SegmentationModel` (model), `SegmentationScreen`, `ExportScreen`, `Header`, theme `PINE`.
- Produces:
  - `NmsloSegmentorTool(on_back_to_tools: Callable[[], None])` — a `QWidget` owning a `QStackedWidget` with: an open-lease screen, then segmentation, then export. Public: `load_lease(folder: Path) -> None` (sets `self.ingest_result`, `self.model`, shows segmentation); attributes `ingest_result`, `model`.
  - `SegmentationScreen(model, lease_number, on_continue, on_back_to_tools)` — same as before plus `on_back_to_tools`, passed to its `Header` with `context_html` = `Lease <number>` (number in `PINE`).
  - `ExportScreen(ingest_result, model, on_back, on_new_lease, on_back_to_tools)` — same as before plus `on_back_to_tools`, passed to its `Header`.

- [ ] **Step 1: Update `SegmentationScreen` to take `on_back_to_tools` and use it in the Header**

In `src/aa_tool/ui/nmslo_segmentor/segmentation_screen.py`, add the import near the top:
```python
from aa_tool.ui import theme
```
Change the constructor signature:
```python
    def __init__(
        self,
        model: SegmentationModel,
        lease_number: str,
        on_continue: Callable[[], None],
        on_back_to_tools: Callable[[], None],
    ):
```
Store it and replace the Header construction line:
```python
        self.on_continue = on_continue
        self.on_back_to_tools = on_back_to_tools
```
```python
        self.header = Header(
            active_step=2,
            context_html=f'Lease&nbsp;<span style="color:{theme.PINE}">{lease_number}</span>',
            on_back_to_tools=on_back_to_tools,
        )
```

- [ ] **Step 2: Update `ExportScreen` to take `on_back_to_tools` and use it in the Header**

In `src/aa_tool/ui/nmslo_segmentor/export_screen.py`, add `from aa_tool.ui import theme` near the top. Change the constructor signature to add the parameter:
```python
    def __init__(
        self,
        ingest_result: IngestResult,
        model: SegmentationModel,
        on_back: Callable[[], None],
        on_new_lease: Callable[[], None],
        on_back_to_tools: Callable[[], None],
    ):
```
Store `self.on_back_to_tools = on_back_to_tools` alongside the other callbacks, and replace the header construction line:
```python
        outer.addWidget(Header(active_step=3, lease=ingest_result.lease_number))
```
with:
```python
        outer.addWidget(Header(
            active_step=3,
            context_html=f'Lease&nbsp;<span style="color:{theme.PINE}">{ingest_result.lease_number}</span>',
            on_back_to_tools=on_back_to_tools,
        ))
```

- [ ] **Step 3: Write `src/aa_tool/ui/nmslo_segmentor/tool.py`**

```python
from collections.abc import Callable
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from aa_tool.ingest import scan_lease_folder
from aa_tool.model import SegmentationModel
from aa_tool.ui.header import Header
from aa_tool.ui.nmslo_segmentor.export_screen import ExportScreen
from aa_tool.ui.nmslo_segmentor.segmentation_screen import SegmentationScreen


class NmsloSegmentorTool(QtWidgets.QWidget):
    def __init__(self, on_back_to_tools: Callable[[], None]):
        super().__init__()
        self.setObjectName("screen")
        self.on_back_to_tools = on_back_to_tools
        self.ingest_result = None
        self.model: SegmentationModel | None = None
        self._segmentation_screen: SegmentationScreen | None = None
        self._export_screen: ExportScreen | None = None

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.stack = QtWidgets.QStackedWidget()
        outer.addWidget(self.stack)

        self._build_open_screen()

    def _build_open_screen(self) -> None:
        page = QtWidgets.QWidget()
        page.setObjectName("screen")
        v = QtWidgets.QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(Header(
            active_step=1,
            context_html="NMSLO Segmentor",
            on_back_to_tools=self.on_back_to_tools,
        ))

        center = QtWidgets.QVBoxLayout()
        center.setContentsMargins(0, 0, 0, 0)
        center.setSpacing(14)
        center.addStretch()
        h1 = QtWidgets.QLabel("Open a lease file")
        h1.setObjectName("h1")
        h1.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        sub = QtWidgets.QLabel(
            "Choose a lease folder. Its PDFs are merged so you can mark the\n"
            "first page of each document, then export a bookmarked PDF and an index."
        )
        sub.setObjectName("sub")
        sub.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        button = QtWidgets.QPushButton("Choose lease folder…")
        button.setObjectName("primary")
        button.clicked.connect(self._choose_folder)
        center.addWidget(h1)
        center.addWidget(sub)
        center.addSpacing(8)
        center.addWidget(button, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        center.addStretch()
        v.addLayout(center, 1)

        self.open_index = self.stack.addWidget(page)

    def _choose_folder(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Choose lease folder", str(Path.home())
        )
        if folder:
            self.load_lease(Path(folder))

    def _swap_in(self, screen, previous):
        if previous is not None:
            self.stack.removeWidget(previous)
            previous.deleteLater()
        index = self.stack.addWidget(screen)
        self.stack.setCurrentIndex(index)

    def load_lease(self, folder: Path) -> None:
        self.ingest_result = scan_lease_folder(folder)
        self.model = SegmentationModel(self.ingest_result.sources)
        screen = SegmentationScreen(
            self.model,
            self.ingest_result.lease_number,
            on_continue=self._show_export_screen,
            on_back_to_tools=self.on_back_to_tools,
        )
        self._swap_in(screen, self._segmentation_screen)
        self._segmentation_screen = screen

    def _show_export_screen(self) -> None:
        screen = ExportScreen(
            self.ingest_result,
            self.model,
            on_back=self._back_to_segmentation,
            on_new_lease=self._restart,
            on_back_to_tools=self.on_back_to_tools,
        )
        self._swap_in(screen, self._export_screen)
        self._export_screen = screen

    def _back_to_segmentation(self) -> None:
        if self._segmentation_screen is not None:
            self.stack.setCurrentWidget(self._segmentation_screen)

    def _restart(self) -> None:
        # "Process another lease" — back to this tool's open screen, fresh state.
        self.stack.setCurrentIndex(self.open_index)
        for attr in ("_segmentation_screen", "_export_screen"):
            screen = getattr(self, attr)
            if screen is not None:
                self.stack.removeWidget(screen)
                screen.deleteLater()
                setattr(self, attr, None)
        self.ingest_result = None
        self.model = None
```

- [ ] **Step 4: Replace `src/aa_tool/ui/main_window.py` with a temporary single-tool host**

(The board comes in Task 7; for now MainWindow hosts the tool directly so the app keeps working and tests stay green.)

```python
from PySide6 import QtWidgets

from aa_tool.ui import theme
from aa_tool.ui.nmslo_segmentor.tool import NmsloSegmentorTool


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Abstract Tools")
        self.resize(1200, 820)
        self.tool = NmsloSegmentorTool(on_back_to_tools=lambda: None)
        self.setCentralWidget(self.tool)


def main() -> None:
    import sys

    app = QtWidgets.QApplication(sys.argv)
    theme.apply_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
```

- [ ] **Step 5: Update `tests/test_ui_segmentation.py` for the new constructor**

Change the `_screen` helper:
```python
def _screen(model):
    return SegmentationScreen(model, "B11294", on_continue=lambda: None,
                              on_back_to_tools=lambda: None)
```

- [ ] **Step 6: Update `tests/test_ui_export_screen.py` for the new constructor**

Change the `ExportScreen(...)` construction to:
```python
    screen = ExportScreen(
        result, model, on_back=lambda: None, on_new_lease=lambda: None,
        on_back_to_tools=lambda: None,
    )
```

- [ ] **Step 7: Write `tests/test_nmslo_segmentor_tool.py`**

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aa_tool.ui.nmslo_segmentor.tool import NmsloSegmentorTool


def test_load_lease_builds_model(qtbot, make_pdf, tmp_path):
    lease = tmp_path / "B11294"
    make_pdf("368481.pdf", 2, parent=lease / "0")

    tool = NmsloSegmentorTool(on_back_to_tools=lambda: None)
    qtbot.addWidget(tool)
    tool.load_lease(lease)

    assert tool.ingest_result.lease_number == "B11294"
    assert len(tool.model.pages) == 2


def test_back_to_tools_callback_wired(qtbot, make_pdf, tmp_path):
    called = []
    from PySide6 import QtWidgets

    tool = NmsloSegmentorTool(on_back_to_tools=lambda: called.append(True))
    qtbot.addWidget(tool)
    # The open screen's header has the Back-to-Tools button; clicking it fires the callback.
    back_buttons = [b for b in tool.findChildren(QtWidgets.QPushButton)
                    if b.objectName() == "backToTools"]
    assert back_buttons
    back_buttons[0].click()
    assert called == [True]
```

- [ ] **Step 8: Replace `tests/test_ui_main_window.py` with a minimal smoke test**

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aa_tool.ui.main_window import MainWindow


def test_main_window_constructs(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.windowTitle() == "Abstract Tools"
```

- [ ] **Step 9: Run the full suite**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest -q`
Expected: all PASS.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "refactor: extract NmsloSegmentorTool with Back-to-Tools wiring"
```

---

### Task 7: Wire the board into MainWindow + register the tool

**Files:**
- Modify: `src/aa_tool/tools.py` (add `TOOLS` registry)
- Modify: `src/aa_tool/ui/main_window.py` (board shell)
- Modify: `tests/test_ui_main_window.py` (launch + back-to-board)

**Interfaces:**
- Consumes: `Tool`, `TOOLS` (tools.py); `HomeBoard`; `NmsloSegmentorTool`.
- Produces:
  - `tools.py` module global `TOOLS: list[Tool]` containing the NMSLO Segmentor.
  - `MainWindow` with `launch_tool(tool_id: str) -> None` and `show_board() -> None`; roots at the board.

- [ ] **Step 1: Add the registry to `src/aa_tool/tools.py`**

Append at the end of the file:

```python
from aa_tool.ui.nmslo_segmentor.tool import NmsloSegmentorTool

SEGMENTOR_TOOL = Tool(
    id="nmslo_segmentor",
    name="NMSLO Segmentor",
    description=(
        "Merge a lease file's PDFs, mark the first page of each document, "
        "and export a bookmarked PDF plus an Excel index."
    ),
    category="NM State Land Office",
    icon="icons/segmentor.svg",
    build=lambda on_back: NmsloSegmentorTool(on_back),
)

TOOLS: list[Tool] = [SEGMENTOR_TOOL]
```

- [ ] **Step 2: Write the failing test in `tests/test_ui_main_window.py`**

Replace the file with:

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aa_tool.ui.main_window import MainWindow


def test_starts_on_board_then_launches_and_returns(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    # Starts on the board.
    assert window.stack.currentWidget() is window.board

    window.launch_tool("nmslo_segmentor")
    assert window.stack.currentWidget() is not window.board

    window.show_board()
    assert window.stack.currentWidget() is window.board
```

- [ ] **Step 3: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_ui_main_window.py -v`
Expected: FAIL (`MainWindow` has no `board` / `launch_tool`).

- [ ] **Step 4: Replace `src/aa_tool/ui/main_window.py` with the board shell**

```python
from PySide6 import QtWidgets

from aa_tool import tools as tools_module
from aa_tool.ui import theme
from aa_tool.ui.home_board import HomeBoard


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Abstract Tools")
        self.resize(1200, 820)

        self.stack = QtWidgets.QStackedWidget()
        self.setCentralWidget(self.stack)

        self._tools = {t.id: t for t in tools_module.TOOLS}
        self.board = HomeBoard(tools_module.TOOLS, on_launch=self.launch_tool)
        self.stack.addWidget(self.board)

        self._current_tool = None

    def launch_tool(self, tool_id: str) -> None:
        tool = self._tools[tool_id]
        widget = tool.build(self.show_board)
        if self._current_tool is not None:
            self.stack.removeWidget(self._current_tool)
            self._current_tool.deleteLater()
        self._current_tool = widget
        self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)

    def show_board(self) -> None:
        self.stack.setCurrentWidget(self.board)
        if self._current_tool is not None:
            self.stack.removeWidget(self._current_tool)
            self._current_tool.deleteLater()
            self._current_tool = None


def main() -> None:
    import sys

    app = QtWidgets.QApplication(sys.argv)
    theme.apply_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_ui_main_window.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest -q`
Expected: all PASS.

- [ ] **Step 7: Manual smoke test (Linux dev box)**

Run: `venv/bin/python main.py`
Verify: app opens on the board with the "NM State Land Office" section and the NMSLO Segmentor card; clicking it opens the tool's Open screen; "← Back to Tools" returns to the board; opening a lease → segment → export still works, and "Process another lease" returns to the tool's Open screen.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: home board shell launches registered tools"
```

---

## Self-Review

**Spec coverage:**
- Tool registry (id/name/description/category/icon/build) → Task 2 (dataclass) + Task 7 (TOOLS). ✓
- Home board: top bar, hero, agency sections, cards, launch-by-id → Task 3. ✓
- App shell: roots at board, launch_tool, show_board, drops tool state → Task 7. ✓
- NmsloSegmentorTool in `nmslo_segmentor/` package with own stack + state → Tasks 5, 6. ✓
- "Process another lease" returns to the tool's open screen (distinct from Back to Tools) → Task 6 `_restart`. ✓
- Header: Back-to-Tools link + divider + context_html + steps + pill; set_status removed → Task 4. ✓
- Icons: bundled SVG via QtSvg, spec datas → Task 1. ✓
- Paper theme reuse, board/card/back-link styles → Tasks 3, 4. ✓
- Component boundaries (home_board knows only the registry; main_window knows no segmentation) → Tasks 3, 7. ✓
- TDD + synthetic fixtures + offscreen → every task. ✓
- "← Back to Tools" placement (far left, single row, divider, context) → Tasks 4, 6. ✓

**Placeholder scan:** No TBDs. Every code step shows complete code. The `test_back_to_tools_callback_wired` test finds the `backToTools` button via `findChildren` and clicks it (real behavior). Task 6's temporary MainWindow is explicitly replaced in Task 7.

**Type consistency:** `Header(active_step, context_html, on_back_to_tools, lease)` is defined in Task 4 and called consistently in Tasks 6. `SegmentationScreen(model, lease_number, on_continue, on_back_to_tools)` and `ExportScreen(ingest_result, model, on_back, on_new_lease, on_back_to_tools)` are defined in Task 6 and constructed identically in tests and in `NmsloSegmentorTool`. `Tool.build` is `Callable[[on_back], QWidget]` in Task 2 and matched by `lambda on_back: NmsloSegmentorTool(on_back)` in Task 7 and `HomeBoard`/`MainWindow` call `on_launch(tool.id)` / `tool.build(self.show_board)` consistently. `TOOLS` is referenced as `tools_module.TOOLS` after being defined in Task 7.
