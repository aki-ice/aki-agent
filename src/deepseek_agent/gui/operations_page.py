from __future__ import annotations

import json

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QTextEdit, QVBoxLayout, QWidget

from ..runtime import RunStore
from .theme import C, FONT_SERIF, primary_button_style, secondary_button_style


class OperationsPage(QWidget):
    def __init__(self, store: RunStore, parent=None):
        super().__init__(parent)
        self.store = store
        self._build()
        self.refresh()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(2000)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 26, 32, 32)
        title = QLabel("任务与审批")
        title.setStyleSheet(f"color: {C['text']}; font-family: {FONT_SERIF}; font-size: 24px; font-weight: 900;")
        layout.addWidget(title)
        row = QHBoxLayout()
        self._filter = QComboBox()
        self._filter.addItems(["全部", "queued", "running", "waiting_approval", "completed", "failed", "cancelled", "timed_out"])
        refresh = QPushButton("刷新")
        refresh.setStyleSheet(primary_button_style())
        refresh.clicked.connect(self.refresh)
        row.addWidget(self._filter)
        row.addWidget(refresh)
        row.addStretch()
        layout.addLayout(row)
        self._runs = QListWidget()
        self._runs.currentItemChanged.connect(self._show_run)
        layout.addWidget(self._runs, 1)
        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        layout.addWidget(self._detail, 1)

    def refresh(self):
        status = self._filter.currentText()
        rows = self.store.list_runs(status=None if status == "全部" else status)
        self._runs.clear()
        for row in rows:
            item = QListWidgetItem(f"[{row['status']}] {row['model']} · {row['user_input'][:80]}")
            item.setData(32, row["id"])
            self._runs.addItem(item)

    def _show_run(self, current, _previous):
        if not current:
            return
        run_id = current.data(32)
        payload = {"run": next((row for row in self.store.list_runs() if row["id"] == run_id), {}), "events": self.store.run_events(run_id), "tool_calls": self.store.tool_calls(run_id), "approvals": self.store.approval_requests(run_id)}
        self._detail.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
