"""Shared top bar used by every screen, so the app reads as one tool.

Shows the lease number, a 1·Open / 2·Segment / 3·Export step indicator, and a
right-hand area for screen-specific status (a progress pill + a status line).
"""

from PySide6 import QtCore, QtWidgets

from aa_tool.ui import theme

_STEPS = ["1 · Open", "2 · Segment", "3 · Export"]


class Header(QtWidgets.QWidget):
    def __init__(self, active_step: int, lease: str | None = None):
        super().__init__()
        self.setObjectName("header")

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(22, 11, 22, 11)
        layout.setSpacing(18)

        brand = QtWidgets.QLabel()
        brand.setObjectName("brand")
        if lease:
            brand.setText(f'Lease&nbsp;<span style="color:{theme.PINE}">{lease}</span>')
        else:
            brand.setText("AA State Abstract Tool")
        layout.addWidget(brand)

        for i, label in enumerate(_STEPS, start=1):
            chip = QtWidgets.QLabel(label)
            chip.setObjectName("stepActive" if i == active_step else "step")
            layout.addWidget(chip)

        layout.addStretch()

        # Progress pill (hidden until set_progress is called).
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

        # Status line (hidden until set_status is called).
        self._status = QtWidgets.QLabel()
        self._status.setObjectName("status")
        self._status.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self._status.setVisible(False)
        layout.addWidget(self._status)

    def set_status(self, text: str) -> None:
        self._status.setText(text)
        self._status.setVisible(True)

    def set_progress(self, value: int, maximum: int, text: str) -> None:
        self._bar.setMaximum(max(maximum, 1))
        self._bar.setValue(value)
        self._pill_text.setText(text)
        self._pill_wrap.setVisible(True)
