# emperor_agent.py
import sys
import random
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QScrollArea, QFrame,
    QSizePolicy, QGridLayout, QGraphicsDropShadowEffect, QTextEdit,
    QLineEdit, QComboBox
)
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon, QPainter, QPen, QBrush, QFontDatabase

# ==================== 样式配置 ====================
THEME = {
    "bg": "#f5f0e8",
    "card_bg": "#faf8f3",
    "sidebar_bg": "#f0ebe3",
    "text_primary": "#3d3d3d",
    "text_secondary": "#8a8a8a",
    "accent": "#8b4513",  # 棕色/国风
    "accent_light": "#d4a574",
    "border": "#e0d5c5",
    "highlight": "#c44a4a",  # 红色标签
    "green": "#4a7c59",
    "card_shadow": "#d0c8b8"
}


# ==================== 自定义组件 ====================
class Card(QFrame):
    """数据卡片"""

    def __init__(self, title, value, subtitle="", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(f"""
            #card {{
                background-color: {THEME["card_bg"]};
                border: 1px solid {THEME["border"]};
                border-radius: 16px;
                padding: 20px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 12px;")
        layout.addWidget(title_lbl)

        # 数值
        self.value_lbl = QLabel(value)
        self.value_lbl.setStyleSheet(f"""
            color: {THEME['text_primary']};
            font-size: 32px;
            font-weight: bold;
        """)
        layout.addWidget(self.value_lbl)

        # 副标题
        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
            layout.addWidget(sub_lbl)

        # 阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(THEME["card_shadow"]))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

        self.setMinimumHeight(120)


class HeatmapWidget(QWidget):
    """GitHub 风格贡献热力图"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(800, 140)
        self.data = self.generate_data()

    def generate_data(self):
        """生成模拟数据：过去一年的每日活跃度"""
        data = []
        base = datetime.now() - timedelta(days=365)
        for i in range(365):
            date = base + timedelta(days=i)
            # 模拟：近期更活跃
            weight = max(0, (i - 300) / 65) if i > 300 else 0.1
            level = random.choices([0, 1, 2, 3, 4],
                                   weights=[1 - weight, weight * 0.5, weight * 0.3, weight * 0.15, weight * 0.05])[0]
            data.append((date, level))
        return data

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cell_size = 14
        gap = 3
        weeks = 53
        days = 7

        colors = [
            "#e8e0d5",  # level 0
            "#d4b8a8",  # level 1
            "#c49a7c",  # level 2
            "#b07c5c",  # level 3
            "#8b4513",  # level 4
        ]

        for i, (date, level) in enumerate(self.data):
            week = i // 7
            day = i % 7
            x = week * (cell_size + gap) + 40
            y = day * (cell_size + gap) + 20

            painter.setBrush(QBrush(QColor(colors[level])))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(x, y, cell_size, cell_size, 3, 3)

        # 绘制月份标签
        months = ["5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月", "1月", "2月", "3月", "4月", "5月"]
        painter.setPen(QPen(QColor(THEME["text_secondary"])))
        for i, m in enumerate(months):
            x = i * 7 * (cell_size + gap) + 40
            painter.drawText(x, 15, m)

        # 星期标签
        weekdays = ["一", "三", "五"]
        for i, d in enumerate(weekdays):
            y = i * 2 * (cell_size + gap) + 25
            painter.drawText(10, y, d)


class NavButton(QPushButton):
    """侧边栏导航按钮"""

    def __init__(self, icon_text, label, badge=None, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 12, 16, 12)

        # 图标
        icon = QLabel(icon_text)
        icon.setStyleSheet("font-size: 20px;")
        layout.addWidget(icon)

        # 文字
        text = QLabel(label)
        text.setStyleSheet(f"color: {THEME['text_primary']}; font-size: 14px;")
        layout.addWidget(text)

        layout.addStretch()

        # 徽标
        if badge:
            badge_lbl = QLabel(badge)
            badge_lbl.setStyleSheet(f"""
                background-color: {THEME['highlight']};
                color: white;
                border-radius: 10px;
                padding: 2px 8px;
                font-size: 11px;
            """)
            layout.addWidget(badge_lbl)

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 12px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {THEME["border"]};
            }}
            QPushButton:checked {{
                background-color: {THEME["accent_light"]};
            }}
        """)


class FilterButton(QPushButton):
    """顶部筛选按钮"""

    def __init__(self, text, active=False, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setChecked(active)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME["accent"] if active else "transparent"};
                color: {"white" if active else THEME["text_secondary"]};
                border: 1px solid {THEME["accent"] if active else THEME["border"]};
                border-radius: 20px;
                padding: 8px 20px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {THEME["accent_light"]};
                color: white;
            }}
            QPushButton:checked {{
                background-color: {THEME["accent"]};
                color: white;
            }}
        """)


