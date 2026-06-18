from collections.abc import Callable
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from aa_tool.ui.header import Header
from aa_tool.ui.tiff_converter.plan_screen import CONVERTER_STEPS, PlanScreen


class TiffConverterTool(QtWidgets.QWidget):
    def __init__(self, on_back_to_tools: Callable[[], None]):
        super().__init__()
        self.setObjectName("screen")
        self.on_back_to_tools = on_back_to_tools
        self.plan_screen: PlanScreen | None = None

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
            context_html="Batch TIFF to PDF Converter",
            on_back_to_tools=self.on_back_to_tools,
            steps=CONVERTER_STEPS,
        ))

        center = QtWidgets.QVBoxLayout()
        center.setContentsMargins(0, 0, 0, 0)
        center.setSpacing(14)
        center.addStretch()
        h1 = QtWidgets.QLabel("Convert a folder of TIFFs")
        h1.setObjectName("h1")
        h1.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        sub = QtWidgets.QLabel(
            "Choose a folder. Every TIFF becomes a PDF, the folder structure is\n"
            "mirrored, and other files are copied across unchanged."
        )
        sub.setObjectName("sub")
        sub.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        button = QtWidgets.QPushButton("Choose folder…")
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
            self, "Choose folder of TIFFs", str(Path.home())
        )
        if folder:
            self.load_folder(Path(folder))

    def load_folder(self, folder: Path) -> None:
        screen = PlanScreen(
            folder,
            on_back_to_tools=self.on_back_to_tools,
            on_new_folder=self._restart,
        )
        if self.plan_screen is not None:
            self.stack.removeWidget(self.plan_screen)
            self.plan_screen.shutdown()
            self.plan_screen.deleteLater()
        index = self.stack.addWidget(screen)
        self.stack.setCurrentIndex(index)
        self.plan_screen = screen

    def _restart(self) -> None:
        self.stack.setCurrentIndex(self.open_index)
        if self.plan_screen is not None:
            self.stack.removeWidget(self.plan_screen)
            self.plan_screen.shutdown()
            self.plan_screen.deleteLater()
            self.plan_screen = None

    def shutdown(self) -> None:
        if self.plan_screen is not None:
            self.plan_screen.shutdown()

    def closeEvent(self, event):  # noqa: N802 (Qt override)
        self.shutdown()
        super().closeEvent(event)
