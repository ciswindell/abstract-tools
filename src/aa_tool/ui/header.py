"""Shared top bar. On a tool screen it shows a Back-to-Tools link, the tool or
lease context, a step indicator, and an optional progress pill.
"""

from collections.abc import Callable

from PySide6 import QtCore, QtWidgets

_STEPS = ["1 · Open", "2 · Segment", "3 · Export"]


class Header(QtWidgets.QWidget):
    def __init__(
        self,
        active_step: int,
        context_html: str = "",
        on_back_to_tools: Callable[[], None] | None = None,
        lease: str | None = None,
        steps: list[str] | None = None,
    ):
        super().__init__()
        self.setObjectName("header")

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(22, 11, 22, 11)
        layout.setSpacing(16)

        self.back_button = None
        if on_back_to_tools is not None:
            self.back_button = QtWidgets.QPushButton("←  Back to Tools")
            self.back_button.setObjectName("backToTools")
            self.back_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            self.back_button.clicked.connect(lambda: on_back_to_tools())
            layout.addWidget(self.back_button)
            divider = QtWidgets.QFrame()
            divider.setObjectName("hdrDivider")
            divider.setFixedHeight(22)
            layout.addWidget(divider)

        brand = QtWidgets.QLabel()
        brand.setObjectName("brand")
        if context_html:
            brand.setText(context_html)
        elif lease:
            brand.setText(f"Lease&nbsp;{lease}")
        else:
            brand.setText("Abstract Tools")
        layout.addWidget(brand)

        step_labels = steps if steps is not None else _STEPS
        for i, label in enumerate(step_labels, start=1):
            chip = QtWidgets.QLabel(label)
            chip.setObjectName("stepActive" if i == active_step else "step")
            layout.addWidget(chip)

        layout.addStretch()

        self._pill_wrap = QtWidgets.QWidget()
        pill_row = QtWidgets.QHBoxLayout(self._pill_wrap)
        pill_row.setContentsMargins(0, 0, 0, 0)
        pill_row.setSpacing(8)
        self._bar = QtWidgets.QProgressBar()
        self._bar.setObjectName("pill")
        self._bar.setTextVisible(False)
        self._pill_text = QtWidgets.QLabel()
        self._pill_text.setObjectName("pillText")
        pill_row.addWidget(self._bar)
        pill_row.addWidget(self._pill_text)
        self._pill_wrap.setVisible(False)
        layout.addWidget(self._pill_wrap)

    def set_progress(self, value: int, maximum: int, text: str) -> None:
        self._bar.setMaximum(max(maximum, 1))
        self._bar.setValue(value)
        self._pill_text.setText(text)
        self._pill_wrap.setVisible(True)