# ==================== 页面 ====================
class ChatPage(QWidget):
    """聊天页面（图1风格适配）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title = QLabel("💬 御前对话")
        title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {THEME['text_primary']};")
        layout.addWidget(title)

        # 聊天区域
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: {THEME["card_bg"]};
                border: 1px solid {THEME["border"]};
                border-radius: 16px;
                padding: 15px;
                font-size: 14px;
                color: {THEME["text_primary"]};
            }}
        """)
        layout.addWidget(self.chat_display)

        # 输入区
        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("输入消息...")
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background-color: {THEME["card_bg"]};
                border: 2px solid {THEME["border"]};
                border-radius: 12px;
                padding: 12px 16px;
                font-size: 14px;
                color: {THEME["text_primary"]};
            }}
            QLineEdit:focus {{
                border-color: {THEME["accent"]};
            }}
        """)
        self.input_field.returnPressed.connect(self.send_message)

        send_btn = QPushButton("发送")
        send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME["accent"]};
                color: white;
                border: none;
                border-radius: 12px;
                padding: 12px 30px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {THEME["accent_light"]};
            }}
        """)
        send_btn.clicked.connect(self.send_message)

        input_layout.addWidget(self.input_field)
        input_layout.addWidget(send_btn)
        layout.addLayout(input_layout)

    def send_message(self):
        msg = self.input_field.text().strip()
        if not msg:
            return
        self.chat_display.append(f"<b>你:</b> {msg}")
        self.input_field.clear()
        # 模拟回复
        QTimer.singleShot(500, lambda: self.chat_display.append(
            f"<b style='color:{THEME['accent']}'>Agent:</b> 收到「{msg}」"
        ))


