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
        try:
            png = render_page_png(page.source.path, page.source_page_index)
        except Exception:
            self.preview.clear()
            return
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
