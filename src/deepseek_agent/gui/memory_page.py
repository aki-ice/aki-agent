from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .daily_memory_store import DailyMemory, DailyMemoryStore
from .theme import C, FONT_NUMBER, FONT_SERIF, card_style, primary_button_style, secondary_button_style, shadow


class MemoryCard(QFrame):
    selected = pyqtSignal(str)

    def __init__(self, memory: DailyMemory, parent=None):
        super().__init__(parent)
        self.memory = memory
        self.setObjectName("Card")
        self.setStyleSheet(card_style(radius=16, bg=C["panel"]))
        self.setGraphicsEffect(shadow(16, 24, 3))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        row = QHBoxLayout()
        day = QLabel(self.memory.day)
        day.setStyleSheet(f"background-color: {C['panel']}; border: none; color: {C['text']}; font-family: {FONT_NUMBER}; font-size: 20px; font-weight: 900;")
        row.addWidget(day)
        row.addStretch()
        count = QLabel(f"{self.memory.session_count} sessions · {self.memory.message_count} messages")
        count.setStyleSheet(f"background-color: {C['panel']}; border: none; color: {C['muted']}; font-size: 10px;")
        row.addWidget(count)
        layout.addLayout(row)

        preview = QLabel(self._preview(self.memory.summary))
        preview.setWordWrap(True)
        preview.setStyleSheet(f"background-color: {C['panel']}; border: none; color: {C['muted']}; font-size: 11px;")
        layout.addWidget(preview)

        updated = QLabel(f"Updated: {self.memory.updated_at}")
        updated.setStyleSheet(f"background-color: {C['panel']}; border: none; color: {C['muted_2']}; font-size: 9px;")
        layout.addWidget(updated)

    def mousePressEvent(self, event) -> None:
        self.selected.emit(self.memory.day)
        super().mousePressEvent(event)

    def _preview(self, text: str) -> str:
        cleaned = " ".join(text.replace("#", "").split())
        if len(cleaned) <= 150:
            return cleaned
        return cleaned[:150].rstrip() + "..."


class MemoryPage(QWidget):
    refresh_requested = pyqtSignal()

    def __init__(self, store: DailyMemoryStore, parent=None):
        super().__init__(parent)
        self.store = store
        self._current_day: str | None = None
        self._build()
        self.refresh()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {C['bg']}; }}")

        content = QWidget()
        content.setStyleSheet(f"background-color: {C['bg']};")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 26, 32, 34)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("每日记忆")
        title.setStyleSheet(f"background-color: {C['bg']}; border: none; color: {C['text']}; font-family: {FONT_SERIF}; font-size: 24px; font-weight: 900;")
        subtitle = QLabel("按日期汇总当天问答，记录这一天大致讨论了什么。")
        subtitle.setStyleSheet(f"background-color: {C['bg']}; border: none; color: {C['muted']}; font-size: 11px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()

        refresh_btn = QPushButton("刷新今日概要")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh_today)
        refresh_btn.setStyleSheet(primary_button_style())
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(16)

        list_frame = QFrame()
        list_frame.setObjectName("Card")
        list_frame.setStyleSheet(card_style(radius=18))
        list_frame.setGraphicsEffect(shadow(18, 28, 4))
        list_layout = QVBoxLayout(list_frame)
        list_layout.setContentsMargins(16, 14, 16, 14)
        list_layout.setSpacing(10)
        list_title = QLabel("Memory Days")
        list_title.setStyleSheet(f"background-color: {C['panel']}; border: none; color: {C['text']}; font-size: 14px; font-weight: 900;")
        list_layout.addWidget(list_title)
        self._list_layout = QVBoxLayout()
        self._list_layout.setSpacing(10)
        list_layout.addLayout(self._list_layout)
        list_layout.addStretch()
        body.addWidget(list_frame, 1)

        detail_frame = QFrame()
        detail_frame.setObjectName("Card")
        detail_frame.setStyleSheet(card_style(radius=18))
        detail_frame.setGraphicsEffect(shadow(18, 28, 4))
        detail_layout = QVBoxLayout(detail_frame)
        detail_layout.setContentsMargins(16, 14, 16, 14)
        detail_layout.setSpacing(10)

        self._detail_title = QLabel("请选择一天")
        self._detail_title.setStyleSheet(f"background-color: {C['panel']}; border: none; color: {C['text']}; font-size: 16px; font-weight: 900;")
        detail_layout.addWidget(self._detail_title)

        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setStyleSheet(f"""
            QTextEdit {{
                background-color: {C['panel']};
                color: {C['text']};
                border: 1px solid {C['border_soft']};
                border-radius: 12px;
                padding: 12px;
                font-size: 12px;
            }}
        """)
        detail_layout.addWidget(self._detail, 1)

        btn_row = QHBoxLayout()
        refresh_selected = QPushButton("刷新选中日期")
        refresh_selected.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_selected.clicked.connect(self._refresh_selected)
        refresh_selected.setStyleSheet(secondary_button_style())
        btn_row.addWidget(refresh_selected)
        btn_row.addStretch()
        detail_layout.addLayout(btn_row)
        body.addWidget(detail_frame, 2)

        layout.addLayout(body, 1)
        scroll.setWidget(content)
        root.addWidget(scroll)

    def refresh(self) -> None:
        memories = self.store.list_memories()
        self._clear_list()
        if not memories:
            empty = QLabel("暂无每日记忆。完成一次对话后会自动生成今日概要。")
            empty.setWordWrap(True)
            empty.setStyleSheet(f"background-color: {C['panel']}; border: none; color: {C['muted']}; font-size: 11px;")
            self._list_layout.addWidget(empty)
            self._detail_title.setText("暂无记录")
            self._detail.setPlainText("完成一次对话后，系统会根据当天问答自动生成概要。")
            return
        for memory in memories:
            card = MemoryCard(memory)
            card.selected.connect(self._select_day)
            self._list_layout.addWidget(card)
        if self._current_day is None or self.store.get_memory(self._current_day) is None:
            self._select_day(memories[0].day)
        else:
            self._select_day(self._current_day)

    def _clear_list(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _select_day(self, day: str) -> None:
        memory = self.store.get_memory(day)
        if not memory:
            return
        self._current_day = day
        self._detail_title.setText(f"{day} 对话概要")
        self._detail.setPlainText(memory.summary)

    def _refresh_today(self) -> None:
        memory = self.store.refresh_day()
        if memory is None:
            QMessageBox.information(self, "提示", "今天还没有可汇总的对话。")
            return
        self._current_day = memory.day
        self.refresh()
        self.refresh_requested.emit()

    def _refresh_selected(self) -> None:
        if not self._current_day:
            QMessageBox.information(self, "提示", "请先选择一个日期。")
            return
        memory = self.store.refresh_day(self._current_day)
        if memory is None:
            QMessageBox.information(self, "提示", "该日期没有可汇总的对话。")
            return
        self.refresh()
        self.refresh_requested.emit()
