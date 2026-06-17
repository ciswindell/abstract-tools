"""The segmentation workbench — the screen where the user marks document
boundaries. Designed so the eye stays at the top: every control sits above the
page, classification is shown by button colour (green = first, yellow =
continuation) for peripheral vision, and F/C classify-and-auto-advance so the
whole lease can be worked from the keyboard.
"""

from collections.abc import Callable

from PySide6 import QtCore, QtGui, QtWidgets

from aa_tool.model import SegmentationModel
from aa_tool.render import page_size, render_page_png
from aa_tool.ui.header import Header

_ZOOM_STEP = 1.2
_MIN_ZOOM = 0.2
_MAX_ZOOM = 5.0


def _repolish(widget: QtWidgets.QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class _PageRow(QtWidgets.QFrame):
    """A clickable page entry in the rail."""

    def __init__(self, global_index: int, page_no: int, source: str, on_click):
        super().__init__()
        self.global_index = global_index
        self._on_click = on_click
        self.setObjectName("pageRow")
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(22, 6, 10, 6)
        row.setSpacing(12)
        self.label = QtWidgets.QLabel(f"Page {page_no}")
        self.label.setObjectName("pageLabel")
        self.src = QtWidgets.QLabel(source)
        self.src.setObjectName("pageSrc")
        row.addWidget(self.label)
        row.addWidget(self.src)
        row.addStretch()

    def mousePressEvent(self, event):  # noqa: N802 (Qt override)
        self._on_click(self.global_index)

    def set_current(self, current: bool) -> None:
        self.setObjectName("pageRowCur" if current else "pageRow")
        self.label.setObjectName("pageLabelCur" if current else "pageLabel")
        _repolish(self)
        _repolish(self.label)


class SegmentationScreen(QtWidgets.QWidget):
    def __init__(
        self,
        model: SegmentationModel,
        lease_number: str,
        on_continue: Callable[[], None],
    ):
        super().__init__()
        self.setObjectName("screen")
        self.model = model
        self.on_continue = on_continue
        self.selected_index = 0
        self._zoom = None  # explicit zoom factor, or None when a fit mode is active
        self._fit = "width"  # "width" | "page" | None
        self._reviewed: set[int] = set()
        self._page_rows: dict[int, _PageRow] = {}

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header = Header(active_step=2, lease=lease_number)
        outer.addWidget(self.header)

        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        outer.addLayout(body, 1)

        body.addWidget(self._build_rail())
        body.addWidget(self._build_stage(), 1)

        outer.addWidget(self._build_legend())

        self.refresh_list()
        if self.model.pages:
            self.select_page(0)

    # ---- rail -------------------------------------------------------------
    def _build_rail(self) -> QtWidgets.QWidget:
        scroll = QtWidgets.QScrollArea()
        scroll.setObjectName("rail")
        scroll.setFixedWidth(240)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._rail_scroll = scroll
        self._rail_inner = QtWidgets.QWidget()
        self._rail_inner.setObjectName("railInner")
        self._rail_layout = QtWidgets.QVBoxLayout(self._rail_inner)
        self._rail_layout.setContentsMargins(10, 14, 10, 14)
        self._rail_layout.setSpacing(2)
        title = QtWidgets.QLabel("DOCUMENTS")
        title.setObjectName("railTitle")
        self._rail_layout.addWidget(title)
        scroll.setWidget(self._rail_inner)
        return scroll

    def refresh_list(self) -> None:
        # Clear all rows except the title (index 0).
        while self._rail_layout.count() > 1:
            item = self._rail_layout.takeAt(1)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._page_rows = {}

        doc_no = 0
        for page in self.model.pages:
            gi = page.global_index
            if self.model.is_first_page(gi):
                doc_no += 1
                head = QtWidgets.QLabel(f"●  DOC {doc_no} · {page.source.file_number}")
                head.setObjectName("docHead")
                head.setContentsMargins(6, 8, 6, 2)
                self._rail_layout.addWidget(head)
            row = _PageRow(gi, gi + 1, page.source.file_number, self.select_page)
            self._rail_layout.addWidget(row)
            self._page_rows[gi] = row
        self._rail_layout.addStretch()
        # Re-apply current highlight after a rebuild.
        if self.selected_index in self._page_rows:
            self._page_rows[self.selected_index].set_current(True)

    # ---- stage (controls + canvas) ---------------------------------------
    def _build_stage(self) -> QtWidgets.QWidget:
        stage = QtWidgets.QWidget()
        stage.setObjectName("screen")
        v = QtWidgets.QVBoxLayout(stage)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self._build_controls())

        self.canvas = QtWidgets.QScrollArea()
        self.canvas.setObjectName("canvas")
        self.canvas.setWidgetResizable(False)
        self.canvas.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.page_image = QtWidgets.QLabel()
        self.page_image.setObjectName("pageImage")
        self.page_image.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.canvas.setWidget(self.page_image)
        v.addWidget(self.canvas, 1)
        return stage

    def _build_controls(self) -> QtWidgets.QWidget:
        bar = QtWidgets.QWidget()
        bar.setObjectName("controls")
        h = QtWidgets.QHBoxLayout(bar)
        h.setContentsMargins(18, 12, 18, 12)
        h.setSpacing(14)

        self.prev_button = QtWidgets.QPushButton("←")
        self.next_button = QtWidgets.QPushButton("→")
        for b in (self.prev_button, self.next_button):
            b.setObjectName("nav")
        self.prev_button.setToolTip("Previous page  (←)")
        self.next_button.setToolTip("Next page  (→)")
        self.prev_button.clicked.connect(lambda: self.select_page(self.selected_index - 1))
        self.next_button.clicked.connect(lambda: self.select_page(self.selected_index + 1))
        h.addWidget(self.prev_button)
        h.addWidget(self.next_button)

        self.first_button = QtWidgets.QPushButton("First Page   F")
        self.first_button.setObjectName("classify")
        self.first_button.setProperty("kind", "first")
        self.first_button.clicked.connect(self.mark_first_page)
        self.continuation_button = QtWidgets.QPushButton("Continuation   C")
        self.continuation_button.setObjectName("classify")
        self.continuation_button.setProperty("kind", "cont")
        self.continuation_button.clicked.connect(self.mark_continuation)
        h.addWidget(self.first_button, 1)
        h.addWidget(self.continuation_button, 1)

        h.addStretch()

        self.fit_width_button = QtWidgets.QPushButton("Fit width")
        self.fit_page_button = QtWidgets.QPushButton("Fit page")
        self.zoom_out_button = QtWidgets.QPushButton("−")
        self.zoom_in_button = QtWidgets.QPushButton("+")
        for b in (self.fit_width_button, self.fit_page_button, self.zoom_out_button, self.zoom_in_button):
            b.setObjectName("zoom")
        self.fit_width_button.clicked.connect(lambda: self._set_fit("width"))
        self.fit_page_button.clicked.connect(lambda: self._set_fit("page"))
        self.zoom_out_button.clicked.connect(lambda: self._nudge_zoom(1 / _ZOOM_STEP))
        self.zoom_in_button.clicked.connect(lambda: self._nudge_zoom(_ZOOM_STEP))
        self.zoom_label = QtWidgets.QLabel("--")
        self.zoom_label.setObjectName("zoomLabel")
        self.zoom_label.setFixedWidth(46)
        self.zoom_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        h.addWidget(self.fit_width_button)
        h.addWidget(self.fit_page_button)
        h.addWidget(self.zoom_out_button)
        h.addWidget(self.zoom_label)
        h.addWidget(self.zoom_in_button)

        self.continue_button = QtWidgets.QPushButton("Continue to export  →")
        self.continue_button.setObjectName("finish")
        self.continue_button.clicked.connect(lambda: self.on_continue())
        h.addWidget(self.continue_button)

        # Keyboard shortcuts mirror the buttons.
        for key, slot in [
            ("F", self.mark_first_page),
            ("C", self.mark_continuation),
            ("Left", lambda: self.select_page(self.selected_index - 1)),
            ("Right", lambda: self.select_page(self.selected_index + 1)),
            ("Ctrl++", lambda: self._nudge_zoom(_ZOOM_STEP)),
            ("Ctrl+=", lambda: self._nudge_zoom(_ZOOM_STEP)),
            ("Ctrl+-", lambda: self._nudge_zoom(1 / _ZOOM_STEP)),
            ("Ctrl+0", lambda: self._set_fit("width")),
        ]:
            QtGui.QShortcut(QtGui.QKeySequence(key), self, slot)
        return bar

    def _build_legend(self) -> QtWidgets.QWidget:
        bar = QtWidgets.QWidget()
        bar.setObjectName("legend")
        h = QtWidgets.QHBoxLayout(bar)
        h.setContentsMargins(22, 7, 22, 7)
        h.setSpacing(22)
        for text in [
            "← →  move between pages",
            "F  first page · auto-advances",
            "C  continuation · auto-advances",
            "Ctrl + / −  zoom",
            "Ctrl 0  fit width",
        ]:
            lbl = QtWidgets.QLabel(text)
            lbl.setObjectName("legend")
            h.addWidget(lbl)
        h.addStretch()
        return bar

    # ---- selection & classification --------------------------------------
    def select_page(self, global_index: int) -> None:
        if not self.model.pages:
            return
        global_index = max(0, min(global_index, len(self.model.pages) - 1))
        if self.selected_index in self._page_rows:
            self._page_rows[self.selected_index].set_current(False)
        self.selected_index = global_index
        self._reviewed.add(global_index)
        if global_index in self._page_rows:
            self._page_rows[global_index].set_current(True)
            self._rail_scroll.ensureWidgetVisible(self._page_rows[global_index])
        self._update_buttons()
        self._update_header()
        self._render()

    def _update_buttons(self) -> None:
        is_first = self.model.is_first_page(self.selected_index)
        self.first_button.setProperty("active", "true" if is_first else "false")
        self.continuation_button.setProperty("active", "false" if is_first else "true")
        self.continuation_button.setEnabled(self.selected_index != 0)
        _repolish(self.first_button)
        _repolish(self.continuation_button)

    def _update_header(self) -> None:
        total_pages = len(self.model.pages)
        self.header.set_progress(
            len(self._reviewed), total_pages,
            f"{len(self._reviewed)} of {total_pages} pages reviewed",
        )

    def mark_first_page(self) -> None:
        self.model.set_first_page(self.selected_index)
        self.refresh_list()
        self._advance()

    def mark_continuation(self) -> None:
        if self.selected_index == 0:
            return
        self.model.set_continuation(self.selected_index)
        self.refresh_list()
        self._advance()

    def _advance(self) -> None:
        # Auto-advance to the very next page (never skips classified pages).
        self.select_page(self.selected_index + 1)

    # ---- zoom & rendering -------------------------------------------------
    def _set_fit(self, mode: str) -> None:
        self._fit = mode
        self._zoom = None
        self._render()

    def _nudge_zoom(self, factor: float) -> None:
        self._zoom = max(_MIN_ZOOM, min(_MAX_ZOOM, self._effective_zoom() * factor))
        self._fit = None
        self._render()

    def _effective_zoom(self) -> float:
        if self._zoom is not None:
            return self._zoom
        if not self.model.pages:
            return 1.0
        page = self.model.pages[self.selected_index]
        pt_w, pt_h = page_size(page.source.path, page.source_page_index)
        vp = self.canvas.viewport()
        avail_w = vp.width() - 48
        avail_h = vp.height() - 48
        if avail_w <= 0 or pt_w <= 0:
            return 1.0
        if self._fit == "page" and avail_h > 0 and pt_h > 0:
            return max(_MIN_ZOOM, min(avail_w / pt_w, avail_h / pt_h))
        return max(_MIN_ZOOM, avail_w / pt_w)

    def _render(self) -> None:
        if not self.model.pages:
            return
        page = self.model.pages[self.selected_index]
        zoom = self._effective_zoom()
        png = render_page_png(page.source.path, page.source_page_index, zoom)
        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(png)
        self.page_image.setPixmap(pixmap)
        self.page_image.resize(pixmap.size())
        self.zoom_label.setText(f"{round(zoom * 100)}%")

    def resizeEvent(self, event):  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        if self._fit is not None:
            self._render()
