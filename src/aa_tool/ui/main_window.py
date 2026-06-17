from pathlib import Path

from PySide6 import QtCore, QtWidgets

from aa_tool.ingest import scan_lease_folder
from aa_tool.model import SegmentationModel
from aa_tool.ui import theme
from aa_tool.ui.export_screen import ExportScreen
from aa_tool.ui.header import Header
from aa_tool.ui.segmentation_screen import SegmentationScreen


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AA State Abstract Tool")
        self.resize(1200, 820)

        self.stack = QtWidgets.QStackedWidget()
        self.setCentralWidget(self.stack)

        self.ingest_result = None
        self.model: SegmentationModel | None = None
        self._segmentation_screen: SegmentationScreen | None = None
        self._export_screen: ExportScreen | None = None

        self._build_folder_screen()

    def _build_folder_screen(self):
        page = QtWidgets.QWidget()
        page.setObjectName("screen")
        v = QtWidgets.QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(Header(active_step=1))

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

        self.folder_index = self.stack.addWidget(page)

    def _choose_folder(self):
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
        )
        self._swap_in(screen, self._segmentation_screen)
        self._segmentation_screen = screen

    def _show_export_screen(self) -> None:
        screen = ExportScreen(
            self.ingest_result, self.model, on_back=self._back_to_segmentation
        )
        self._swap_in(screen, self._export_screen)
        self._export_screen = screen

    def _back_to_segmentation(self) -> None:
        if self._segmentation_screen is not None:
            self.stack.setCurrentWidget(self._segmentation_screen)


def main() -> None:
    import sys

    app = QtWidgets.QApplication(sys.argv)
    theme.apply_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
