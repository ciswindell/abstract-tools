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
