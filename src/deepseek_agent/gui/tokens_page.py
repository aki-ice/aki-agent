from __future__ import annotations

from datetime import datetime, timedelta

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QFont, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from .theme import C, FONT_NUMBER, FONT_SERIF, card_style, shadow


class TokenCard(QFrame):
    def __init__(self, title: str, value: str, subtitle: str = "", accent: str = C["primary"], parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._accent = accent
        self.setStyleSheet(card_style(radius=18))
        self.setMinimumHeight(116)
        self.setGraphicsEffect(shadow(20, 32, 4))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"background-color: {C['panel']}; border: none; color: {C['muted']}; font-size: 10px; font-weight: 900;")
        layout.addWidget(title_lbl)

        self._value_lbl = QLabel(value)
        self._value_lbl.setStyleSheet(
            f"background-color: {C['panel']}; border: none; color: {accent}; font-family: {FONT_NUMBER}; font-size: 29px; font-weight: 900;"
        )
        layout.addWidget(self._value_lbl)

        if subtitle:
            sub = QLabel(subtitle)
            sub.setStyleSheet(f"background-color: {C['panel']}; border: none; color: {C['muted']}; font-size: 10px;")
            layout.addWidget(sub)

    def set_value(self, value: str) -> None:
        self._value_lbl.setText(value)


class TokenHeatmap(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(142)
        self._activity: dict[str, int] = {}

    def set_activity(self, activity: dict[str, int]) -> None:
        self._activity = activity
        self.update()

    def _level(self, day: datetime) -> int:
        tokens = self._activity.get(day.date().isoformat(), 0)
        if tokens <= 0:
            return 0
        if tokens < 500:
            return 1
        if tokens < 2_000:
            return 2
        if tokens < 8_000:
            return 3
        return 4

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cell = 10
        gap = 4
        left = 48
        top = 34
        colors = [
            QColor("#F0DFC1"),
            QColor("#E2BD89"),
            QColor("#CE8656"),
            QColor("#B94B3C"),
            QColor(C["primary"]),
        ]

        painter.setPen(QPen(QColor(C["muted"])))
        painter.setFont(QFont("Microsoft YaHei UI", 8))
        for idx, month in enumerate(["7月", "8月", "9月", "10月", "11月", "12月", "1月", "2月", "3月", "4月", "5月", "6月"]):
            painter.drawText(left + idx * 44, 18, month)

        start = datetime.now() - timedelta(days=364)
        for i in range(365):
            day = start + timedelta(days=i)
            week = i // 7
            weekday = i % 7
            painter.setBrush(QBrush(colors[self._level(day)]))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(left + week * (cell + gap), top + weekday * (cell + gap), cell, cell, 3, 3)


class TokensPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._session_input = 0
        self._session_output = 0
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {C['bg']}; }}")

        content = QWidget()
        content.setStyleSheet(f"background-color: {C['bg']};")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 26, 32, 34)
        layout.setSpacing(18)

        title = QLabel("令牌用量")
        title.setStyleSheet(f"color: {C['text']}; font-family: {FONT_SERIF}; font-size: 24px; font-weight: 900;")
        layout.addWidget(title)
        desc = QLabel("跟踪历史 Token 消耗和活跃情况。")
        desc.setStyleSheet(f"color: {C['muted']}; font-size: 11px;")
        layout.addWidget(desc)

        cards = QGridLayout()
        cards.setSpacing(14)
        self._input_card = TokenCard("INPUT TOKENS", "0", "历史输入", C["success"])
        self._output_card = TokenCard("OUTPUT TOKENS", "0", "历史输出", C["accent"])
        self._total_card = TokenCard("TOTAL TOKENS", "0", "输入输出合计", C["primary"])
        self._avg_card = TokenCard("AVG / REQUEST", "0", "平均每次请求", C["warning"])
        cards.addWidget(self._input_card, 0, 0)
        cards.addWidget(self._output_card, 0, 1)
        cards.addWidget(self._total_card, 0, 2)
        cards.addWidget(self._avg_card, 0, 3)
        layout.addLayout(cards)

        heat_frame = QFrame()
        heat_frame.setObjectName("Card")
        heat_frame.setStyleSheet(card_style(radius=20))
        heat_frame.setGraphicsEffect(shadow(22, 32, 5))
        hl = QVBoxLayout(heat_frame)
        hl.setContentsMargins(20, 16, 20, 16)
        ht = QLabel("Usage Heatmap · 最近 365 天")
        ht.setStyleSheet(f"color: {C['text']}; font-size: 14px; font-weight: 900;")
        hl.addWidget(ht)
        self._heatmap = TokenHeatmap()
        hl.addWidget(self._heatmap)
        layout.addWidget(heat_frame)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def update_stats(self, input_tokens: int, output_tokens: int, request_count: int, activity: dict[str, int] | None = None) -> None:
        self._session_input = input_tokens
        self._session_output = output_tokens
        total = input_tokens + output_tokens
        avg = total // max(request_count, 1)
        self._input_card.set_value(f"{input_tokens:,}")
        self._output_card.set_value(f"{output_tokens:,}")
        self._total_card.set_value(f"{total:,}")
        self._avg_card.set_value(f"{avg:,}")
        if activity is not None:
            self._heatmap.set_activity(activity)
