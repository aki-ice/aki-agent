from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget

from ..file_workbench import FileWorkbench
from .theme import C, FONT_SERIF, input_style, primary_button_style, secondary_button_style


class FileWorkbenchPage(QWidget):
    def __init__(self, workbench: FileWorkbench, parent=None):
        super().__init__(parent)
        self.workbench = workbench
        self._build()
        self._refresh(".")

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 26, 32, 32)
        title = QLabel("本地文件工作台")
        title.setStyleSheet(f"color: {C['text']}; font-family: {FONT_SERIF}; font-size: 24px; font-weight: 900;")
        layout.addWidget(title)
        self._path = QLabel(str(self.workbench.workspace_root))
        layout.addWidget(self._path)
        row = QHBoxLayout()
        refresh = QPushButton("刷新")
        refresh.setStyleSheet(primary_button_style())
        refresh.clicked.connect(lambda: self._refresh("."))
        reveal = QPushButton("资源管理器定位")
        reveal.setStyleSheet(secondary_button_style())
        reveal.clicked.connect(lambda: self.workbench.reveal("."))
        row.addWidget(refresh)
        row.addWidget(reveal)
        row.addStretch()
        layout.addLayout(row)
        self._files = QListWidget()
        self._files.itemDoubleClicked.connect(self._preview)
        layout.addWidget(self._files, 1)
        self._preview_box = QTextEdit()
        self._preview_box.setReadOnly(True)
        layout.addWidget(self._preview_box, 1)

    def _refresh(self, path: str):
        self._files.clear()
        for item in self.workbench.list_directory(path):
            entry = self._files.addItem(f"{'[DIR] ' if item['directory'] else ''}{item['name']}")
            self._files.item(self._files.count() - 1).setData(Qt.ItemDataRole.UserRole, item["path"])

    def _preview(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        try:
            self._preview_box.setPlainText(self.workbench.preview(path))
        except Exception as exc:
            QMessageBox.warning(self, "预览失败", str(exc))
