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
