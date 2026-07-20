from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget

from .chat_store import ChatSession
from .theme import C, FONT_SERIF, input_style, primary_button_style, secondary_button_style, shadow

MAX_BUBBLE_WIDTH = 680


class ChatPage(QWidget):
    stop_requested = pyqtSignal()
    send_message = pyqtSignal(str)
    clear_requested = pyqtSignal()
    new_session_requested = pyqtSignal()
    session_selected = pyqtSignal(int)
    delete_session_requested = pyqtSignal()
    search_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sending = False
        self._empty = True
        self._loading_sessions = False
        self._stream_bubble: QLabel | None = None
        self._stream_text = ""
        self._current_session_id: int | None = None
        self._build()

    def _build(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        side = QFrame()
        side.setFixedWidth(230)
        side.setStyleSheet(f"background-color: {C['panel_soft']}; border-right: 1px solid {C['border']};")
        sl = QVBoxLayout(side)
        sl.setContentsMargins(12, 14, 12, 14)
        sl.setSpacing(10)
        title = QLabel("历史对话")
        title.setStyleSheet(f"color: {C['text']}; font-size: 15px; font-weight: 900; background: transparent; border: none;")
        sl.addWidget(title)
        new_btn = QPushButton("新建对话")
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self.new_session_requested.emit)
        new_btn.setStyleSheet(primary_button_style(10))
        sl.addWidget(new_btn)
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("全文搜索会话...")
        self._search_input.setStyleSheet(input_style())
        self._search_input.returnPressed.connect(lambda: self.search_requested.emit(self._search_input.text()))
        self._search_input.textChanged.connect(lambda text: self.search_requested.emit(text) if not text else None)
        sl.addWidget(self._search_input)
        self._session_list = QListWidget()
        self._session_list.setStyleSheet(f"QListWidget {{ background-color: {C['panel_soft']}; border: none; color: {C['text']}; }} QListWidget::item {{ padding: 10px 8px; border-radius: 10px; margin: 2px 0; }} QListWidget::item:selected {{ background-color: {C['panel_deep']}; color: {C['primary']}; }}")
        self._session_list.currentItemChanged.connect(self._on_session_item_changed)
        sl.addWidget(self._session_list, 1)
        del_btn = QPushButton("删除当前对话")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.clicked.connect(self.delete_session_requested.emit)
        del_btn.setStyleSheet(secondary_button_style(10))
        sl.addWidget(del_btn)
        outer.addWidget(side)

        main = QVBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        outer.addLayout(main, 1)
        top = QFrame()
        top.setFixedHeight(64)
        top.setStyleSheet(f"background-color: {C['bg']}; border-bottom: 1px solid {C['border_soft']};")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(28, 0, 28, 0)
        self._title = QLabel("对话")
        self._title.setStyleSheet(f"color: {C['text']}; font-family: {FONT_SERIF}; font-size: 20px; font-weight: 900;")
        tl.addWidget(self._title)
        tl.addStretch()
        self._status_indicator = QLabel("● Ready")
        self._status_indicator.setStyleSheet(f"color: {C['success']}; font-size: 11px; font-weight: 800;")
        tl.addWidget(self._status_indicator)
        main.addWidget(top)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {C['bg']}; }}")
        self._msg_container = QWidget()
        self._msg_container.setStyleSheet(f"background-color: {C['bg']};")
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(26, 18, 26, 18)
        self._msg_layout.setSpacing(8)
        self._msg_layout.addStretch()
        self._scroll.setWidget(self._msg_container)
        main.addWidget(self._scroll, 1)
        self._show_welcome()

        input_frame = QFrame()
        input_frame.setStyleSheet(f"background-color: {C['bg']}; border-top: 1px solid {C['border_soft']};")
        il = QVBoxLayout(input_frame)
        il.setContentsMargins(24, 12, 24, 14)
        il.setSpacing(8)
        self._input = QTextEdit()
        self._input.setPlaceholderText("请输入你的问题...  Ctrl+Enter 发送")
        self._input.setMaximumHeight(106)
        self._input.setStyleSheet(input_style())
        self._input.setGraphicsEffect(shadow(16, 22, 3))
        il.addWidget(self._input)
        br = QHBoxLayout()
        hint = QLabel("Ctrl+Enter  Send")
        hint.setStyleSheet(f"color: {C['muted']}; font-size: 10px;")
        br.addWidget(hint)
        br.addStretch()
        attach_btn = QPushButton("文档 / 图片")
        attach_btn.clicked.connect(self._attach_document)
        attach_btn.setStyleSheet(secondary_button_style())
        br.addWidget(attach_btn)
        clear_btn = QPushButton("清空当前显示")
        clear_btn.clicked.connect(self.clear_chat)
        clear_btn.setStyleSheet(secondary_button_style())
        br.addWidget(clear_btn)
        self._send_btn = QPushButton("发送")
        self._send_btn.clicked.connect(self._send_or_stop)
        self._send_btn.setStyleSheet(primary_button_style())
        br.addWidget(self._send_btn)
        il.addLayout(br)
        main.addWidget(input_frame)

    def set_sessions(self, sessions: list[ChatSession], current_id: int | None) -> None:
        self._loading_sessions = True
        self._session_list.clear()
        for s in sessions:
            item = QListWidgetItem(f"{s.title}\n{s.updated_at.replace('T', ' ')} · {s.message_count} 条")
            item.setData(Qt.ItemDataRole.UserRole, s.id)
            self._session_list.addItem(item)
            if current_id == s.id:
                self._session_list.setCurrentItem(item)
        self._current_session_id = current_id
        self._loading_sessions = False

    def load_messages(self, title: str, messages: list[dict[str, str]]) -> None:
        self._title.setText(title or "对话")
        self._clear_messages()
        self._stream_bubble = None
        self._stream_text = ""
        if not messages:
            self._show_welcome()
            return
        self._empty = False
        for m in messages:
            role = m.get("role", "assistant")
            if role in {"user", "assistant", "system"}:
                self._add_bubble(role, m.get("content", ""))

    def _on_session_item_changed(self, cur: QListWidgetItem | None, _prev: QListWidgetItem | None) -> None:
        if self._loading_sessions or cur is None:
            return
        sid = cur.data(Qt.ItemDataRole.UserRole)
        if isinstance(sid, int) and sid != self._current_session_id:
            self._current_session_id = sid
            self.session_selected.emit(sid)

    def _show_welcome(self) -> None:
        self._empty = True
        seal = QLabel("氷")
        seal.setFixedSize(74, 74)
        seal.setAlignment(Qt.AlignmentFlag.AlignCenter)
        seal.setStyleSheet(f"background-color: {C['primary']}; color: {C['white']}; border-radius: 20px; font-family: {FONT_SERIF}; font-size: 42px; font-weight: 900;")
        row = QHBoxLayout(); row.addStretch(); row.addWidget(seal); row.addStretch()
        self._msg_layout.insertLayout(self._msg_layout.count() - 1, row)
        for text, size in [("AKI Agent", 24), ("Ask anything  ·  Code  ·  Analyze  ·  Create", 11)]:
            lbl = QLabel(text); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {C['text'] if size == 24 else C['muted']}; font-size: {size}px; font-weight: {'900' if size == 24 else '400'};")
            self._msg_layout.insertWidget(self._msg_layout.count() - 1, lbl)

    def _clear_messages(self) -> None:
        while self._msg_layout.count() > 1:
            item = self._msg_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            elif item.layout(): self._clear_layout(item.layout())

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            elif item.layout(): self._clear_layout(item.layout())

    def _attach_document(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片或 PDF",
            "",
            "Documents (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.pdf *.doc *.docx *.ppt *.pptx *.xls *.xlsx);;Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff);;PDF (*.pdf);;Office (*.doc *.docx *.ppt *.pptx *.xls *.xlsx);;All files (*)",
        )
        if not path:
            return
        current = self._input.toPlainText().strip()
        instruction = f'请使用 paddle_ocr 工具解析文件："{path}"，并根据识别内容回答我的问题。'
        self._input.setPlainText(f"{current}\n\n{instruction}".strip())
        self._input.setFocus()
        QMessageBox.information(self, "已添加", "文件路径已加入消息。发送后 Agent 会调用 paddle_ocr。")

    def _send_or_stop(self) -> None:
        if self._sending:
            self._send_btn.setEnabled(False)
            self._send_btn.setText("停止中...")
            self.stop_requested.emit()
            return
        self._do_send()

    def _do_send(self) -> None:
        if self._sending: return
        text = self._input.toPlainText().strip()
        if not text: return
        self._sending = True
        self._send_btn.setEnabled(True)
        self._send_btn.setText("停止")
        self._send_btn.setStyleSheet(secondary_button_style())
        self._status_indicator.setText("● Thinking")
        self._status_indicator.setStyleSheet(f"color: {C['warning']}; font-size: 11px; font-weight: 800;")
        if self._empty:
            self._clear_messages(); self._empty = False
        self._add_bubble("user", text)
        self._input.clear()
        self._stream_begin()
        self.send_message.emit(text)

    def _stream_begin(self) -> None:
        self._stream_text = ""
        self._stream_bubble = self._add_bubble("assistant", "")

    def _stream_append(self, text: str) -> None:
        self._stream_text += text
        if self._stream_bubble:
            self._stream_bubble.setText(self._stream_text)
            QTimer.singleShot(30, self._scroll_bottom)

    def _on_stream_done(self, _full_text: str) -> None:
        self._stream_bubble = None
        self._stream_text = ""
        self._reset_ui()

    def _add_bubble(self, role: str, text: str) -> QLabel:
        cfg = {"user": (C["panel_deep"], C["text"], "You", "right", C["accent"]), "assistant": (C["panel"], C["text"], "Agent", "left", C["primary"]), "system": (C["panel_soft"], C["danger"], "System", "left", C["danger"])}[role]
        bg, fg, label, side, accent = cfg
        wrapper = QHBoxLayout(); wrapper.setContentsMargins(0, 0, 0, 0)
        if side == "right": wrapper.addStretch()
        bubble = QFrame(); bubble.setObjectName("Bubble")
        bubble.setStyleSheet(f"QFrame#Bubble {{ background-color: {bg}; border: 1px solid {C['border']}; border-radius: 16px; }}")
        bubble.setMaximumWidth(MAX_BUBBLE_WIDTH); bubble.setGraphicsEffect(shadow(18, 30, 4))
        bl = QVBoxLayout(bubble); bl.setContentsMargins(16, 11, 16, 13); bl.setSpacing(5)
        hdr = QHBoxLayout(); avatar = QLabel(label[0]); avatar.setFixedSize(24, 24); avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(f"background-color: {accent}; color: {C['white']}; border-radius: 12px; font-size: 10px; font-weight: 900;")
        hdr.addWidget(avatar); name = QLabel(label); name.setStyleSheet(f"background-color: {bg}; border: none; color: {accent}; font-size: 11px; font-weight: 900;")
        hdr.addWidget(name); tm = QLabel(datetime.now().strftime("%H:%M")); tm.setStyleSheet(f"background-color: {bg}; border: none; color: {C['muted']}; font-size: 9px;")
        hdr.addWidget(tm); hdr.addStretch(); bl.addLayout(hdr)
        msg = QLabel(text); msg.setWordWrap(True); msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        msg.setStyleSheet(f"background-color: {bg}; border: none; color: {fg}; font-size: 12px; line-height: 1.5;")
        bl.addWidget(msg); wrapper.addWidget(bubble)
        if side == "left": wrapper.addStretch()
        self._msg_layout.insertLayout(self._msg_layout.count() - 1, wrapper)
        QTimer.singleShot(60, self._scroll_bottom)
        return msg

    def add_system_message(self, text: str) -> None:
        if self._empty:
            self._clear_messages(); self._empty = False
        self._add_bubble("system", text)

    def _reset_ui(self) -> None:
        self._sending = False
        self._send_btn.setEnabled(True)
        self._send_btn.setText("发送")
        self._send_btn.setStyleSheet(primary_button_style())
        self._status_indicator.setText("● Ready")
        self._status_indicator.setStyleSheet(f"color: {C['success']}; font-size: 11px; font-weight: 800;")

    def clear_chat(self) -> None:
        self._clear_messages(); self._show_welcome(); self._stream_bubble = None; self._stream_text = ""
        self.clear_requested.emit()

    def _scroll_bottom(self) -> None:
        sb = self._scroll.verticalScrollBar(); sb.setValue(sb.maximum())
