from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget

from ..memory import LongTermMemory, MemoryEntry
from .theme import C, FONT_SERIF, primary_button_style, secondary_button_style


class LongTermMemoryPage(QWidget):
    def __init__(self, memory: LongTermMemory, parent=None) -> None:
        super().__init__(parent)
        self.memory = memory
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 26, 32, 32)
        layout.setSpacing(12)
        title = QLabel("长期记忆")
        title.setStyleSheet(f"color: {C['text']}; font-family: {FONT_SERIF}; font-size: 24px; font-weight: 900;")
        description = QLabel("跨会话保存的重要事实和对话摘要。新请求会自动检索相关记忆并注入上下文。")
        description.setStyleSheet(f"color: {C['muted']}; font-size: 11px;")
        layout.addWidget(title)
        layout.addWidget(description)

        self._input = QTextEdit()
        self._input.setMaximumHeight(100)
        self._input.setPlaceholderText("手动添加需要长期记住的信息...")
        layout.addWidget(self._input)
        row = QHBoxLayout()
        add = QPushButton("添加记忆")
        add.setStyleSheet(primary_button_style())
        add.clicked.connect(self._add)
        search = QPushButton("搜索")
        search.setStyleSheet(secondary_button_style())
        search.clicked.connect(self._search)
        refresh = QPushButton("全部记忆")
        refresh.setStyleSheet(secondary_button_style())
        refresh.clicked.connect(self.refresh)
        clear = QPushButton("清空")
        clear.setStyleSheet(secondary_button_style())
        clear.clicked.connect(self._clear)
        row.addWidget(add)
        row.addWidget(search)
        row.addWidget(refresh)
        row.addWidget(clear)
        row.addStretch()
        layout.addLayout(row)
        self._list = QListWidget()
        layout.addWidget(self._list, 1)

    def refresh(self) -> None:
        self._show(self.memory.all())

    def _show(self, entries: list[MemoryEntry]) -> None:
        self._list.clear()
        for entry in entries:
            self._list.addItem(f"{entry.created_at} · importance={entry.importance:.1f}\n{entry.content}")

    def _add(self) -> None:
        content = self._input.toPlainText().strip()
        if not content:
            return
        self.memory.add(MemoryEntry(content=content, metadata={"type": "manual"}, importance=0.8))
        self._input.clear()
        self.refresh()

    def _search(self) -> None:
        query = self._input.toPlainText().strip()
        if query:
            self._show(self.memory.search(query, top_k=20))

    def _clear(self) -> None:
        if QMessageBox.question(self, "确认", "确定清空所有长期记忆吗？") == QMessageBox.StandardButton.Yes:
            self.memory.clear()
            self.refresh()
