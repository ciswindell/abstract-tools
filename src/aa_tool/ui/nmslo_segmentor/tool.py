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

    def _swap_in(self, screen: QtWidgets.QWidget, previous: QtWidgets.QWidget | None) -> None:
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
