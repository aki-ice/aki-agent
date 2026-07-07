from __future__ import annotations

import os

from dotenv import load_dotenv, set_key
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .theme import C, FONT_NUMBER, FONT_SERIF, card_style, input_style, primary_button_style, secondary_button_style, shadow


class NavButton(QPushButton):
    def __init__(self, icon: str, label: str, parent=None):
        super().__init__(parent)
        self._label = label
        self._icon = icon
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setText(f"  {icon}   {label}")
        self.setMinimumHeight(42)
        self._update_style(False)

    def _update_style(self, checked: bool) -> None:
        bg = C["panel_deep"] if checked else "transparent"
        fg = C["primary"] if checked else C["text"]
        weight = "800" if checked else "600"
        border = C["primary"] if checked else "transparent"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: none;
                border-left: 4px solid {border};
                border-radius: 12px;
                text-align: left;
                padding: 8px 14px;
                font-size: 13px;
                font-weight: {weight};
            }}
            QPushButton:hover {{
                background-color: {C['panel_deep']};
                color: {C['primary']};
            }}
        """)

    def setChecked(self, checked: bool) -> None:
        super().setChecked(checked)
        self._update_style(checked)


class MiniStat(QFrame):
    def __init__(self, title: str, value: str, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setStyleSheet(card_style(radius=13, bg=C["panel_soft"]))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        self._value = QLabel(value)
        self._value.setStyleSheet(f"background-color: {C['panel_soft']}; border: none; color: {C['text']}; font-family: {FONT_NUMBER}; font-size: 16px; font-weight: 800;")
        title_label = QLabel(title)
        title_label.setStyleSheet(f"background-color: {C['panel_soft']}; border: none; color: {C['muted']}; font-size: 9px; font-weight: 700;")
        layout.addWidget(self._value)
        layout.addWidget(title_label)

    def set_value(self, value: str) -> None:
        self._value.setText(value)


class Sidebar(QWidget):
    nav_changed = pyqtSignal(str)
    model_changed = pyqtSignal(str)
    api_changed = pyqtSignal(str, str)
    prompt_changed = pyqtSignal(str)
    token_reset = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(320)
        self.setStyleSheet(f"background-color: {C['sidebar']};")
        self._nav_buttons: dict[str, NavButton] = {}
        self._input_tokens = 0
        self._output_tokens = 0
        self._sessions = 0
        self._prompt_presets = {
            "默认助手": "你是在DeepSeek代理工作台中的一个有用助手。回答保持简明、专业且乐于助人。",
            "严谨研究员": "你是一名严谨的研究型助手。回答时先澄清事实来源，区分确定信息和推测，结构化给出结论、依据、风险与下一步建议。",
            "代码工程师": "你是一名资深软件工程师。回答时优先给出可执行方案、关键代码、边界情况、测试方法和工程权衡。",
            "温和陪伴型": "你是一名温和、耐心、鼓励式的助手。回答时语气友好，避免生硬措辞，先共情再给出清晰建议。",
            "简洁高效": "你是一名高效助手。回答必须简洁、直接、少废话，优先给出结论和行动步骤。",
        }
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(12)

        brand = QFrame()
        brand.setStyleSheet("QFrame { background: transparent; border: none; }")
        brand_row = QHBoxLayout(brand)
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(10)

        seal = QLabel("氷")
        seal.setFixedSize(48, 48)
        seal.setAlignment(Qt.AlignmentFlag.AlignCenter)
        seal.setStyleSheet(
            f"background-color: {C['primary']}; color: {C['white']}; border-radius: 14px; "
            f"font-family: {FONT_SERIF}; font-size: 28px; font-weight: 900;"
        )
        brand_row.addWidget(seal)

        title_box = QVBoxLayout()
        name = QLabel("AKI Agent")
        name.setStyleSheet(f"color: {C['text']}; font-size: 15px; font-weight: 900;")
        desc = QLabel("DeepSeek 工作台")
        desc.setStyleSheet(f"color: {C['muted']}; font-size: 10px;")
        title_box.addWidget(name)
        title_box.addWidget(desc)
        brand_row.addLayout(title_box)
        layout.addWidget(brand)

        model_card = self._card()
        ml = QVBoxLayout(model_card)
        ml.setContentsMargins(12, 10, 12, 10)
        ml.setSpacing(6)
        ml.addWidget(self._section_label("Model"))
        self._model_combo = QComboBox()
        self._model_combo.addItems([
            "deepseek-v4-pro",
            "deepseek-v4-flash",
            "deepseek-v4",
            "deepseek-chat",
            "deepseek-reasoner",
            "deepseek-coder",
        ])
        self._model_combo.setEditable(True)
        env_model = os.getenv("DEEPSEEK_MODEL", "")
        if env_model:
            self._model_combo.setCurrentText(env_model)
        self._model_combo.setMinimumHeight(38)
        self._model_combo.setStyleSheet(input_style())
        self._model_combo.currentTextChanged.connect(lambda t: self.model_changed.emit(t) if t else None)
        ml.addWidget(self._model_combo)
        layout.addWidget(model_card)

        api_card = self._card()
        al = QVBoxLayout(api_card)
        al.setContentsMargins(12, 10, 12, 10)
        al.setSpacing(6)
        al.addWidget(self._section_label("API Key"))

        key_row = QHBoxLayout()
        key_row.setSpacing(8)
        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setPlaceholderText("sk-...")
        key = os.getenv("DEEPSEEK_API_KEY", "")
        if key:
            self._api_key_input.setText(key)
        self._api_key_input.setMinimumHeight(32)
        self._api_key_input.setStyleSheet(input_style())
        key_row.addWidget(self._api_key_input)

        self._show_key_cb = QCheckBox()
        self._show_key_cb.setFixedWidth(26)
        self._show_key_cb.setToolTip("显示/隐藏 API Key")
        self._show_key_cb.stateChanged.connect(self._toggle_key_vis)
        key_row.addWidget(self._show_key_cb)
        al.addLayout(key_row)

        al.addWidget(self._section_label("Base URL"))
        self._base_url_input = QLineEdit()
        self._base_url_input.setText(os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
        self._base_url_input.setMinimumHeight(32)
        self._base_url_input.setStyleSheet(input_style())
        al.addWidget(self._base_url_input)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        import_btn = QPushButton("导入")
        import_btn.setMinimumHeight(30)
        import_btn.setMinimumWidth(68)
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.clicked.connect(self._import_env)
        import_btn.setStyleSheet(secondary_button_style(9))
        btn_row.addWidget(import_btn, 1)

        save_btn = QPushButton("保存")
        save_btn.setMinimumHeight(30)
        save_btn.setMinimumWidth(68)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save_env)
        save_btn.setStyleSheet(secondary_button_style(9))
        btn_row.addWidget(save_btn, 1)

        apply_btn = QPushButton("应用")
        apply_btn.setMinimumHeight(30)
        apply_btn.setMinimumWidth(68)
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.clicked.connect(self._apply_config)
        apply_btn.setStyleSheet(primary_button_style(9))
        btn_row.addWidget(apply_btn, 1)
        al.addLayout(btn_row)
        layout.addWidget(api_card)
        model_card.setVisible(False)
        api_card.setVisible(False)

        prompt_card = self._card()
        pl = QVBoxLayout(prompt_card)
        pl.setContentsMargins(12, 10, 12, 10)
        pl.setSpacing(7)
        pl.addWidget(self._section_label("Prompt 提示词"))
        self._prompt_combo = QComboBox()
        self._prompt_combo.addItems(list(self._prompt_presets.keys()))
        self._prompt_combo.currentTextChanged.connect(self._load_prompt_preset)
        self._prompt_combo.setMinimumHeight(32)
        self._prompt_combo.setStyleSheet(input_style())
        pl.addWidget(self._prompt_combo)
        self._prompt_input = QTextEdit()
        self._prompt_input.setPlaceholderText("输入系统提示词，用来定义 AI 的回答方式、性格、角色和约束...")
        self._prompt_input.setMinimumHeight(118)
        self._prompt_input.setMaximumHeight(150)
        self._prompt_input.setStyleSheet(input_style())
        env_prompt = os.getenv("DEEPSEEK_SYSTEM_PROMPT", "").strip()
        self._prompt_input.setPlainText(env_prompt or self._prompt_presets["默认助手"])
        pl.addWidget(self._prompt_input)
        prompt_btns = QHBoxLayout()
        import_prompt_btn = QPushButton("导入")
        import_prompt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_prompt_btn.clicked.connect(self._import_prompt_file)
        import_prompt_btn.setStyleSheet(secondary_button_style(9))
        prompt_btns.addWidget(import_prompt_btn)
        save_prompt_btn = QPushButton("保存")
        save_prompt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_prompt_btn.clicked.connect(self._save_prompt)
        save_prompt_btn.setStyleSheet(secondary_button_style(9))
        prompt_btns.addWidget(save_prompt_btn)
        apply_prompt_btn = QPushButton("应用")
        apply_prompt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_prompt_btn.clicked.connect(self._apply_prompt)
        apply_prompt_btn.setStyleSheet(primary_button_style(9))
        prompt_btns.addWidget(apply_prompt_btn)
        pl.addLayout(prompt_btns)
        layout.addWidget(prompt_card)

        stat_grid = QHBoxLayout()
        stat_grid.setSpacing(8)
        self._session_stat = MiniStat("SESSIONS", "0")
        self._token_stat = MiniStat("TOKENS", "0")
        stat_grid.addWidget(self._session_stat)
        stat_grid.addWidget(self._token_stat)
        layout.addLayout(stat_grid)

        nav_title = QLabel("NAVIGATION")
        nav_title.setStyleSheet(f"color: {C['muted']}; font-size: 10px; font-weight: 900; padding-left: 4px;")
        layout.addWidget(nav_title)

        nav_items = [("首页", "Dashboard"), ("对话", "Chat"), ("模型", "Model"), ("记忆", "Memory"), ("团队", "Team"), ("技能", "SkillsTools"), ("令牌", "Tokens")]
        for icon, label in nav_items:
            btn = NavButton(icon, label)
            btn.clicked.connect(lambda checked, l=label: self._on_nav(l))
            self._nav_buttons[label] = btn
            layout.addWidget(btn)

        token_card = self._card()
        tl = QVBoxLayout(token_card)
        tl.setContentsMargins(12, 10, 12, 10)
        tl.setSpacing(4)
        tl.addWidget(self._section_label("TOKEN USAGE"))
        self._input_tok_lbl = QLabel("Input:   0")
        self._output_tok_lbl = QLabel("Output:  0")
        self._total_tok_lbl = QLabel("Total:   0")
        for label in [self._input_tok_lbl, self._output_tok_lbl, self._total_tok_lbl]:
            label.setStyleSheet(f"color: {C['text']}; font-family: Consolas; font-size: 11px;")
            tl.addWidget(label)
        reset_btn = QPushButton("Reset")
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self.reset_tokens)
        reset_btn.setStyleSheet(secondary_button_style(8))
        tl.addWidget(reset_btn)
        layout.addWidget(token_card)

        layout.addStretch()
        version = QLabel("v1.0.0  ·  DeepSeek Agent")
        version.setStyleSheet(f"color: {C['muted']}; font-size: 10px; padding-left: 4px;")
        layout.addWidget(version)

        self._on_nav("Dashboard")

    def _card(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Card")
        frame.setStyleSheet(card_style(radius=14, bg=C["panel_soft"]))
        frame.setGraphicsEffect(shadow(14, 22, 3))
        return frame

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"color: {C['muted']}; font-size: 9px; font-weight: 900;")
        return label

    def _on_nav(self, label: str) -> None:
        for lbl, btn in self._nav_buttons.items():
            btn.setChecked(lbl == label)
        self.nav_changed.emit(label)

    def _toggle_key_vis(self) -> None:
        mode = QLineEdit.EchoMode.Normal if self._show_key_cb.isChecked() else QLineEdit.EchoMode.Password
        self._api_key_input.setEchoMode(mode)

    def _import_env(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select .env", "", "ENV (*.env);;All (*)")
        if not path:
            return
        load_dotenv(path, override=True)
        for var_name, setter in [
            ("DEEPSEEK_API_KEY", self._api_key_input.setText),
            ("DEEPSEEK_BASE_URL", self._base_url_input.setText),
            ("DEEPSEEK_MODEL", self._model_combo.setCurrentText),
        ]:
            val = os.getenv(var_name, "")
            if val:
                setter(val)
        self._apply_config()
        QMessageBox.information(self, "OK", f"Imported from {os.path.basename(path)}")

    def _save_env(self) -> None:
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            ".env",
        )
        try:
            set_key(env_path, "DEEPSEEK_API_KEY", self._api_key_input.text())
            set_key(env_path, "DEEPSEEK_BASE_URL", self._base_url_input.text())
            set_key(env_path, "DEEPSEEK_MODEL", self._model_combo.currentText())
            load_dotenv(env_path, override=True)
            QMessageBox.information(self, "OK", "Saved to .env")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _apply_config(self) -> None:
        key = self._api_key_input.text().strip()
        url = self._base_url_input.text().strip()
        model = self._model_combo.currentText().strip()
        if key:
            os.environ["DEEPSEEK_API_KEY"] = key
        if url:
            os.environ["DEEPSEEK_BASE_URL"] = url
        if model:
            os.environ["DEEPSEEK_MODEL"] = model
        self.api_changed.emit(key, url)

    def _load_prompt_preset(self, name: str) -> None:
        prompt = self._prompt_presets.get(name)
        if prompt:
            self._prompt_input.setPlainText(prompt)

    def _import_prompt_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "导入提示词", "", "Prompt (*.md *.txt);;Markdown (*.md);;Text (*.txt);;All (*)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                self._prompt_input.setPlainText(fh.read().strip())
            self._apply_prompt()
            QMessageBox.information(self, "OK", f"已导入 {os.path.basename(path)}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _save_prompt(self) -> None:
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            ".env",
        )
        try:
            set_key(env_path, "DEEPSEEK_SYSTEM_PROMPT", self.current_system_prompt)
            load_dotenv(env_path, override=True)
            QMessageBox.information(self, "OK", "Prompt 已保存到 .env")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _apply_prompt(self) -> None:
        prompt = self.current_system_prompt
        if prompt:
            os.environ["DEEPSEEK_SYSTEM_PROMPT"] = prompt
        self.prompt_changed.emit(prompt)

    def add_session(self) -> None:
        self._sessions += 1
        self._session_stat.set_value(str(self._sessions))

    def add_tokens(self, inp: int, out: int) -> None:
        self._input_tokens += inp
        self._output_tokens += out
        self._draw_tokens()

    def reset_tokens(self) -> None:
        self._input_tokens = 0
        self._output_tokens = 0
        self._draw_tokens()
        self.token_reset.emit()

    def _draw_tokens(self) -> None:
        total = self._input_tokens + self._output_tokens
        self._input_tok_lbl.setText(f"Input:   {self._input_tokens:,}")
        self._output_tok_lbl.setText(f"Output:  {self._output_tokens:,}")
        self._total_tok_lbl.setText(f"Total:   {total:,}")
        self._token_stat.set_value(f"{total // 1000}K" if total >= 1000 else str(total))

    def set_model(self, model: str) -> None:
        if model:
            self._model_combo.setCurrentText(model)

    def set_api_config(self, api_key: str, base_url: str, model: str) -> None:
        if api_key:
            self._api_key_input.setText(api_key)
        if base_url:
            self._base_url_input.setText(base_url)
        if model:
            self._model_combo.setCurrentText(model)
        self._apply_config()

    @property
    def current_system_prompt(self) -> str:
        return self._prompt_input.toPlainText().strip()

    @property
    def current_model(self) -> str:
        return self._model_combo.currentText().strip()

    @property
    def api_key(self) -> str:
        return self._api_key_input.text().strip()

    @property
    def base_url(self) -> str:
        return self._base_url_input.text().strip()

    @property
    def input_tokens(self) -> int:
        return self._input_tokens

    @property
    def output_tokens(self) -> int:
        return self._output_tokens

    @property
    def sessions(self) -> int:
        return self._sessions
