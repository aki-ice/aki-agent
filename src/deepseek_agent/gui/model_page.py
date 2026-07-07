from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget

from .model_config_store import ModelConfig, ModelConfigStore
from .theme import C, FONT_SERIF, card_style, input_style, primary_button_style, secondary_button_style, shadow


class ModelPage(QWidget):
    model_selected = pyqtSignal(str)
    config_selected = pyqtSignal(str, str, str)

    def __init__(self, current_model: str = "deepseek-v4-pro", parent=None):
        super().__init__(parent)
        self._current_model = current_model
        self._store = ModelConfigStore()
        self._configs: dict[int, ModelConfig] = {}
        self._build()
        self.refresh()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {C['bg']}; }}")
        content = QWidget()
        content.setStyleSheet(f"background-color: {C['bg']}; QLabel {{ background: transparent; border: none; }}")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 26, 32, 34)
        layout.setSpacing(16)

        title = QLabel("模型与 API 配置")
        title.setStyleSheet(f"background: transparent; border: none; color: {C['text']}; font-family: {FONT_SERIF}; font-size: 24px; font-weight: 900;")
        layout.addWidget(title)
        desc = QLabel("添加任意 OpenAI-compatible API：模型名、Base URL 和 API Key。选择后会立即应用到当前 Agent。")
        desc.setStyleSheet(f"background: transparent; border: none; color: {C['muted']}; font-size: 11px;")
        layout.addWidget(desc)

        cur = self._card()
        cl = QVBoxLayout(cur)
        cl.setContentsMargins(20, 16, 20, 16)
        cl.addWidget(self._label("CURRENT MODEL"))
        self._cur_model_lbl = QLabel(self._current_model)
        self._cur_model_lbl.setStyleSheet(f"background: transparent; border: none; color: {C['primary']}; font-size: 24px; font-weight: 900;")
        cl.addWidget(self._cur_model_lbl)
        layout.addWidget(cur)

        list_card = self._card()
        ll = QVBoxLayout(list_card)
        ll.setContentsMargins(20, 16, 20, 16)
        ll.setSpacing(10)
        ll.addWidget(self._label("SAVED CONFIGS"))
        self._config_list = QListWidget()
        self._config_list.setMinimumHeight(220)
        self._config_list.setStyleSheet(f"QListWidget {{ background-color: {C['panel']}; border: 1px solid {C['border']}; border-radius: 12px; color: {C['text']}; padding: 6px; }} QListWidget::viewport {{ background-color: {C['panel']}; }} QListWidget::item {{ background-color: {C['panel']}; padding: 10px; border-radius: 8px; margin: 2px; }} QListWidget::item:selected {{ background-color: {C['panel_deep']}; color: {C['primary']}; }}")
        ll.addWidget(self._config_list)
        btns = QHBoxLayout()
        apply_btn = QPushButton("应用选中配置")
        apply_btn.clicked.connect(self._apply_selected)
        apply_btn.setStyleSheet(primary_button_style())
        btns.addWidget(apply_btn)
        delete_btn = QPushButton("删除选中配置")
        delete_btn.clicked.connect(self._delete_selected)
        delete_btn.setStyleSheet(secondary_button_style())
        btns.addWidget(delete_btn)
        btns.addStretch()
        ll.addLayout(btns)
        layout.addWidget(list_card)

        form = self._card()
        fl = QVBoxLayout(form)
        fl.setContentsMargins(20, 16, 20, 16)
        fl.setSpacing(10)
        fl.addWidget(self._label("ADD CUSTOM PROVIDER / MODEL"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        self._name_input = self._input("例如：我的 DeepSeek Pro")
        self._provider_input = self._input("例如：DeepSeek / OpenAI / OpenRouter")
        self._model_input = self._input("例如：deepseek-v4-pro / gpt-4o-mini")
        self._base_url_input = self._input("例如：https://api.deepseek.com/v1")
        self._api_key_input = self._input("API Key")
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        fields = [
            ("名称", self._name_input),
            ("Provider", self._provider_input),
            ("模型名", self._model_input),
            ("Base URL", self._base_url_input),
            ("API Key", self._api_key_input),
        ]
        for row, (label, widget) in enumerate(fields):
            grid.addWidget(self._label(label), row, 0)
            grid.addWidget(widget, row, 1)
        fl.addLayout(grid)
        add_btn = QPushButton("添加并应用")
        add_btn.clicked.connect(self._add_config)
        add_btn.setStyleSheet(primary_button_style())
        fl.addWidget(add_btn)
        layout.addWidget(form)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def refresh(self) -> None:
        self._configs = {cfg.id: cfg for cfg in self._store.list_configs()}
        self._config_list.clear()
        for cfg in self._configs.values():
            masked = cfg.api_key[:6] + "..." + cfg.api_key[-4:] if cfg.api_key else "使用当前环境 API Key"
            item = QListWidgetItem(f"{cfg.name}\n{cfg.provider} · {cfg.model}\n{cfg.base_url}\n{masked}")
            item.setData(Qt.ItemDataRole.UserRole, cfg.id)
            self._config_list.addItem(item)

    def set_current_model(self, model: str) -> None:
        self._current_model = model
        self._cur_model_lbl.setText(model)

    def _add_config(self) -> None:
        name = self._name_input.text().strip()
        provider = self._provider_input.text().strip() or "Custom"
        model = self._model_input.text().strip()
        base_url = self._base_url_input.text().strip()
        api_key = self._api_key_input.text().strip()
        if not name or not model or not base_url:
            QMessageBox.warning(self, "提示", "名称、模型名和 Base URL 必填。")
            return
        config_id = self._store.add_config(name, provider, model, base_url, api_key)
        self.refresh()
        self._select_config_id(config_id)
        self._apply_config(self._configs[config_id])
        for widget in [self._name_input, self._provider_input, self._model_input, self._base_url_input, self._api_key_input]:
            widget.clear()

    def _apply_selected(self) -> None:
        item = self._config_list.currentItem()
        if not item:
            QMessageBox.information(self, "提示", "请先选择一个配置。")
            return
        cfg = self._configs.get(int(item.data(Qt.ItemDataRole.UserRole)))
        if cfg:
            self._apply_config(cfg)

    def _delete_selected(self) -> None:
        item = self._config_list.currentItem()
        if not item:
            return
        config_id = int(item.data(Qt.ItemDataRole.UserRole))
        self._store.delete_config(config_id)
        self.refresh()

    def _select_config_id(self, config_id: int) -> None:
        for index in range(self._config_list.count()):
            item = self._config_list.item(index)
            if int(item.data(Qt.ItemDataRole.UserRole)) == config_id:
                self._config_list.setCurrentItem(item)
                break

    def _apply_config(self, cfg: ModelConfig) -> None:
        self._store.touch(cfg.id)
        self.set_current_model(cfg.model)
        self.config_selected.emit(cfg.model, cfg.base_url, cfg.api_key)

    def _input(self, placeholder: str) -> QLineEdit:
        widget = QLineEdit()
        widget.setPlaceholderText(placeholder)
        widget.setMinimumHeight(36)
        widget.setStyleSheet(input_style() + f"\nQLineEdit {{ background-color: {C['panel']}; }}")
        return widget

    def _card(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Card")
        frame.setStyleSheet(card_style(radius=18) + "\nQFrame#Card QLabel { background: transparent; border: none; }")
        frame.setGraphicsEffect(shadow(20, 30, 4))
        return frame

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"background: transparent; border: none; color: {C['muted']}; font-size: 10px; font-weight: 900;")
        return label
