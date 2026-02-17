"""PyQt5 widget for document import through framework-neutral ImportView."""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from contracts.import_constants import SUPPORTED_EXTENSIONS
from ui.views.import_view import ImportView


class ImportWidget(QWidget):
    """UI adapter for selecting and submitting a document to ImportView."""

    def __init__(self, *, import_view: ImportView) -> None:
        super().__init__()
        self._import_view = import_view
        self._selected_file_path: str | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)

        self.select_button = QPushButton("Select file")
        self.select_button.clicked.connect(self._select_file)
        root_layout.addWidget(self.select_button)

        self.file_info_label = QLabel("No file selected")
        self.file_info_label.setWordWrap(True)
        root_layout.addWidget(self.file_info_label)

        action_layout = QHBoxLayout()
        self.import_button = QPushButton("Import")
        self.import_button.setEnabled(False)
        self.import_button.clicked.connect(self._submit_selected_file)
        action_layout.addWidget(self.import_button)
        action_layout.addStretch(1)
        root_layout.addLayout(action_layout)

        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        root_layout.addWidget(self.result_label)

        root_layout.addStretch(1)

    def _select_file(self) -> None:
        selected_file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select document to import",
            "",
            self._file_dialog_filter(),
        )
        if not selected_file_path:
            return

        self._selected_file_path = selected_file_path
        self.import_button.setEnabled(True)
        self.result_label.setText("")
        self.file_info_label.setText(self._build_file_info_text(selected_file_path))

    def _submit_selected_file(self) -> None:
        if not self._selected_file_path:
            self.result_label.setText("Please select a file before importing.")
            return

        result = self._import_view.submit_file(self._selected_file_path)
        if result.ok:
            data = result.data or {}
            document_id = str(data.get("id", ""))
            if document_id:
                self.result_label.setText(f"Import succeeded. document_id={document_id}")
            else:
                self.result_label.setText("Import succeeded.")
            return

        error = result.error
        if error is None:
            self.result_label.setText("Import failed with an unknown error.")
            return

        self.result_label.setText(f"Import failed: {error.code} - {error.message}")

    def _file_dialog_filter(self) -> str:
        patterns = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_EXTENSIONS))
        return f"Supported Documents ({patterns});;All Files (*)"

    def _build_file_info_text(self, file_path: str) -> str:
        path = Path(file_path)
        file_name = path.name
        file_format = (path.suffix or "(none)").lower()
        try:
            file_size_bytes = path.stat().st_size
            file_size_text = self._format_file_size(file_size_bytes)
        except OSError:
            file_size_text = "unknown"

        return f"Selected: {file_name} | Size: {file_size_text} | Format: {file_format}"

    def _format_file_size(self, size_bytes: int) -> str:
        units = ["B", "KB", "MB", "GB", "TB"]
        value = float(max(0, size_bytes))
        for unit in units:
            if value < 1024.0 or unit == units[-1]:
                if unit == "B":
                    return f"{int(value)} {unit}"
                return f"{value:.1f} {unit}"
            value /= 1024.0
        return f"{size_bytes} B"

