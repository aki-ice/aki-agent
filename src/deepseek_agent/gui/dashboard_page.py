from __future__ import annotations

from datetime import datetime, timedelta

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .stats_store import DashboardStats
from .theme import C, FONT_NUMBER, FONT_SERIF, card_style, shadow


class StatCard(QFrame):
    def __init__(self, title: str, value: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setStyleSheet(card_style())
        self.setMinimumHeight(104)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setGraphicsEffect(shadow(20, 35, 4))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(4)

        title_label = QLabel(title.upper())
        title_label.setStyleSheet(
            f"background-color: {C['panel']}; border: none; color: {C['muted']}; "
            "font-size: 10px; font-weight: 800; letter-spacing: 1px;"
        )
        layout.addWidget(title_label)

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(
            f"background-color: {C['panel']}; border: none; color: {C['text']}; font-family: {FONT_NUMBER}; font-size: 25px; font-weight: 800;"
        )
        layout.addWidget(self.value_label)

        subtitle_label = QLabel(subtitle)
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet(f"background-color: {C['panel']}; border: none; color: {C['muted']}; font-size: 10px;")
        layout.addWidget(subtitle_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class ActivityHeatmap(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(142)
        self._activity: dict[str, int] = {}

    def set_activity(self, activity: dict[str, int]) -> None:
        self._activity = activity
        self.update()

    def _level_for_day(self, day: datetime) -> int:
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

        today = datetime.now()
        start = today - timedelta(days=364)

        painter.setPen(QPen(QColor(C["muted"])))
        painter.setFont(QFont("Microsoft YaHei UI", 8))
        for idx, month in enumerate(["7月", "8月", "9月", "10月", "11月", "12月", "1月", "2月", "3月", "4月", "5月", "6月"]):
            painter.drawText(left + idx * 44, 18, month)

        for i in range(365):
            day = start + timedelta(days=i)
            week = i // 7
            weekday = i % 7
            level = self._level_for_day(day)
            x = left + week * (cell + gap)
            y = top + weekday * (cell + gap)
            painter.setBrush(QBrush(colors[level]))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(x, y, cell, cell, 3, 3)

        painter.setPen(QPen(QColor(C["muted"])))
        painter.setFont(QFont("Microsoft YaHei UI", 8))
        legend_x = max(left, self.width() - 96)
        painter.drawText(legend_x - 22, 26, "少")
        for index, color in enumerate(colors):
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(legend_x + index * 14, 18, 10, 10, 3, 3)
        painter.setPen(QPen(QColor(C["muted"])))
        painter.drawText(legend_x + 72, 26, "多")


class DashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background: {C['bg']}; border: none; }}")

        content = QWidget()
        content.setStyleSheet(f"background: {C['bg']};")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 24, 32, 32)
        layout.setSpacing(18)

        title_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("用量账本")
        title.setStyleSheet(f"color: {C['text']}; font-family: {FONT_SERIF}; font-size: 24px; font-weight: 900;")
        subtitle = QLabel("会话、消息、Token 与模型活跃情况总览")
        subtitle.setStyleSheet(f"color: {C['muted']}; font-size: 11px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        title_row.addLayout(title_box)
        title_row.addStretch()

        badge = QLabel("今日 · 工作台")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background: {C['primary']}; color: {C['white']}; border-radius: 13px; padding: 6px 14px; font-weight: 700;"
        )
        title_row.addWidget(badge)
        layout.addLayout(title_row)

        grid = QGridLayout()
        grid.setSpacing(14)
        self.sessions = StatCard("Sessions", "0", "历史会话请求")
        self.messages = StatCard("Messages", "0", "用户与 Agent 消息数")
        self.tokens = StatCard("Total Tokens", "0", "历史输入输出总量")
        self.active_days = StatCard("Active Days", "0", "最近活跃天数")
        self.current_streak = StatCard("Current Streak", "0 天", "连续使用天数")
        self.longest_streak = StatCard("Longest Streak", "0 天", "最长连续使用记录")
        self.peak_hour = StatCard("Peak Hour", datetime.now().strftime("%H:00"), "最常使用时段")
        self.favorite_model = StatCard("Favorite Model", "deepseek-v4-pro", "当前常用模型")

        cards = [
            self.sessions,
            self.messages,
            self.tokens,
            self.active_days,
            self.current_streak,
            self.longest_streak,
            self.peak_hour,
            self.favorite_model,
        ]
        for index, card in enumerate(cards):
            grid.addWidget(card, index // 4, index % 4)
        layout.addLayout(grid)

        heat_frame = QFrame()
        heat_frame.setObjectName("Card")
        heat_frame.setStyleSheet(card_style(radius=20))
        heat_frame.setGraphicsEffect(shadow(22, 32, 5))
        heat_layout = QVBoxLayout(heat_frame)
        heat_layout.setContentsMargins(20, 16, 20, 16)
        heat_layout.setSpacing(10)

        heat_title = QLabel("活跃热力图")
        heat_title.setStyleSheet(f"color: {C['text']}; font-size: 15px; font-weight: 900;")
        heat_layout.addWidget(heat_title)
        self.heatmap = ActivityHeatmap()
        heat_layout.addWidget(self.heatmap)
        layout.addWidget(heat_frame)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def update_stats(self, stats: DashboardStats) -> None:
        self.sessions.set_value(f"{stats.sessions:,}")
        self.messages.set_value(f"{stats.messages:,}")
        self.tokens.set_value(f"{stats.total_tokens:,}")
        self.active_days.set_value(str(stats.active_days))
        self.current_streak.set_value(f"{stats.current_streak} 天")
        self.longest_streak.set_value(f"{stats.longest_streak} 天")
        self.peak_hour.set_value(stats.peak_hour)
        self.favorite_model.set_value(stats.favorite_model)
        self.heatmap.set_activity(stats.activity)
