from collections.abc import Callable

from PySide6 import QtCore, QtWidgets

from abstract_tools.tools import Tool, tools_by_category
from abstract_tools.ui.icons import svg_pixmap


class _ToolCard(QtWidgets.QFrame):
    def __init__(self, tool: Tool, on_launch: Callable[[str], None]):
        super().__init__()
        self.setObjectName("toolCard")
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._tool_id = tool.id
        self._on_launch = on_launch

        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(22, 22, 22, 22)
        v.setSpacing(12)

        icon = QtWidgets.QLabel()
        icon.setObjectName("toolCardIcon")
        icon.setFixedSize(46, 46)
        icon.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(svg_pixmap(tool.icon, 24))
        v.addWidget(icon)

        name = QtWidgets.QLabel(tool.name)
        name.setObjectName("toolCardName")
        v.addWidget(name)

        desc = QtWidgets.QLabel(tool.description)
        desc.setObjectName("toolCardDesc")
        desc.setWordWrap(True)
        v.addWidget(desc)
        v.addStretch()

    def mousePressEvent(self, event):  # noqa: N802 (Qt override)
        if event is None or event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._on_launch(self._tool_id)


class HomeBoard(QtWidgets.QWidget):
    def __init__(self, tools: list[Tool], on_launch: Callable[[str], None]):
        super().__init__()
        self.setObjectName("screen")
        self.cards: dict[str, QtWidgets.QWidget] = {}

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        top = QtWidgets.QWidget()
        top.setObjectName("boardTop")
        top_row = QtWidgets.QHBoxLayout(top)
        top_row.setContentsMargins(28, 14, 28, 14)
        brand = QtWidgets.QLabel("Abstract Tools")
        brand.setObjectName("boardBrand")
        top_row.addWidget(brand)
        top_row.addStretch()
        outer.addWidget(top)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        inner = QtWidgets.QWidget()
        inner.setObjectName("boardBody")
        body = QtWidgets.QVBoxLayout(inner)
        body.setContentsMargins(28, 30, 28, 60)
        body.setSpacing(0)

        hero = QtWidgets.QLabel("Tools")
        hero.setObjectName("boardHero")
        hero.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        sub = QtWidgets.QLabel("Select a tool to get started")
        sub.setObjectName("boardHeroSub")
        sub.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        body.addWidget(hero)
        body.addWidget(sub)
        body.addSpacing(24)

        for category, group in tools_by_category(tools).items():
            head_row = QtWidgets.QHBoxLayout()
            head_row.setSpacing(12)
            label = QtWidgets.QLabel(category)
            label.setObjectName("secHead")
            rule = QtWidgets.QFrame()
            rule.setObjectName("secRule")
            head_row.addWidget(label)
            head_row.addWidget(rule, 1)
            body.addSpacing(12)
            body.addLayout(head_row)
            body.addSpacing(14)

            grid = QtWidgets.QGridLayout()
            grid.setSpacing(16)
            for i, tool in enumerate(group):
                card = _ToolCard(tool, on_launch)
                self.cards[tool.id] = card
                grid.addWidget(card, i // 3, i % 3)
            # Keep cards left-aligned at their natural width in a 3-col grid.
            for col in range(3):
                grid.setColumnStretch(col, 1)
            body.addLayout(grid)

        body.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
