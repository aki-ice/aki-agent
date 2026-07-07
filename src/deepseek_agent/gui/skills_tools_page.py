from __future__ import annotations

import shutil
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .plugin_importer import PluginImporter, PluginImportError
from .plugin_store import PluginInfo, PluginStore
from .theme import C, FONT_SERIF, card_style, primary_button_style, secondary_button_style, shadow


class PluginCard(QFrame):
    toggled = pyqtSignal(str, bool)
    trusted = pyqtSignal(str, bool)
    detail_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(self, plugin: PluginInfo, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.setObjectName("Card")
        self.setStyleSheet(card_style(radius=16, bg=C["panel"]))
        self.setGraphicsEffect(shadow(16, 24, 3))
        self._build()

    def _build(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        info = QVBoxLayout()
        info.setSpacing(5)

        title_row = QHBoxLayout()
        name = QLabel(self.plugin.name)
        name.setStyleSheet(f"background-color: {C['panel']}; border: none; color: {C['text']}; font-size: 15px; font-weight: 900;")
        title_row.addWidget(name)

        source = QLabel(f"{self.plugin.source} · v{self.plugin.version}")
        source.setStyleSheet(f"background-color: {C['panel']}; border: none; color: {C['muted']}; font-size: 10px;")
        title_row.addWidget(source)
        title_row.addStretch()
        info.addLayout(title_row)

        desc = QLabel(self.plugin.description or "No description")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"background-color: {C['panel']}; border: none; color: {C['muted']}; font-size: 11px;")
        info.addWidget(desc)

        path = QLabel(self.plugin.entry_path)
        path.setWordWrap(True)
        path.setStyleSheet(f"background-color: {C['panel']}; border: none; color: {C['muted_2']}; font-size: 9px;")
        info.addWidget(path)

        if self.plugin.type == "tool" and self.plugin.source == "imported":
            warn_text = "已信任，可启用执行。" if self.plugin.trusted else "外部 Tool 未信任，不会执行。"
            warn_color = C["success"] if self.plugin.trusted else C["warning"]
            warn = QLabel(warn_text)
            warn.setStyleSheet(f"background-color: {C['panel']}; border: none; color: {warn_color}; font-size: 10px; font-weight: 800;")
            info.addWidget(warn)

        layout.addLayout(info, 1)

        actions = QVBoxLayout()
        actions.setSpacing(8)

        self.toggle_btn = QPushButton("已启用" if self.plugin.enabled else "已禁用")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(self.plugin.enabled)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._toggle)
        self._refresh_toggle_style()
        actions.addWidget(self.toggle_btn)

        detail_btn = QPushButton("详情")
        detail_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        detail_btn.clicked.connect(lambda: self.detail_requested.emit(self.plugin.id))
        detail_btn.setStyleSheet(secondary_button_style(10))
        actions.addWidget(detail_btn)

        if self.plugin.type == "tool" and self.plugin.source == "imported":
            trust_btn = QPushButton("取消信任" if self.plugin.trusted else "信任")
            trust_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            trust_btn.clicked.connect(lambda: self.trusted.emit(self.plugin.id, not self.plugin.trusted))
            trust_btn.setStyleSheet(primary_button_style(10) if not self.plugin.trusted else secondary_button_style(10))
            actions.addWidget(trust_btn)

        if self.plugin.source == "imported":
            delete_btn = QPushButton("删除")
            delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.plugin.id))
            delete_btn.setStyleSheet(secondary_button_style(10))
            actions.addWidget(delete_btn)

        actions.addStretch()
        layout.addLayout(actions)

    def _toggle(self) -> None:
        enabled = self.toggle_btn.isChecked()
        self.toggle_btn.setText("已启用" if enabled else "已禁用")
        self._refresh_toggle_style()
        self.toggled.emit(self.plugin.id, enabled)

    def _refresh_toggle_style(self) -> None:
        if self.toggle_btn.isChecked():
            self.toggle_btn.setStyleSheet(primary_button_style(10))
        else:
            self.toggle_btn.setStyleSheet(secondary_button_style(10))


