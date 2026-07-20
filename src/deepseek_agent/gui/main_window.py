from __future__ import annotations

import os
import threading

from dotenv import load_dotenv
from openai import OpenAI
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..agent import DeepSeekAgent
from ..runtime import AgentError, CancelledError, ErrorCategory, RunContext, RunStatus, RunStore
from ..rag import Retriever
from ..file_workbench import FileWorkbench
from ..memory import LongTermMemory
from ..workflows import DocumentWorkflowService
from .file_workbench_page import FileWorkbenchPage
from .workflow_page import WorkflowPage
from .chat_page import ChatPage
from .chat_store import ChatStore
from .dashboard_page import DashboardPage
from .daily_memory_store import DailyMemoryStore
from .memory_page import MemoryPage
from .knowledge_page import KnowledgePage
from .long_term_memory_page import LongTermMemoryPage
from .operations_page import OperationsPage
from .model_page import ModelPage
from .plugin_store import PluginStore
from .sidebar import Sidebar
from .skills_tools_page import SkillsToolsPage
from .stats_store import StatsStore
from .team_page import TeamPage
from .theme import C
from .tokens_page import TokensPage


class QueryWorker(QObject):
    stream_chunk = pyqtSignal(str)
    stream_done = pyqtSignal(int, str, str, int, int, str, bool)
    stream_error = pyqtSignal(str)
    tokens_updated = pyqtSignal(int, int)
    status_update = pyqtSignal(str)
    approval_requested = pyqtSignal(object)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DeepSeek Agent Workbench")
        self.resize(1340, 1080)
        self.setMinimumSize(980, 640)

        self._agent: DeepSeekAgent | None = None
        self._lock = threading.Lock()
        self._request_count = 0
        self._session_input_tokens = 0
        self._session_output_tokens = 0
        self._stats_store = StatsStore()
        self._chat_store = ChatStore()
        self._current_chat_session_id: int | None = None
        self._daily_memory_store = DailyMemoryStore()
        self._plugin_store = PluginStore()
        self._run_store = RunStore()
        self._retriever = Retriever(embedder_backend="hash", store_path="data/knowledge_store.pkl")
        self._long_term_memory = LongTermMemory("data/long_term_memory.db", embedder=self._retriever.embedder)
        self._active_run: RunContext | None = None
        self._session_approvals: set[str] = set()

        self._build_ui()

        self._worker = QueryWorker()
        self._worker.stream_chunk.connect(self._chat_page._stream_append)
        self._worker.stream_done.connect(self._on_stream_done)
        self._worker.stream_error.connect(self._on_stream_error)
        self._worker.tokens_updated.connect(self._on_tokens_update)
        self._worker.status_update.connect(self._status_text.setText)
        self._worker.approval_requested.connect(self._show_approval)

        self._connect_signals()
        self._init_agent()
        self._ensure_chat_session()
        self._refresh_dashboard()

    def _build_ui(self) -> None:
        central = QWidget()
        central.setStyleSheet(f"background-color: {C['bg']};")
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._sidebar = Sidebar()
        main_layout.addWidget(self._sidebar)

        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background-color: {C['border']}; border: none;")
        main_layout.addWidget(sep)

        content_area = QVBoxLayout()
        content_area.setContentsMargins(0, 0, 0, 0)
        content_area.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background-color: {C['bg']};")

        self._dashboard_page = DashboardPage()
        self._chat_page = ChatPage()
        self._model_page = ModelPage(current_model=self._sidebar.current_model)
        self._memory_page = MemoryPage(self._daily_memory_store)
        self._long_term_memory_page = LongTermMemoryPage(self._long_term_memory)
        self._file_workbench = FileWorkbench(".")
        self._file_page = FileWorkbenchPage(self._file_workbench)
        self._workflow_page = WorkflowPage(DocumentWorkflowService())
        self._operations_page = OperationsPage(self._run_store)
        self._knowledge_page = KnowledgePage(self._retriever)
        self._team_page = TeamPage()
        self._skills_tools_page = SkillsToolsPage(self._plugin_store)
        self._tokens_page = TokensPage()

        self._stack.addWidget(self._dashboard_page)
        self._stack.addWidget(self._chat_page)
        self._stack.addWidget(self._model_page)
        self._stack.addWidget(self._memory_page)
        self._stack.addWidget(self._long_term_memory_page)
        self._stack.addWidget(self._file_page)
        self._stack.addWidget(self._knowledge_page)
        self._stack.addWidget(self._workflow_page)
        self._stack.addWidget(self._operations_page)
        self._stack.addWidget(self._team_page)
        self._stack.addWidget(self._skills_tools_page)
        self._stack.addWidget(self._tokens_page)
        content_area.addWidget(self._stack, 1)

        status_frame = QFrame()
        status_frame.setFixedHeight(34)
        status_frame.setStyleSheet(f"background-color: {C['panel_soft']}; border-top: 1px solid {C['border']};")
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(16, 0, 16, 0)

        self._status_text = QLabel("Ready")
        self._status_text.setStyleSheet(f"color: {C['success']}; font-size: 11px; font-weight: 700;")
        status_layout.addWidget(self._status_text)
        status_layout.addStretch()

        self._model_status = QLabel(self._sidebar.current_model)
        self._model_status.setStyleSheet(f"color: {C['primary']}; font-size: 11px; font-weight: 800;")
        status_layout.addWidget(self._model_status)

        content_area.addWidget(status_frame)
        main_layout.addLayout(content_area, 1)

    def _connect_signals(self) -> None:
        self._sidebar.nav_changed.connect(self._on_nav)
        self._sidebar.model_changed.connect(self._on_model_change)
        self._sidebar.api_changed.connect(self._on_api_change)
        self._sidebar.prompt_changed.connect(self._on_prompt_change)
        self._sidebar.token_reset.connect(self._on_token_reset)
        self._chat_page.send_message.connect(self._on_chat_send)
        self._chat_page.stop_requested.connect(self._cancel_active_run)
        self._chat_page.clear_requested.connect(self._on_token_reset)
        self._chat_page.new_session_requested.connect(self._new_chat_session)
        self._chat_page.session_selected.connect(self._load_chat_session)
        self._chat_page.delete_session_requested.connect(self._delete_current_chat_session)
        self._chat_page.search_requested.connect(self._search_chat_sessions)
        self._model_page.model_selected.connect(self._on_model_page_select)
        self._model_page.config_selected.connect(self._on_model_config_select)
        self._skills_tools_page.plugin_changed.connect(self._rebuild_agent)
        self._knowledge_page.knowledge_changed.connect(self._rebuild_agent)

    def _ensure_chat_session(self) -> None:
        sessions = self._chat_store.list_sessions()
        if sessions:
            self._current_chat_session_id = sessions[0].id
        else:
            self._current_chat_session_id = self._chat_store.create_session(model=self._sidebar.current_model)
        self._refresh_chat_sessions()
        self._load_chat_session(self._current_chat_session_id)

    def _refresh_chat_sessions(self) -> None:
        self._chat_page.set_sessions(self._chat_store.list_sessions(), self._current_chat_session_id)

    def _search_chat_sessions(self, query: str) -> None:
        query = query.strip()
        if not query:
            self._refresh_chat_sessions()
            return
        matched_ids = {result.session_id for result in self._chat_store.search(query)}
        sessions = [session for session in self._chat_store.list_sessions() if session.id in matched_ids]
        self._chat_page.set_sessions(sessions, self._current_chat_session_id)

    def _new_chat_session(self) -> None:
        self._current_chat_session_id = self._chat_store.create_session(model=self._sidebar.current_model)
        if self._agent:
            self._agent.reset()
        self._refresh_chat_sessions()
        self._load_chat_session(self._current_chat_session_id)

    def _load_chat_session(self, session_id: int | None) -> None:
        if session_id is None:
            return
        self._current_chat_session_id = session_id
        sessions = {session.id: session for session in self._chat_store.list_sessions()}
        messages = self._chat_store.messages(session_id)
        title = sessions.get(session_id).title if session_id in sessions else "对话"
        self._chat_page.load_messages(title, messages)
        if self._agent:
            self._restore_agent_history(messages)

    def _delete_current_chat_session(self) -> None:
        if self._current_chat_session_id is None:
            return
        self._chat_store.delete_session(self._current_chat_session_id)
        self._current_chat_session_id = None
        self._ensure_chat_session()

    def _restore_agent_history(self, messages: list[dict[str, str]]) -> None:
        if not self._agent:
            return
        self._agent.reset()
        for message in messages:
            role = message.get("role")
            content = message.get("content", "")
            if role in {"user", "assistant"} and content:
                self._agent.conv_memory.add(role, content)

    def _build_system_prompt(self) -> str:
        base_prompt = self._sidebar.current_system_prompt or os.getenv("DEEPSEEK_SYSTEM_PROMPT", "").strip()
        if not base_prompt:
            base_prompt = "You are a helpful assistant inside the DeepSeek Agent Workbench. Be concise, professional, and helpful."
        tool_policy = (
            "\n\nTool policy: For explicit search requests, latest news, current events, recent information, "
            "or source-based retrieval, use web_search. Use hot_news only when the user explicitly asks for "
            "热搜、热榜、排行榜、微博热搜、百度热搜 or trending lists. "
            "For file creation, writing, editing, deletion, copy, move, or rename requests, you must call the appropriate file tool "
            "such as write_file, edit_file, delete_path, copy_path, move_path, or create_directory. "
            "For tasks that ask you to search the web and generate a local document, first use web_search/web_fetch as needed, "
            "then use write_file to create the requested .md/.txt document; do not stop after only creating the directory. "
            "For local images, PDFs, or document URLs, call paddle_ocr with the provided path or URL before analyzing or answering about the content. "
            "Never claim OCR succeeded unless the paddle_ocr tool result confirms it. "
            "Never claim a file operation succeeded unless the tool result confirms it."
        )
        return base_prompt + tool_policy

    def _init_agent(self) -> None:
        load_dotenv()
        model = self._sidebar.current_model
        api_key = self._sidebar.api_key
        base_url = self._sidebar.base_url
        self._model_status.setText(model)
        self._team_page.configure(api_key=api_key, base_url=base_url, model=model)

        if not api_key:
            self._chat_page.add_system_message("欢迎使用 DeepSeek Agent Workbench。请先在左侧配置 API Key。")
            self._status_text.setText("未配置 API Key")
            return

        try:
            enabled_builtin_tools = self._plugin_store.enabled_builtin_tool_names()
            enabled_external_tools = self._plugin_store.enabled_external_tool_paths()
            self._agent = DeepSeekAgent(
                system_prompt=self._build_system_prompt(),
                model=model,
                reasoning_effort="medium",
                thinking_enabled=False,
                enable_tools=bool(enabled_builtin_tools or enabled_external_tools),
                enabled_skill_paths=self._plugin_store.enabled_skill_paths(),
                enabled_builtin_tools=enabled_builtin_tools,
                enabled_external_tool_paths=enabled_external_tools,
                enable_rag=True,
                retriever=self._retriever,
                enable_long_term_memory=True,
                memory_db_path="data/long_term_memory.db",
                max_tool_rounds=5,
            )
            self._agent.base_url = base_url
            self._agent.long_term_memory = self._long_term_memory
            self._agent.client = OpenAI(api_key=api_key, base_url=base_url)
            self._agent.tool_executor.client = self._agent.client
            self._agent.tool_executor.run_store = self._run_store
            if self._current_chat_session_id is not None:
                self._restore_agent_history(self._chat_store.messages(self._current_chat_session_id))
            self._status_text.setText(f"Connected  |  {model}")
        except Exception as e:
            self._chat_page.add_system_message(f"初始化失败：{e}")
            self._status_text.setText("初始化失败")

    def _rebuild_agent(self) -> None:
        self._plugin_store.sync_builtins()
        self._agent = None
        self._init_agent()
        self._refresh_dashboard()

    def _on_nav(self, label: str) -> None:
        pages = {"Dashboard": 0, "Chat": 1, "Model": 2, "Memory": 3, "LongMemory": 4, "Files": 5, "Knowledge": 6, "Workflows": 7, "Operations": 8, "Team": 9, "SkillsTools": 10, "Tokens": 11}
        self._stack.setCurrentIndex(pages.get(label, 0))
        if label == "Memory":
            self._memory_page.refresh()
        if label == "LongMemory":
            self._long_term_memory_page.refresh()
        self._update_tokens_page()
        self._refresh_dashboard()

    def _on_model_change(self, model: str) -> None:
        self._model_status.setText(model)
        self._model_page.set_current_model(model)
        self._team_page.configure(api_key=self._sidebar.api_key, base_url=self._sidebar.base_url, model=model)
        if self._agent:
            self._agent.model = model
            self._agent.tool_executor.model = model
            self._status_text.setText(f"Connected  |  {model}")
        self._refresh_dashboard()

    def _on_api_change(self, api_key: str, base_url: str) -> None:
        self._team_page.configure(api_key=api_key, base_url=base_url, model=self._sidebar.current_model)
        self._rebuild_agent()

    def _on_prompt_change(self, _prompt: str) -> None:
        self._rebuild_agent()
        self._status_text.setText("Prompt 已应用")

    def _on_model_page_select(self, model: str) -> None:
        self._sidebar.set_model(model)
        self._on_model_change(model)

    def _on_model_config_select(self, model: str, base_url: str, api_key: str) -> None:
        self._sidebar.set_api_config(api_key, base_url, model)
        self._model_page.set_current_model(model)
        self._status_text.setText(f"Applied model config  |  {model}")

    def _on_token_reset(self) -> None:
        self._session_input_tokens = 0
        self._session_output_tokens = 0
        self._update_tokens_page()
        self._refresh_dashboard()

    def _approval_callback(self, tool_name: str, arguments: dict, risk: str) -> bool:
        if tool_name in self._session_approvals:
            return True
        request = {"tool": tool_name, "arguments": arguments, "risk": risk, "event": threading.Event(), "allowed": False, "session": False}
        self._worker.approval_requested.emit(request)
        while not request["event"].wait(0.1):
            if self._active_run and self._active_run.cancellation.is_cancelled:
                return False
        if request.get("session"):
            self._session_approvals.add(tool_name)
        return bool(request.get("allowed"))

    def _show_approval(self, request: dict) -> None:
        arguments = request.get("arguments", {})
        summary = "\n".join(f"{key}: {value}" for key, value in arguments.items() if key.lower() not in {"token", "api_key", "password", "secret"})
        box = QMessageBox(self)
        box.setWindowTitle("工具调用审批")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(f"Agent 请求执行 `{request.get('tool')}`（风险：{request.get('risk')}）")
        box.setInformativeText(summary[:2000] or "无参数")
        once = box.addButton("允许一次", QMessageBox.ButtonRole.AcceptRole)
        session = box.addButton("本次会话允许", QMessageBox.ButtonRole.YesRole)
        box.addButton("拒绝", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        request["allowed"] = clicked in {once, session}
        request["session"] = clicked is session
        request["event"].set()

    def _cancel_active_run(self) -> None:
        if self._active_run:
            self._active_run.cancellation.cancel()
            self._status_text.setText("正在停止...")

    def _on_chat_send(self, text: str) -> None:
        if not self._agent:
            self._chat_page.add_system_message("Agent 尚未初始化，请先配置 API Key。")
            self._chat_page._reset_ui()
            return

        agent = self._agent
        model = self._sidebar.current_model
        with self._lock:
            self._request_count += 1
            req_id = self._request_count

        if self._current_chat_session_id is None:
            self._new_chat_session()
        session_id = int(self._current_chat_session_id or self._chat_store.create_session(model=model))
        run_context = RunContext(session_id=session_id, approval_callback=self._approval_callback)
        run_context.event_callback = lambda event, payload: self._run_store.add_event(run_context.run_id, event, payload)
        self._active_run = run_context
        self._run_store.create_run(run_context, model, text)
        self._restore_agent_history(self._chat_store.messages(session_id))
        self._sidebar.add_session()

        threading.Thread(
            target=self._run_query,
            args=(agent, text, req_id, model, session_id, run_context),
            daemon=True,
        ).start()

    def _run_query(self, agent: DeepSeekAgent, user_input: str, req_id: int, model: str, session_id: int, run_context: RunContext) -> None:
        try:
            self._worker.status_update.emit(f"思考中... (#{req_id})")
            accumulated = ""
            for chunk in agent.ask_stream(user_input, run_context=run_context):
                accumulated += chunk
                self._worker.stream_chunk.emit(chunk)

            usage = run_context.usage
            inp = usage.prompt_tokens
            out = usage.completion_tokens
            if usage.total_tokens == 0:
                inp = max(1, len(user_input) // 3)
                out = max(1, len(accumulated) // 3)
                usage.prompt_tokens = inp
                usage.completion_tokens = out
                usage.total_tokens = inp + out
                usage.estimated = True
            self._run_store.set_status(run_context.run_id, RunStatus.COMPLETED, output=accumulated, usage=usage)
            self._worker.tokens_updated.emit(inp, out)
            self._worker.stream_done.emit(session_id, user_input, accumulated, inp, out, model, usage.estimated)
            self._worker.status_update.emit(f"Ready  |  {model}")
        except CancelledError as exc:
            error = AgentError(ErrorCategory.CANCELLED, "cancelled", str(exc))
            self._run_store.set_status(run_context.run_id, RunStatus.CANCELLED, error=error, usage=run_context.usage)
            self._worker.stream_error.emit("任务已取消。")
        except TimeoutError as exc:
            error = AgentError(ErrorCategory.TIMEOUT, "run_timeout", str(exc), True)
            self._run_store.set_status(run_context.run_id, RunStatus.TIMED_OUT, error=error, usage=run_context.usage)
            self._worker.stream_error.emit(f"任务超时：{exc}")
        except Exception as exc:
            error = AgentError(ErrorCategory.INTERNAL, "run_failed", str(exc))
            self._run_store.set_status(run_context.run_id, RunStatus.FAILED, error=error, usage=run_context.usage)
            self._worker.stream_error.emit(f"请求失败：{exc}")
        finally:
            if self._active_run is run_context:
                self._active_run = None

    def _on_stream_done(self, session_id: int, user_input: str, full_text: str, inp: int, out: int, model: str, estimated: bool) -> None:
        if session_id:
            existing = self._chat_store.messages(session_id)
            self._chat_store.add_message(session_id, "user", user_input)
            self._chat_store.add_message(session_id, "assistant", full_text)
            if not existing:
                self._chat_store.rename_session(session_id, user_input[:36])
            self._refresh_chat_sessions()
        self._stats_store.record_exchange(
            model=model,
            user_input=user_input,
            assistant_output=full_text,
            input_tokens=inp,
            output_tokens=out,
        )
        self._daily_memory_store.refresh_day()
        self._memory_page.refresh()
        self._chat_page._on_stream_done(full_text)
        self._refresh_dashboard()

    def _on_stream_error(self, error: str) -> None:
        self._chat_page.add_system_message(error)
        self._chat_page._reset_ui()
        self._status_text.setText("请求失败")

    def _on_tokens_update(self, inp: int, out: int) -> None:
        self._session_input_tokens += inp
        self._session_output_tokens += out
        self._sidebar.add_tokens(inp, out)
        self._update_tokens_page()
        self._refresh_dashboard()

    def _update_tokens_page(self) -> None:
        stats = self._stats_store.dashboard_stats()
        _, input_tokens, output_tokens = self._stats_store.session_totals()
        self._tokens_page.update_stats(
            input_tokens,
            output_tokens,
            max(stats.sessions, 1),
            stats.activity,
        )

    def _refresh_dashboard(self) -> None:
        self._dashboard_page.update_stats(self._stats_store.dashboard_stats())
