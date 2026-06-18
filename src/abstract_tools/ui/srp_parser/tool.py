# src/abstract_tools/ui/srp_parser/tool.py
from collections.abc import Callable

from PySide6 import QtWidgets

from abstract_tools.ui.srp_parser.drop_screen import DropScreen


class SrpParserTool(QtWidgets.QWidget):
    """Root widget for the SRP Parser tool."""

    def __init__(self, on_back_to_tools: Callable[[], None]):
        super().__init__()
        self.setObjectName("screen")

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.screen = DropScreen(on_back_to_tools=on_back_to_tools)
        outer.addWidget(self.screen)

    def shutdown(self) -> None:
        self.screen.shutdown()

    def closeEvent(self, event):  # noqa: N802 (Qt override)
        self.shutdown()
        super().closeEvent(event)