class SkillsToolsPage(QWidget):
    plugin_changed = pyqtSignal()

    def __init__(self, store: PluginStore, parent=None):
        super().__init__(parent)
        self.store = store
        self.importer = PluginImporter(store)
        self._selected_zip: str | None = None
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

        title = QLabel("Skills & Tools")
        title.setStyleSheet(f"background-color: {C['bg']}; border: none; color: {C['text']}; font-family: {FONT_SERIF}; font-size: 24px; font-weight: 900;")
        layout.addWidget(title)

        desc = QLabel("选择要启用的技能和工具，或从 ZIP 导入新的 Skill/Tool。")
        desc.setStyleSheet(f"background-color: {C['bg']}; border: none; color: {C['muted']}; font-size: 11px;")
        layout.addWidget(desc)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background: {C['bg']}; }}
            QTabBar::tab {{
                background: {C['panel_soft']};
                color: {C['text']};
                border: 1px solid {C['border']};
                border-radius: 10px;
                padding: 8px 18px;
                margin-right: 8px;
                font-weight: 800;
            }}
            QTabBar::tab:selected {{
                background: {C['primary']};
                color: {C['white']};
            }}
        """)

        self.skills_tab = self._list_tab()
        self.tools_tab = self._list_tab()
        self.import_tab = self._import_tab()
        self.tabs.addTab(self.skills_tab, "Skills")
        self.tabs.addTab(self.tools_tab, "Tools")
        self.tabs.addTab(self.import_tab, "Import")
        layout.addWidget(self.tabs)

        layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll)

    def _list_tab(self) -> QWidget:
        tab = QWidget()
        tab.setStyleSheet(f"background-color: {C['bg']};")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(12)
        layout.addStretch()
        return tab

    def _import_tab(self) -> QWidget:
        tab = QWidget()
        tab.setStyleSheet(f"background-color: {C['bg']};")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(12)

        card = QFrame()
        card.setObjectName("Card")
        card.setStyleSheet(card_style(radius=18))
        card.setGraphicsEffect(shadow(18, 28, 4))
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(10)

        tip = QLabel("ZIP 中必须包含 manifest.json。Skill 导入后可直接启用；外部 Tool 需要先确认信任，然后才能启用执行。")
        tip.setWordWrap(True)
        tip.setStyleSheet(f"background-color: {C['panel']}; border: none; color: {C['muted']}; font-size: 11px;")
        card_layout.addWidget(tip)

        self.path_label = QLabel("未选择 ZIP 文件")
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet(f"background-color: {C['panel']}; border: none; color: {C['text']}; font-size: 11px;")
        card_layout.addWidget(self.path_label)

        btn_row = QHBoxLayout()
        choose_btn = QPushButton("选择 ZIP")
        choose_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        choose_btn.clicked.connect(self._choose_zip)
        choose_btn.setStyleSheet(secondary_button_style())
        btn_row.addWidget(choose_btn)

        import_btn = QPushButton("导入")
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.clicked.connect(self._import_zip)
        import_btn.setStyleSheet(primary_button_style())
        btn_row.addWidget(import_btn)

        export_btn = QPushButton("导出配置")
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.clicked.connect(self._export_config)
        export_btn.setStyleSheet(secondary_button_style())
        btn_row.addWidget(export_btn)
        btn_row.addStretch()
        card_layout.addLayout(btn_row)
        layout.addWidget(card)
        layout.addStretch()
        return tab

    def refresh(self) -> None:
        self.store.sync_builtins()
        self._render_list(self.skills_tab, self.store.list_plugins("skill"))
        self._render_list(self.tools_tab, self.store.list_plugins("tool"))

    def _render_list(self, tab: QWidget, plugins: list[PluginInfo]) -> None:
        layout = tab.layout()
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not plugins:
            empty = QLabel("暂无插件")
            empty.setStyleSheet(f"background-color: {C['bg']}; border: none; color: {C['muted']}; font-size: 12px;")
            layout.addWidget(empty)
        for plugin in plugins:
            card = PluginCard(plugin)
            card.toggled.connect(self._set_enabled)
            card.trusted.connect(self._set_trusted)
            card.detail_requested.connect(self._show_details)
            card.delete_requested.connect(self._delete_plugin)
            layout.addWidget(card)
        layout.addStretch()

    def _set_enabled(self, plugin_id: str, enabled: bool) -> None:
        plugin = self.store.get_plugin(plugin_id)
        if plugin and plugin.type == "tool" and plugin.source == "imported" and enabled and not plugin.trusted:
            QMessageBox.warning(self, "安全提示", "请先点击“信任”确认该外部 Tool 来源可信，然后再启用。")
            enabled = False
        self.store.set_enabled(plugin_id, enabled)
        self.refresh()
        self.plugin_changed.emit()

    def _delete_plugin(self, plugin_id: str) -> None:
        plugin = self.store.get_plugin(plugin_id)
        if not plugin or plugin.source != "imported":
            return
        reply = QMessageBox.question(self, "确认删除", f"确定删除 {plugin.name} 吗？")
        if reply != QMessageBox.StandardButton.Yes:
            return
        deleted = self.store.delete_plugin(plugin_id)
        if deleted:
            path = Path(deleted.entry_path)
            plugin_dir = path.parent
            if "data" in plugin_dir.parts and plugin_dir.exists():
                shutil.rmtree(plugin_dir, ignore_errors=True)
        self.refresh()
        self.plugin_changed.emit()

    def _choose_zip(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择插件 ZIP", "", "ZIP (*.zip)")
        if not path:
            return
        self._selected_zip = path
        self.path_label.setText(path)

    def _import_zip(self) -> None:
        if not self._selected_zip:
            QMessageBox.warning(self, "提示", "请先选择 ZIP 文件。")
            return
        try:
            result = self.importer.import_zip(self._selected_zip)
        except (PluginImportError, OSError) as exc:
            QMessageBox.critical(self, "导入失败", str(exc))
            return
        QMessageBox.information(self, "导入成功", f"{result.plugin.name}\n{result.message}")
        self._selected_zip = None
        self.path_label.setText("未选择 ZIP 文件")
        self.refresh()
        self.plugin_changed.emit()

    def _set_trusted(self, plugin_id: str, trusted: bool) -> None:
        plugin = self.store.get_plugin(plugin_id)
        if not plugin or plugin.type != "tool" or plugin.source != "imported":
            return
        if trusted:
            reply = QMessageBox.warning(
                self,
                "信任外部 Tool",
                "外部 Tool 会在本机执行 Python 代码。请确认来源可信后再继续。\n\n确定信任并允许启用该 Tool 吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.store.set_trusted(plugin_id, trusted)
        if not trusted:
            self.store.set_enabled(plugin_id, False)
        self.refresh()
        self.plugin_changed.emit()

    def _show_details(self, plugin_id: str) -> None:
        plugin = self.store.get_plugin(plugin_id)
        if not plugin:
            return
        detail = (
            f"ID: {plugin.id}\n"
            f"类型: {plugin.type}\n"
            f"名称: {plugin.name}\n"
            f"版本: {plugin.version}\n"
            f"来源: {plugin.source}\n"
            f"启用: {'是' if plugin.enabled else '否'}\n"
            f"信任: {'是' if plugin.trusted else '否'}\n"
            f"安装时间: {plugin.installed_at}\n"
            f"入口: {plugin.entry_path}\n\n"
            f"描述:\n{plugin.description or 'No description'}"
        )
        QMessageBox.information(self, "插件详情", detail)

    def _export_config(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "导出插件配置", "plugins_config.json", "JSON (*.json)")
        if not path:
            return
        try:
            self.store.export_config(path)
        except OSError as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        QMessageBox.information(self, "导出成功", path)

