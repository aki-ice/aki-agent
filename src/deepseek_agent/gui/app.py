from __future__ import annotations

import os
import sys
import warnings

os.environ["QT_LOGGING_RULES"] = "*.debug=false;qt.qpa.*=false;qt.image.png.*=false"
warnings.filterwarnings("ignore", category=DeprecationWarning)

from dotenv import load_dotenv
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from .main_window import MainWindow
from .theme import FONT_FAMILY, app_stylesheet


def launch_gui() -> None:
    load_dotenv()
    app = QApplication(sys.argv)
    app.setApplicationName("DeepSeek Agent Workbench")
    app.setOrganizationName("DeepSeek Agent")
    app.setFont(QFont(FONT_FAMILY, 10))
    app.setStyleSheet(app_stylesheet())

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    launch_gui()
