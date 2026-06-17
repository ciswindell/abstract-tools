# Abstract Tools Home Board — Design Spec

**Date:** 2026-06-17
**Status:** Approved design, pending implementation plan
**Branch base:** `dev`

## Purpose

Turn the app from a single-purpose program into a **suite**. On launch, show a home board — a grid of tool cards grouped by source agency. The existing lease-segmentation flow becomes the first registered tool, the **NMSLO Segmentor**. Adding future tools should be as simple as registering them.

## Architecture

Three pieces: a **tool registry** (data), a **home board** (renders the registry), and a generic **app shell** (swaps between the board and the launched tool). The NMSLO Segmentor is refactored into a self-contained tool widget that the registry registers.

### Tool registry — `src/aa_tool/tools.py`
```python
@dataclass(frozen=True)
class Tool:
    id: str            # e.g. "nmslo_segmentor"
    name: str          # "NMSLO Segmentor"
    description: str   # one-line card description
    category: str      # source agency, e.g. "NM State Land Office"
    icon: str          # resource filename, e.g. "icons/segmentor.svg"
    build: Callable[[Callable[[], None]], QtWidgets.QWidget]
    # build(on_back_to_tools) -> the tool's root widget, with the callback
    # wired to every screen's "Back to Tools" link.

TOOLS: list[Tool] = [SEGMENTOR_TOOL]

def tools_by_category() -> dict[str, list[Tool]]:
    """Preserve insertion order of categories and tools within each."""
```

### Home board — `src/aa_tool/ui/home_board.py`
`HomeBoard(QWidget, on_launch: Callable[[str], None])` renders:
- A top bar: pine logo mark + "Abstract Tools".
- A hero: "Tools" / "Select a tool to get started".
- One section per category (in registry order), each a section header (uppercase label + rule) over a responsive card grid.
- Each card (clickable): SVG icon tile, tool name, description. Clicking calls `on_launch(tool.id)`.
- `HomeBoard` keeps a `cards: dict[str, QWidget]` (tool id → card) so behavior is testable.

### App shell — `src/aa_tool/ui/main_window.py`
`MainWindow` becomes generic:
- Roots at `HomeBoard` (index 0 in a `QStackedWidget`).
- `launch_tool(tool_id)`: looks up the `Tool`, calls `tool.build(on_back_to_tools=self.show_board)`, swaps the stack to it (removing any previous tool widget).
- `show_board()`: removes the current tool widget (dropping its state) and shows the board.
- No segmentation-specific logic remains in `MainWindow`.

### NMSLO Segmentor tool — `src/aa_tool/ui/segmentor/`
The current folder→segment→export orchestration (today in `MainWindow`) moves into a `SegmentorTool(QWidget)` that owns its own `QStackedWidget` of the three screens and the `ingest_result` / `model` state. Files move into a `segmentor/` package:
- `segmentor/tool.py` — `SegmentorTool` (folder-open screen + `load_lease` + `show_export` + internal navigation; accepts `on_back_to_tools`).
- `segmentor/segmentation_screen.py`, `segmentor/export_screen.py` — moved, unchanged in behavior except the header.
- `tools.py` defines `SEGMENTOR_TOOL = Tool(..., build=lambda on_back: SegmentorTool(on_back))`.

The segmentor's "Process another lease" returns to the tool's own open screen (resetting lease state) — distinct from "Back to Tools" which exits to the board.

### Shared header — `src/aa_tool/ui/header.py`
`Header` gains the tool-screen treatment (single row, no extra height):
`Header(active_step: int, context_html: str, on_back_to_tools: Callable[[], None])`
- Left: **"← Back to Tools"** link (pine) calling `on_back_to_tools`.
- Divider, then `context_html` (a rich-text string the caller supplies): the tool name (`"NMSLO Segmentor"` on the open step) or the lease (`'Lease&nbsp;<span style="color:#1d5c54">B11294</span>'`) once loaded.
- Then the step indicator, a stretch, and the optional progress pill (unchanged API: `set_progress`).
- `set_status` is removed (already unused).

### Icons
Tool icons are bundled SVGs under `src/aa_tool/resources/icons/` (pine stroke, line style), rendered to a `QPixmap` via `PySide6.QtSvg.QSvgRenderer` at card-icon size. The NMSLO Segmentor ships `icons/segmentor.svg` (a document with a split line). The PyInstaller spec bundles `resources/icons/*.svg`.

## Visual language
Reuse the existing paper theme (`theme.py`): `--paper`/`--card`/`--pine`, Hanken Grotesk + Spline Sans Mono. New `theme.py` styles: board top bar + logo mark, hero, section header (`#secHead` + rule), `#toolCard` (hover lifts + pine border), card icon tile, and the `#backToTools` link. Approved mockups: a centered hero, agency section headers with a rule, lift-on-hover cards; the Back-to-Tools link at the far left of the tool top bar followed by a divider and context.

## Component boundaries (what depends on what)
- `tools.py` depends on `segmentor/tool.py` (to build it) — pure data + one import.
- `home_board.py` depends only on `tools.py` (registry) — knows nothing about any specific tool.
- `main_window.py` depends on `home_board.py` + `tools.py` — knows nothing about segmentation.
- `segmentor/` depends on the existing core (`ingest`, `model`, `export`, `render`) — unchanged.

## Testing approach (TDD, synthetic fixtures only)
- **Registry:** `TOOLS` contains the segmentor with the right id/name/category; its `icon` resource resolves via `resource_path` and exists.
- **HomeBoard (headless, offscreen):** building it from a 1-tool registry creates one section and one card; clicking the card invokes `on_launch` with `"nmslo_segmentor"`.
- **MainWindow (headless):** `launch_tool("nmslo_segmentor")` shows a tool widget; `show_board()` returns to the board and drops the tool widget.
- **SegmentorTool (headless):** `load_lease(folder)` ingests and builds the model (the moved version of the current main-window test); "Back to Tools" calls `on_back_to_tools`.
- **Existing segmentor tests** are updated for the moved module paths and the new `Header` signature; their behavior assertions are unchanged.
- All tests run headless via `QT_QPA_PLATFORM=offscreen`; real data in `example/` is never used.

## Out of scope (YAGNI)
- Search bar / Ctrl-K (revisit when there are many tools).
- Any second tool (only the NMSLO Segmentor card is real; mockup placeholders are not built).
- Renaming the internal `aa_tool` package (stays as-is; revisit if the repo grows).
