"""PyQt5 widget for conversion readiness, configuration, progress, and diagnostics."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QStandardItemModel
from PyQt5.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class _WorkerSignalBridge(QObject):
    """Qt bridge to route worker callbacks through thread-safe Qt signals."""

    readiness_refreshed = pyqtSignal(object)
    conversion_progressed = pyqtSignal(object)
    conversion_state_changed = pyqtSignal(object)
    conversion_failed = pyqtSignal(object)


class ConversionWidget(QWidget):
    """UI adapter bound to ConversionView state and ConversionWorker callbacks."""

    def __init__(
        self,
        *,
        conversion_view: Any,
        conversion_worker: Any,
        conversion_presenter: Any,
    ) -> None:
        super().__init__()
        self._view = conversion_view
        self._worker = conversion_worker
        self._presenter = conversion_presenter

        self._active_job_id: str = ""
        self._active_correlation_id: str = ""
        self._document_id: str = ""  # set via set_document_id() after import

        self._bridge = _WorkerSignalBridge(self)
        self._worker.on_readiness_refreshed(self._bridge.readiness_refreshed.emit)
        self._worker.on_conversion_progressed(self._bridge.conversion_progressed.emit)
        self._worker.on_conversion_state_changed(self._bridge.conversion_state_changed.emit)
        self._worker.on_conversion_failed(self._bridge.conversion_failed.emit)

        self._bridge.readiness_refreshed.connect(self._on_worker_state_updated)
        self._bridge.conversion_progressed.connect(self._on_worker_state_updated)
        self._bridge.conversion_state_changed.connect(self._on_worker_state_updated)
        self._bridge.conversion_failed.connect(self._on_worker_state_updated)

        self._build_ui()
        self._sync_from_state()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        readiness_group = QGroupBox("Readiness")
        readiness_layout = QVBoxLayout(readiness_group)
        self.readiness_indicator_label = QLabel("Status: unknown")
        readiness_layout.addWidget(self.readiness_indicator_label)
        self.remediation_label = QLabel("")
        self.remediation_label.setWordWrap(True)
        readiness_layout.addWidget(self.remediation_label)
        root.addWidget(readiness_group)

        config_group = QGroupBox("Configuration")
        config_form = QFormLayout(config_group)

        self.engine_combo = QComboBox()
        self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)
        config_form.addRow("Engine", self.engine_combo)

        self.voice_combo = QComboBox()
        config_form.addRow("Voice", self.voice_combo)

        self.language_combo = QComboBox()
        config_form.addRow("Language", self.language_combo)

        self.output_format_combo = QComboBox()
        config_form.addRow("Output format", self.output_format_combo)

        rate_layout = QHBoxLayout()
        self.speech_rate_slider = QSlider()
        self.speech_rate_slider.setOrientation(Qt.Horizontal)
        self.speech_rate_slider.valueChanged.connect(self._on_speech_rate_changed)
        self.speech_rate_value_label = QLabel("1.00")
        rate_layout.addWidget(self.speech_rate_slider)
        rate_layout.addWidget(self.speech_rate_value_label)
        config_form.addRow("Speech rate", rate_layout)

        root.addWidget(config_group)

        action_layout = QHBoxLayout()
        self.convert_button = QPushButton("Convert")
        self.convert_button.clicked.connect(self._on_convert_clicked)
        action_layout.addWidget(self.convert_button)
        action_layout.addStretch(1)
        root.addLayout(action_layout)

        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        self.progress_label = QLabel("Queued")
        progress_layout.addWidget(self.progress_label)
        root.addWidget(progress_group)

        diagnostics_group = QGroupBox("Diagnostics")
        diagnostics_layout = QVBoxLayout(diagnostics_group)
        self.diagnostics_toggle = QToolButton()
        self.diagnostics_toggle.setText("Show details")
        self.diagnostics_toggle.setCheckable(True)
        self.diagnostics_toggle.toggled.connect(self._on_diagnostics_toggled)
        diagnostics_layout.addWidget(self.diagnostics_toggle)

        self.diagnostics_content = QWidget()
        diagnostics_content_layout = QVBoxLayout(self.diagnostics_content)
        self.diagnostics_summary_label = QLabel("")
        self.diagnostics_summary_label.setWordWrap(True)
        diagnostics_content_layout.addWidget(self.diagnostics_summary_label)

        self.diagnostics_remediation_label = QLabel("")
        self.diagnostics_remediation_label.setWordWrap(True)
        diagnostics_content_layout.addWidget(self.diagnostics_remediation_label)

        self.diagnostics_details = QPlainTextEdit()
        self.diagnostics_details.setReadOnly(True)
        diagnostics_content_layout.addWidget(self.diagnostics_details)

        diagnostics_actions = QHBoxLayout()
        self.retry_button = QPushButton("Retry")
        self.retry_button.clicked.connect(self._on_retry_clicked)
        diagnostics_actions.addWidget(self.retry_button)
        self.copy_details_button = QPushButton("Copy support details")
        self.copy_details_button.clicked.connect(self._on_copy_details_clicked)
        diagnostics_actions.addWidget(self.copy_details_button)
        diagnostics_actions.addStretch(1)
        diagnostics_content_layout.addLayout(diagnostics_actions)

        diagnostics_layout.addWidget(self.diagnostics_content)
        root.addWidget(diagnostics_group)

        root.addStretch(1)

    def _on_worker_state_updated(self, _: object) -> None:
        self._sync_from_state()

    def _sync_from_state(self) -> None:
        state = dict(self._view.current_state)
        self._sync_readiness(state)
        self._sync_configuration(state)
        self._sync_conversion_progress(state)
        self._sync_diagnostics(state)

    def _sync_readiness(self, state: dict[str, Any]) -> None:
        status = str(state.get("status", "not_ready"))
        self.readiness_indicator_label.setText(f"Status: {status}")

        remediation_items = [str(item) for item in state.get("remediation_items", [])]
        if remediation_items:
            self.remediation_label.setText("\n".join(f"• {item}" for item in remediation_items))
        else:
            self.remediation_label.setText("No remediation required.")

        self.convert_button.setEnabled(bool(state.get("start_enabled", False)))

    def _sync_configuration(self, state: dict[str, Any]) -> None:
        options = dict(state.get("configuration_options", {}))
        self._populate_combo_with_options(self.engine_combo, options.get("engines", []))
        self._populate_voice_combo(options.get("voices", []))
        self._populate_combo_with_options(self.language_combo, options.get("languages", []))
        self._populate_combo_with_options(self.output_format_combo, options.get("output_formats", []))

        speech_rate = dict(options.get("speech_rate", {}))
        min_rate = float(speech_rate.get("min", 0.5) or 0.5)
        max_rate = float(speech_rate.get("max", 2.0) or 2.0)
        step = float(speech_rate.get("step", 0.05) or 0.05)
        max_slider = int(round((max_rate - min_rate) / step))
        self.speech_rate_slider.blockSignals(True)
        self.speech_rate_slider.setRange(0, max(0, max_slider))
        current_rate = self._get_selected_speech_rate(min_rate=min_rate, step=step)
        slider_value = int(round((current_rate - min_rate) / step))
        self.speech_rate_slider.setValue(max(0, min(max_slider, slider_value)))
        self.speech_rate_slider.blockSignals(False)
        self.speech_rate_value_label.setText(f"{current_rate:.2f}")

    def _sync_conversion_progress(self, state: dict[str, Any]) -> None:
        conversion = dict(state.get("conversion", {}))
        status = str(conversion.get("status", "queued"))
        percent = int(conversion.get("progress_percent", 0) or 0)
        chunk_index = int(conversion.get("chunk_index", -1) or -1)
        succeeded_chunks = int(conversion.get("succeeded_chunks", 0) or 0)
        total_chunks = int(conversion.get("total_chunks", 0) or 0)

        self.progress_bar.setValue(max(0, min(percent, 100)))
        if total_chunks > 0:
            self.progress_label.setText(
                f"{status} — chunk {max(0, chunk_index)} | {succeeded_chunks}/{total_chunks}"
            )
        else:
            self.progress_label.setText(f"{status} — {percent}%")

    def _sync_diagnostics(self, state: dict[str, Any]) -> None:
        diagnostics = dict(state.get("diagnostics", {}))
        panel_visible = bool(diagnostics.get("panel_visible", False))
        details_expanded = bool(diagnostics.get("details_expanded", False))
        self.diagnostics_toggle.blockSignals(True)
        self.diagnostics_toggle.setChecked(details_expanded)
        self.diagnostics_toggle.setText("Hide details" if details_expanded else "Show details")
        self.diagnostics_toggle.blockSignals(False)

        self.diagnostics_content.setVisible(panel_visible)
        self.diagnostics_summary_label.setText(str(diagnostics.get("summary", "")))
        remediation_items = [str(item) for item in diagnostics.get("remediation", [])]
        if remediation_items:
            self.diagnostics_remediation_label.setText("\n".join(f"• {item}" for item in remediation_items))
        else:
            self.diagnostics_remediation_label.setText("")

        details_payload = diagnostics.get("details", {})
        if isinstance(details_payload, dict):
            self.diagnostics_details.setPlainText(json.dumps(details_payload, indent=2, ensure_ascii=False))
        else:
            self.diagnostics_details.setPlainText(str(details_payload))

        self.retry_button.setEnabled(bool(diagnostics.get("retry_enabled", False)))
        self.diagnostics_details.setVisible(details_expanded)

    def _populate_combo_with_options(self, combo: QComboBox, options: list[dict[str, Any]]) -> None:
        selected_id = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for option in options:
            label = str(option.get("label", option.get("id", "")))
            value = str(option.get("id", ""))
            combo.addItem(label, value)
            index = combo.count() - 1
            disabled = bool(option.get("disabled", False))
            reason = str(option.get("reason", ""))
            model = combo.model()
            if isinstance(model, QStandardItemModel):
                item = model.item(index)
                if item is not None:
                    item.setEnabled(not disabled)
                    if reason:
                        item.setToolTip(reason)
            if reason:
                combo.setItemData(index, reason, Qt.ToolTipRole)

        self._ensure_first_enabled_selection(combo)

        if selected_id:
            restored = combo.findData(selected_id)
            if restored >= 0:
                combo.setCurrentIndex(restored)
        combo.blockSignals(False)

    def _populate_voice_combo(self, voices: list[dict[str, Any]]) -> None:
        selected_engine = str(self.engine_combo.currentData() or "")
        selected_id = self.voice_combo.currentData()
        filtered = [
            voice
            for voice in voices
            if not selected_engine or str(voice.get("engine", "")) == selected_engine
        ]
        self.voice_combo.blockSignals(True)
        self.voice_combo.clear()
        for voice in filtered:
            label = str(voice.get("label", voice.get("id", "")))
            voice_id = str(voice.get("id", ""))
            self.voice_combo.addItem(label, voice_id)
            index = self.voice_combo.count() - 1
            disabled = bool(voice.get("disabled", False))
            reason = str(voice.get("reason", ""))
            model = self.voice_combo.model()
            if isinstance(model, QStandardItemModel):
                item = model.item(index)
                if item is not None:
                    item.setEnabled(not disabled)
                    if reason:
                        item.setToolTip(reason)
            if reason:
                self.voice_combo.setItemData(index, reason, Qt.ToolTipRole)

        self._ensure_first_enabled_selection(self.voice_combo)

        if selected_id:
            restored = self.voice_combo.findData(selected_id)
            if restored >= 0:
                self.voice_combo.setCurrentIndex(restored)
        self.voice_combo.blockSignals(False)

    def _ensure_first_enabled_selection(self, combo: QComboBox) -> None:
        model = combo.model()
        if not isinstance(model, QStandardItemModel):
            return

        for index in range(combo.count()):
            item = model.item(index)
            if item is not None and item.isEnabled():
                combo.setCurrentIndex(index)
                return

    def _on_engine_changed(self) -> None:
        options = dict(self._view.current_state.get("configuration_options", {}))
        self._populate_voice_combo(options.get("voices", []))

    def _on_speech_rate_changed(self, value: int) -> None:
        options = dict(self._view.current_state.get("configuration_options", {}))
        speech_rate = dict(options.get("speech_rate", {}))
        min_rate = float(speech_rate.get("min", 0.5) or 0.5)
        step = float(speech_rate.get("step", 0.05) or 0.05)
        rate = min_rate + (float(value) * step)
        self.speech_rate_value_label.setText(f"{rate:.2f}")

    def _get_selected_speech_rate(self, *, min_rate: float, step: float) -> float:
        return min_rate + (float(self.speech_rate_slider.value()) * step)

    def set_document_id(self, document_id: str) -> None:
        """Receive the real document_id after a successful import."""
        self._document_id = document_id
        # Re-enable the convert button if readiness allows it
        state = dict(self._view.current_state)
        self.convert_button.setEnabled(bool(state.get("start_enabled", False)) and bool(document_id))

    def _on_convert_clicked(self) -> None:
        if not self._document_id:
            self.progress_label.setText("failed — no document imported yet")
            return

        options = dict(self._view.current_state.get("configuration_options", {}))
        voices = list(options.get("voices", []))
        self._active_job_id = str(uuid4())
        self._active_correlation_id = str(uuid4())

        config_result = self._presenter.build_conversion_config(
            engine=str(self.engine_combo.currentData() or ""),
            voice_id=str(self.voice_combo.currentData() or ""),
            language=str(self.language_combo.currentData() or ""),
            speech_rate=float(self.speech_rate_value_label.text()),
            output_format=str(self.output_format_combo.currentData() or ""),
            voice_catalog=voices,
            correlation_id=self._active_correlation_id,
            job_id=self._active_job_id,
        )
        if not config_result.ok or config_result.data is None:
            self.progress_label.setText(
                f"failed — {config_result.error.code if config_result.error else 'configuration.failed'}"
            )
            return

        self.convert_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("running — 0%")

        self._worker.execute_conversion_async(
            document_id=self._document_id,
            job_id=self._active_job_id,
            correlation_id=self._active_correlation_id,
            conversion_config=config_result.data,
        )

    def _on_diagnostics_toggled(self, checked: bool) -> None:
        self._view.set_diagnostics_details_expanded(checked)
        self._sync_from_state()

    def _on_retry_clicked(self) -> None:
        if self._view.request_retry():
            self._on_convert_clicked()

    def _on_copy_details_clicked(self) -> None:
        details = self._view.copy_support_details()
        self.diagnostics_details.setPlainText(json.dumps(details, indent=2, ensure_ascii=False))
