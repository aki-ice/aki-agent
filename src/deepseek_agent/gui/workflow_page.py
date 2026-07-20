from __future__ import annotations

import json

from PyQt6.QtWidgets import QComboBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget

from ..workflows import DocumentWorkflowService
from .theme import C, FONT_SERIF, input_style, primary_button_style, secondary_button_style


class WorkflowPage(QWidget):
    def __init__(self, service: DocumentWorkflowService, parent=None):
        super().__init__(parent)
        self.service = service
        self._path = ""
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 26, 32, 32)
        title = QLabel("企业文档工作流")
        title.setStyleSheet(f"color: {C['text']}; font-family: {FONT_SERIF}; font-size: 24px; font-weight: 900;")
        layout.addWidget(title)
        row = QHBoxLayout()
        self._workflow = QComboBox()
        self._workflow.addItem("合同审查", "contract_review")
        self._workflow.addItem("报告总结", "report_summary")
        self._workflow.addItem("表格洞察", "spreadsheet_insight")
        self._workflow.addItem("论文阅读", "paper_reading")
        self._workflow.setStyleSheet(input_style())
        choose = QPushButton("选择文档")
        choose.setStyleSheet(secondary_button_style())
        choose.clicked.connect(self._choose)
        run = QPushButton("运行分析")
        run.setStyleSheet(primary_button_style())
        run.clicked.connect(self._run)
        export = QPushButton("导出 Markdown")
        export.setStyleSheet(secondary_button_style())
        export.clicked.connect(self._export)
        row.addWidget(self._workflow)
        row.addWidget(choose)
        row.addWidget(run)
        row.addWidget(export)
        layout.addLayout(row)
        self._status = QLabel("尚未选择文档")
        layout.addWidget(self._status)
        self._output = QTextEdit()
        self._output.setReadOnly(True)
        layout.addWidget(self._output, 1)
        self._result = None

    def _choose(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择文档", "", "Documents (*.pdf *.docx *.pptx *.xlsx *.csv *.txt *.md);;All (*)")
        if path:
            self._path = path
            self._status.setText(path)

    def _run(self):
        if not self._path:
            return
        try:
            self._result = self.service.run(self._workflow.currentData(), self._path)
            self._output.setPlainText(self._result.to_markdown())
        except Exception as exc:
            QMessageBox.critical(self, "分析失败", str(exc))

    def _export(self):
        if not self._result:
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出结果", "workflow_result.md", "Markdown (*.md);;JSON (*.json)")
        if path:
            self._result.save(path)
