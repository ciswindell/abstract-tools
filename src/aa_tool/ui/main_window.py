from pathlib import Path

from PySide6 import QtCore, QtWidgets

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
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        button = QtWidgets.QPushButton("Choose lease folder…")
        button.clicked.connect(self._choose_folder)
        layout.addWidget(label)
        layout.addWidget(button, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
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
