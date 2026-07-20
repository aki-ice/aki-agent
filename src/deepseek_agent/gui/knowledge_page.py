from __future__ import annotations

import os

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidget, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget

from ..rag import Retriever
from .theme import C, FONT_SERIF, card_style, primary_button_style, secondary_button_style


class KnowledgePage(QWidget):
    knowledge_changed = pyqtSignal()

    def __init__(self, retriever: Retriever, parent=None) -> None:
        super().__init__(parent)
        self.retriever = retriever
        self._sources: list[str] = []
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 26, 32, 32)
        layout.setSpacing(14)
        title = QLabel("知识库")
        title.setStyleSheet(f"color: {C['text']}; font-family: {FONT_SERIF}; font-size: 24px; font-weight: 900;")
        subtitle = QLabel("导入文件或目录，Agent 会在回答前自动检索相关内容。默认使用本地 Hash Embedding，无需额外 API。")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {C['muted']}; font-size: 11px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        buttons = QHBoxLayout()
        file_btn = QPushButton("导入文件")
        file_btn.setStyleSheet(primary_button_style())
        file_btn.clicked.connect(self._import_file)
        directory_btn = QPushButton("导入目录")
        directory_btn.setStyleSheet(secondary_button_style())
        directory_btn.clicked.connect(self._import_directory)
        clear_btn = QPushButton("清空知识库")
        clear_btn.setStyleSheet(secondary_button_style())
        clear_btn.clicked.connect(self._clear)
        buttons.addWidget(file_btn)
        buttons.addWidget(directory_btn)
        buttons.addWidget(clear_btn)
        buttons.addStretch()
        layout.addLayout(buttons)

        body = QHBoxLayout()
        sources_card = QFrame()
        sources_card.setStyleSheet(card_style(radius=16))
        sources_layout = QVBoxLayout(sources_card)
        self._count = QLabel()
        self._count.setStyleSheet(f"color: {C['text']}; font-weight: 800;")
        self._sources_list = QListWidget()
        sources_layout.addWidget(self._count)
        sources_layout.addWidget(self._sources_list)
        body.addWidget(sources_card, 1)

        search_card = QFrame()
        search_card.setStyleSheet(card_style(radius=16))
        search_layout = QVBoxLayout(search_card)
        search_layout.addWidget(QLabel("检索测试"))
        self._query = QTextEdit()
        self._query.setMaximumHeight(90)
        self._query.setPlaceholderText("输入问题，查看会注入 Agent 的知识片段...")
        search_layout.addWidget(self._query)
        search_btn = QPushButton("搜索")
        search_btn.setStyleSheet(primary_button_style())
        search_btn.clicked.connect(self._search)
        search_layout.addWidget(search_btn)
        self._results = QTextEdit()
        self._results.setReadOnly(True)
        search_layout.addWidget(self._results)
        body.addWidget(search_card, 2)
        layout.addLayout(body, 1)

    def refresh(self) -> None:
        entries = getattr(self.retriever.store, "_entries", [])
        sources = sorted({str(entry.metadata.get("source", "")) for entry in entries if entry.metadata.get("source")})
        self._sources_list.clear()
        self._sources_list.addItems(sources)
        self._count.setText(f"{len(entries)} 个片段 · {len(sources)} 个来源")

    def _import_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "导入知识文件", "", "Documents (*.txt *.md *.py *.js *.ts *.json *.yaml *.yml *.toml);;All (*)")
        if not path:
            return
        self._ingest(lambda: self.retriever.ingest_file(path), os.path.basename(path))

    def _import_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "导入知识目录")
        if not path:
            return
        self._ingest(lambda: self.retriever.ingest_directory(path), os.path.basename(path))

    def _ingest(self, operation, label: str) -> None:
        try:
            count = operation()
            self.refresh()
            self.knowledge_changed.emit()
            QMessageBox.information(self, "导入完成", f"{label}：新增 {count} 个知识片段。")
        except Exception as exc:
            QMessageBox.critical(self, "导入失败", str(exc))

    def _clear(self) -> None:
        if QMessageBox.question(self, "确认", "确定清空全部知识片段吗？") != QMessageBox.StandardButton.Yes:
            return
        self.retriever.clear()
        self.retriever.save()
        self.refresh()
        self.knowledge_changed.emit()

    def _search(self) -> None:
        query = self._query.toPlainText().strip()
        if not query:
            return
        results = self.retriever.search(query, top_k=5)
        self._results.setPlainText("\n\n---\n\n".join(f"[{item['score']}] {item['title'] or item['source']}\n{item['text']}" for item in results) or "没有匹配结果")
