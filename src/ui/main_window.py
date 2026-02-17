"""Main PyQt5 window for local-audiobook application."""

from __future__ import annotations

from typing import Any

from PyQt5.QtWidgets import QMainWindow, QTabWidget, QVBoxLayout, QWidget, QLabel

from ui.views.import_view import ImportView
from ui.widgets.import_widget import ImportWidget


class MainWindow(QMainWindow):
    """Main application window with tabbed interface."""

    def __init__(self, *, readiness_status: dict[str, Any], import_view: ImportView | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Local Audiobook Converter")
        self.setMinimumSize(800, 600)
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Display readiness status at the top
        status = readiness_status.get("status", "unknown")
        status_text = f"Readiness Status: {status}"
        if status == "not_ready":
            remediation = readiness_status.get("remediation", [])
            if remediation:
                status_text += f"\nRemediation needed: {len(remediation)} item(s)"
        
        status_label = QLabel(status_text)
        layout.addWidget(status_label)
        
        # Create tab widget for different views
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Add tabs for the main views
        self.tabs.addTab(QLabel("Conversion view - to be implemented"), "Conversion")
        if import_view is not None:
            self.tabs.addTab(ImportWidget(import_view=import_view), "Import")
        else:
            self.tabs.addTab(QLabel("Import view unavailable"), "Import")
        self.tabs.addTab(QLabel("Library view - to be implemented"), "Library")
