from collections.abc import Callable
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from aa_tool.export import ExportSummary, build_summary, run_export
from aa_tool.ingest import IngestResult
from aa_tool.model import SegmentationModel
from aa_tool.ui import theme
from aa_tool.ui.header import Header


class ExportScreen(QtWidgets.QWidget):
    def __init__(
        self,
        ingest_result: IngestResult,
        model: SegmentationModel,
        on_back: Callable[[], None],
        on_new_lease: Callable[[], None],
        on_back_to_tools: Callable[[], None],
    ):
        super().__init__()
        self.setObjectName("screen")
        self.ingest_result = ingest_result
        self.model = model
        self.on_back = on_back
        self.on_new_lease = on_new_lease
        self.on_back_to_tools = on_back_to_tools
        self.out_dir = self._default_out_dir()

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(Header(
            active_step=3,
            context_html=f'Lease&nbsp;<span style="color:{theme.PINE}">{ingest_result.lease_number}</span>',
            on_back_to_tools=on_back_to_tools,
        ))

        documents = self.model.documents()
        doc_count, page_count, source_count, _assignments = build_summary(
            ingest_result, documents
        )

        # Centered hero, mirroring the Open screen: everything tight in the middle.
        center = QtWidgets.QVBoxLayout()
        center.setContentsMargins(48, 0, 48, 0)
        center.setSpacing(16)
        center.addStretch()
        outer.addLayout(center, 1)

        title = QtWidgets.QLabel("Ready to export")
        title.setObjectName("h1")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        center.addWidget(title)

        self.summary_label = QtWidgets.QLabel(
            f"{source_count} source files merged\n"
            f"{page_count} pages\n"
            f"{doc_count} segmented documents"
        )
        self.summary_label.setObjectName("sub")
        self.summary_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        center.addWidget(self.summary_label)

        if ingest_result.skipped:
            warn = QtWidgets.QLabel(
                "Skipped files: " + ", ".join(p.name for p, _ in ingest_result.skipped)
            )
            warn.setObjectName("warn")
            warn.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            center.addWidget(warn)

        center.addSpacing(10)

        # Destination is shown explicitly (defaults to the lease folder) so the
        # user always sees where files will go — no surprise from a dialog.
        dest = QtWidgets.QHBoxLayout()
        dest.setSpacing(10)
        self.path_label = QtWidgets.QLabel(str(self.out_dir))
        self.path_label.setObjectName("savePath")
        change_button = QtWidgets.QPushButton("Change…")
        change_button.setObjectName("ghost")
        change_button.clicked.connect(self._change_folder)
        dest.addStretch()
        dest.addWidget(QtWidgets.QLabel("Save to:"))
        dest.addWidget(self.path_label)
        dest.addWidget(change_button)
        dest.addStretch()
        center.addLayout(dest)

        center.addSpacing(10)
        buttons = QtWidgets.QHBoxLayout()
        buttons.setSpacing(12)
        self.back_button = QtWidgets.QPushButton("←  Back to segmenting")
        self.back_button.setObjectName("ghost")
        self.back_button.clicked.connect(lambda: self.on_back())
        self.export_button = QtWidgets.QPushButton("Export PDF + Excel  →")
        self.export_button.setObjectName("primary")
        self.export_button.clicked.connect(self._on_export_clicked)
        buttons.addStretch()
        buttons.addWidget(self.back_button)
        buttons.addWidget(self.export_button)
        buttons.addStretch()
        center.addLayout(buttons)

        # Inline, on-theme result shown after a successful export (replaces the
        # old unreadable popup). Hidden until Export runs.
        self.result_label = QtWidgets.QLabel()
        self.result_label.setObjectName("success")
        self.result_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.result_label.setVisible(False)
        center.addSpacing(6)
        center.addWidget(self.result_label)

        # Shown after export so the user can move on to the next lease.
        self.new_lease_button = QtWidgets.QPushButton("Process another lease  →")
        self.new_lease_button.setObjectName("primary")
        self.new_lease_button.clicked.connect(lambda: self.on_new_lease())
        self.new_lease_button.setVisible(False)
        center.addSpacing(4)
        center.addWidget(self.new_lease_button, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        center.addStretch()

    def _default_out_dir(self) -> Path:
        if self.ingest_result.sources:
            # lease folder = the grandparent of any source file (folder/<assignment>/<file>)
            return self.ingest_result.sources[0].path.parent.parent
        return Path.cwd()

    def do_export(self) -> ExportSummary:
        documents = self.model.documents()
        return run_export(self.ingest_result, documents, self.out_dir)

    def _change_folder(self) -> None:
        chosen = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Choose output folder", str(self.out_dir)
        )
        if chosen:
            self.out_dir = Path(chosen)
            self.path_label.setText(str(self.out_dir))

    def _on_export_clicked(self) -> None:
        # Saves to the destination shown on screen — no surprise dialog.
        self.do_export()
        self.result_label.setText(f"✓ Exported 2 files to {self.out_dir}")
        self.result_label.setVisible(True)
        self.new_lease_button.setVisible(True)
