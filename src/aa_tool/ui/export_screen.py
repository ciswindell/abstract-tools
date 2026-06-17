from collections.abc import Callable
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from aa_tool.export import ExportSummary, build_summary, run_export
from aa_tool.ingest import IngestResult
from aa_tool.model import SegmentationModel


class ExportScreen(QtWidgets.QWidget):
    def __init__(
        self,
        ingest_result: IngestResult,
        model: SegmentationModel,
        on_back: Callable[[], None],
    ):
        super().__init__()
        self.ingest_result = ingest_result
        self.model = model
        self.on_back = on_back
        self.out_dir = self._default_out_dir()

        layout = QtWidgets.QVBoxLayout(self)

        documents = self.model.documents()
        doc_count, page_count, source_count, assignments = build_summary(
            ingest_result, documents
        )
        self.summary_label = QtWidgets.QLabel(
            f"{doc_count} documents · {page_count} pages merged · "
            f"{source_count} source files · assignments {', '.join(assignments)}"
        )
        layout.addWidget(self.summary_label)

        skipped = ingest_result.skipped
        if skipped:
            warn = QtWidgets.QLabel(
                "Skipped files: " + ", ".join(p.name for p, _ in skipped)
            )
            warn.setStyleSheet("color: #7a5c00;")
            layout.addWidget(warn)

        button_bar = QtWidgets.QHBoxLayout()
        self.back_button = QtWidgets.QPushButton("◀ Back to segmenting")
        self.back_button.clicked.connect(lambda: self.on_back())
        self.export_button = QtWidgets.QPushButton("Export PDF + Excel ▶")
        self.export_button.clicked.connect(self._on_export_clicked)
        button_bar.addWidget(self.back_button)
        button_bar.addStretch()
        button_bar.addWidget(self.export_button)
        layout.addStretch()
        layout.addLayout(button_bar)

    def _default_out_dir(self) -> Path:
        if self.ingest_result.sources:
            # lease folder = the grandparent of any source file (folder/<assignment>/<file>)
            return self.ingest_result.sources[0].path.parent.parent
        return Path.cwd()

    def do_export(self) -> ExportSummary:
        documents = self.model.documents()
        return run_export(self.ingest_result, documents, self.out_dir)

    def _on_export_clicked(self) -> None:
        chosen = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Choose output folder", str(self.out_dir)
        )
        if chosen:
            self.out_dir = Path(chosen)
        summary = self.do_export()
        QtWidgets.QMessageBox.information(
            self,
            "Export complete",
            f"Saved:\n{summary.pdf_path.name}\n{summary.xlsx_path.name}",
        )
