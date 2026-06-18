# src/abstract_tools/ui/update_banner.py
from PySide6 import QtCore, QtWidgets

from abstract_tools.update_check import UpdateInfo


class UpdateBanner(QtWidgets.QFrame):
    """A dismissible 'new version available' bar shown above the main stack."""

    download_requested = QtCore.Signal(object)  # UpdateInfo
    dismissed = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("updateBanner")
        self.info: UpdateInfo | None = None

        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(28, 10, 16, 10)
        row.setSpacing(12)

        self.text_label = QtWidgets.QLabel("")
        self.text_label.setObjectName("updateBannerText")
        row.addWidget(self.text_label)
        row.addStretch()

        self.download_button = QtWidgets.QPushButton("Download update")
        self.download_button.setObjectName("primary")
        self.download_button.clicked.connect(self._on_download)
        row.addWidget(self.download_button)

        self.close_button = QtWidgets.QPushButton("✕")
        self.close_button.setObjectName("ghost")
        self.close_button.setFixedWidth(34)
        self.close_button.clicked.connect(self._on_close)
        row.addWidget(self.close_button)

        self.hide()

    def show_update(self, info: UpdateInfo) -> None:
        self.info = info
        self.text_label.setText(f"Version {info.latest_version} is available")
        self.download_button.setEnabled(True)
        self.show()

    def set_status(self, text: str) -> None:
        self.text_label.setText(text)

    def _on_download(self) -> None:
        if self.info is not None:
            self.download_requested.emit(self.info)

    def _on_close(self) -> None:
        self.hide()
        self.dismissed.emit()