class TokensPage(QWidget):
    """用量账本页面（图2风格）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # 顶部标题 + 筛选
        header = QHBoxLayout()
        title = QLabel("用量账本")
        title.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {THEME['text_primary']};")
        header.addWidget(title)

        subtitle = QLabel("按模型、用途、日期统计的 Token 消耗")
        subtitle.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 13px;")
        header.addWidget(subtitle)
        header.addStretch()

        # 筛选按钮组
        filters = ["概览", "模型", "全部", "30天", "7天"]
        for i, f in enumerate(filters):
            btn = FilterButton(f, active=(i == 0))
            btn.setFixedWidth(70)
            header.addWidget(btn)

        layout.addLayout(header)

        # 数据卡片行
        cards_row = QHBoxLayout()
        cards_row.setSpacing(20)

        cards_data = [
            ("SESSIONS", "8", "相邻调用 > 30 分钟视为新会话"),
            ("MESSAGES", "28", "history.json 中的对话条数"),
            ("TOTAL TOKENS", "642,082", "累计 Token"),
            ("ACTIVE DAYS", "3", "出现过的天数"),
        ]

        for title, value, sub in cards_data:
            card = Card(title, value, sub)
            cards_row.addWidget(card)

        layout.addLayout(cards_row)

        # 第二行卡片
        cards_row2 = QHBoxLayout()
        cards_row2.setSpacing(20)

        cards_data2 = [
            ("CURRENT STREAK", "3 天", "截至今天的连续天数"),
            ("LONGEST STREAK", "3 天", "历史最长连续天数"),
            ("PEAK HOUR", "23:00", "消耗最多 Token 的时段"),
            ("FAVORITE MODEL", "deepseek-v4-flash", "总量最高的模型"),
        ]

        for title, value, sub in cards_data2:
            card = Card(title, value, sub)
            cards_row2.addWidget(card)

        layout.addLayout(cards_row2)

        # 热力图区域
        heatmap_section = QVBoxLayout()
        heatmap_header = QHBoxLayout()
        heatmap_title = QLabel("活跃热力图")
        heatmap_title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {THEME['text_primary']};")
        heatmap_header.addWidget(heatmap_title)
        heatmap_header.addStretch()

        # 图例
        legend = QLabel("更少 □ □ □ □ □ 更多")
        legend.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 12px;")
        heatmap_header.addWidget(legend)

        heatmap_section.addLayout(heatmap_header)

        self.heatmap = HeatmapWidget()
        heatmap_section.addWidget(self.heatmap)

        layout.addLayout(heatmap_section)
        layout.addStretch()


# ==================== 主窗口 ====================
class EmperorAgent(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Aki Agent - 本地智能体工作台")
        self.setMinimumSize(1400, 900)

        # 中央部件
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # ========== 左侧边栏 ==========
        sidebar = QWidget()
        sidebar.setFixedWidth(260)
        sidebar.setStyleSheet(f"background-color: {THEME['sidebar_bg']};")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setSpacing(10)
        sidebar_layout.setContentsMargins(20, 20, 20, 20)

        # Logo 区域
        logo_box = QHBoxLayout()
        logo_icon = QLabel("令")
        logo_icon.setStyleSheet(f"""
            background-color: {THEME["accent"]};
            color: white;
            border-radius: 12px;
            padding: 8px 12px;
            font-size: 24px;
            font-weight: bold;
        """)
        logo_box.addWidget(logo_icon)

        logo_text = QVBoxLayout()
        name = QLabel("Aki Agent")
        name.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {THEME['text_primary']};")
        desc = QLabel("本地智能体工作台")
        desc.setStyleSheet(f"font-size: 12px; color: {THEME['text_secondary']};")
        logo_text.addWidget(name)
        logo_text.addWidget(desc)
        logo_box.addLayout(logo_text)

        sidebar_layout.addLayout(logo_box)

        # 模型选择
        model_frame = QFrame()
        model_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME["card_bg"]};
                border: 1px solid {THEME["border"]};
                border-radius: 12px;
            }}
        """)
        model_layout = QVBoxLayout(model_frame)
        model_combo = QComboBox()
        model_combo.addItem("anthropic / kimi-for-coding")
        model_combo.setStyleSheet(f"""
            QComboBox {{
                border: none;
                background: transparent;
                padding: 8px;
                font-size: 13px;
            }}
        """)
        model_layout.addWidget(model_combo)
        sidebar_layout.addWidget(model_frame)

        # 状态信息
        stats_grid = QGridLayout()
        stats = [
            ("14", "MODELS"), ("632K", "TOKENS"),
            ("9", "SKILLS"), ("10", "TOOLS")
        ]
        for i, (val, label) in enumerate(stats):
            val_lbl = QLabel(val)
            val_lbl.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {THEME['text_primary']};")
            label_lbl = QLabel(label)
            label_lbl.setStyleSheet(f"font-size: 10px; color: {THEME['text_secondary']};")
            stats_grid.addWidget(val_lbl, i // 2 * 2, i % 2)
            stats_grid.addWidget(label_lbl, i // 2 * 2 + 1, i % 2)
        sidebar_layout.addLayout(stats_grid)

        # 导航按钮
        sidebar_layout.addSpacing(20)

        self.nav_buttons = []
        nav_items = [
            ("💬", "Chat", "御前对话", None),
            ("🧠", "Model", "模型管理", None),
            ("📊", "Tokens", "用量账本", None),
        ]

        for icon, label, desc, badge in nav_items:
            btn = NavButton(icon, label, badge)
            btn.clicked.connect(lambda checked, l=label: self.switch_page(l))
            self.nav_buttons.append((btn, label))
            sidebar_layout.addWidget(btn)

            # 描述文字
            if desc:
                desc_lbl = QLabel(f"    {desc}")
                desc_lbl.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
                sidebar_layout.addWidget(desc_lbl)

        sidebar_layout.addStretch()

        # 底部版本
        version = QLabel("v1.0.0 · EmperorAgent")
        version.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        sidebar_layout.addWidget(version)

        main_layout.addWidget(sidebar)

        # ========== 右侧内容区 ==========
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background-color: {THEME['bg']};")

        # 添加页面
        self.pages = {
            "Chat": ChatPage(),
            "Tokens": TokensPage(),
            "Model": QWidget(),  # 占位
        }

        for page in self.pages.values():
            self.stack.addWidget(page)

        main_layout.addWidget(self.stack, 1)

        # 默认选中 Chat
        self.switch_page("Tokens")  # 先显示用量账本看看效果

    def switch_page(self, label):
        """切换页面"""
        for btn, lbl in self.nav_buttons:
            btn.setChecked(lbl == label)

        if label in self.pages:
            self.stack.setCurrentWidget(self.pages[label])


# ==================== 启动 ====================
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 全局字体
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)

    # 全局样式
    app.setStyleSheet(f"""
        QMainWindow {{
            background-color: {THEME["bg"]};
        }}
        QScrollBar:vertical {{
            background: {THEME["sidebar_bg"]};
            width: 8px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical {{
            background: {THEME["border"]};
            border-radius: 4px;
        }}
    """)

    window = EmperorAgent()
    window.show()
    sys.exit(app.exec())