from __future__ import annotations

from PyQt6.QtWidgets import QGraphicsDropShadowEffect
from PyQt6.QtGui import QColor


C = {
    "bg": "#F7FBFF",
    "bg_deep": "#EAF4FF",
    "sidebar": "#F5FAFF",
    "panel": "#FFFFFF",
    "panel_soft": "#F1F7FF",
    "panel_deep": "#E2F0FF",
    "border": "#C9DDF2",
    "border_soft": "#E1ECF8",
    "text": "#18324A",
    "muted": "#6D849A",
    "muted_2": "#96AABC",
    "primary": "#2F86E8",
    "primary_hover": "#1F74D2",
    "primary_dark": "#15549E",
    "accent": "#62A8FF",
    "accent_soft": "#CFE6FF",
    "success": "#2E8B57",
    "warning": "#C9822E",
    "danger": "#D45B6A",
    "white": "#FFFFFF",
    "shadow": "#9BBCE0",
}

FONT_FAMILY = "Microsoft YaHei UI"
FONT_SERIF = "SimSun"
FONT_NUMBER = "Georgia"


def shadow(blur: int = 24, alpha: int = 42, y: int = 5) -> QGraphicsDropShadowEffect:
    effect = QGraphicsDropShadowEffect()
    effect.setBlurRadius(blur)
    effect.setColor(QColor(72, 126, 190, alpha))
    effect.setOffset(0, y)
    return effect


def app_stylesheet() -> str:
    return f"""
        QMainWindow {{
            background-color: {C['bg']};
        }}
        QWidget {{
            color: {C['text']};
            font-family: {FONT_FAMILY};
        }}
        QLabel {{
            background: transparent;
            border: none;
        }}
        QToolTip {{
            background-color: {C['primary_dark']};
            color: {C['white']};
            border: none;
            border-radius: 6px;
            padding: 6px 8px;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 9px;
            margin: 4px 2px 4px 2px;
        }}
        QScrollBar::handle:vertical {{
            background: {C['border']};
            border-radius: 4px;
            min-height: 32px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {C['accent_soft']};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar:horizontal {{
            height: 0;
        }}
    """


def card_style(radius: int = 18, border: str | None = None, bg: str | None = None) -> str:
    return f"""
        QFrame#Card {{
            background-color: {bg or C['panel']};
            border: 1px solid {border or C['border']};
            border-radius: {radius}px;
        }}
    """


def primary_button_style(radius: int = 12) -> str:
    return f"""
        QPushButton {{
            background-color: {C['primary']};
            color: {C['white']};
            border: none;
            border-radius: {radius}px;
            padding: 8px 16px;
            font-weight: 700;
        }}
        QPushButton:hover {{
            background-color: {C['primary_hover']};
        }}
        QPushButton:disabled {{
            background-color: {C['border']};
            color: {C['muted']};
        }}
    """


def secondary_button_style(radius: int = 10) -> str:
    return f"""
        QPushButton {{
            background-color: {C['panel_soft']};
            color: {C['text']};
            border: 1px solid {C['border']};
            border-radius: {radius}px;
            padding: 7px 12px;
        }}
        QPushButton:hover {{
            background-color: {C['panel_deep']};
            color: {C['primary']};
        }}
    """


def input_style() -> str:
    return f"""
        QLineEdit, QTextEdit, QComboBox {{
            background-color: {C['panel']};
            color: {C['text']};
            border: 1px solid {C['border']};
            border-radius: 10px;
            padding: 8px 10px;
            selection-background-color: {C['accent_soft']};
        }}
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
            border-color: {C['primary']};
        }}
        QComboBox QAbstractItemView {{
            background-color: {C['panel']};
            color: {C['text']};
            border: 1px solid {C['border']};
            selection-background-color: {C['panel_deep']};
        }}
    """
