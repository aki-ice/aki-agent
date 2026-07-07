from __future__ import annotations

import os
import threading

from dotenv import load_dotenv
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..agent import DeepSeekAgent
from ..team import TeamMember
from .theme import C, FONT_SERIF, card_style, input_style, primary_button_style, secondary_button_style, shadow


class TeamWorker(QObject):
    chunk = pyqtSignal(str)
    stage = pyqtSignal(str, str)
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)
    status = pyqtSignal(str)


class TeamPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._api_key = ""
        self._base_url = "https://api.deepseek.com"
        self._model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
        self._worker = TeamWorker()
        self._worker.chunk.connect(self._append_output)
        self._worker.stage.connect(self._update_stage)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.status.connect(self._status.setText if hasattr(self, "_status") else lambda _: None)
        self._member_rows: list[tuple[QLineEdit, QLineEdit, QTextEdit]] = []
        self._stage_labels: dict[str, QLabel] = {}
        self._build()
        self._bind_worker()

    def configure(self, *, api_key: str, base_url: str, model: str) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._model_label.setText(model)

    def _bind_worker(self) -> None:
        try:
            self._worker.status.disconnect()
        except TypeError:
            pass
        self._worker.status.connect(self._status.setText)

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

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Team Collaboration")
        title.setStyleSheet(f"background-color: {C['bg']}; border: none; color: {C['text']}; font-family: {FONT_SERIF}; font-size: 24px; font-weight: 900;")
        subtitle = QLabel("配置多个专家 Agent，以 sequential / parallel / debate 模式协作完成任务。")
        subtitle.setStyleSheet(f"background-color: {C['bg']}; border: none; color: {C['muted']}; font-size: 11px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()
        self._model_label = QLabel(self._model)
        self._model_label.setStyleSheet(f"background-color: {C['panel_soft']}; color: {C['primary']}; border: 1px solid {C['border']}; border-radius: 12px; padding: 8px 12px; font-weight: 800;")
        header.addWidget(self._model_label)
        layout.addLayout(header)

        config_card = self._card()
        config_layout = QGridLayout(config_card)
        config_layout.setContentsMargins(16, 14, 16, 14)
        config_layout.setHorizontalSpacing(12)
        config_layout.setVerticalSpacing(10)

        config_layout.addWidget(self._label("Team Name"), 0, 0)
        self._team_name = QLineEdit("dev_team")
        self._team_name.setStyleSheet(input_style())
        config_layout.addWidget(self._team_name, 0, 1)

        config_layout.addWidget(self._label("Mode"), 0, 2)
        self._mode = QComboBox()
        self._mode.addItems(["sequential", "parallel", "debate"])
        self._mode.setStyleSheet(input_style())
        config_layout.addWidget(self._mode, 0, 3)

        config_layout.addWidget(self._label("Debate Rounds"), 0, 4)
        self._rounds = QSpinBox()
        self._rounds.setRange(1, 5)
        self._rounds.setValue(2)
        self._rounds.setStyleSheet(input_style())
        config_layout.addWidget(self._rounds, 0, 5)
        layout.addWidget(config_card)

        members_card = self._card()
        members_layout = QVBoxLayout(members_card)
        members_layout.setContentsMargins(16, 14, 16, 14)
        members_layout.setSpacing(10)
        members_title = QLabel("Team Members")
        members_title.setStyleSheet(f"background-color: {C['panel']}; border: none; color: {C['text']}; font-size: 15px; font-weight: 900;")
        members_layout.addWidget(members_title)

        self._members_layout = QVBoxLayout()
        self._members_layout.setSpacing(10)
        members_layout.addLayout(self._members_layout)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("添加成员")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(lambda: self._add_member("member", "specialist", "你是一个专业助手，请从你的角色角度完成任务。"))
        add_btn.setStyleSheet(secondary_button_style())
        btn_row.addWidget(add_btn)
        btn_row.addStretch()
        members_layout.addLayout(btn_row)
        layout.addWidget(members_card)

        self._add_member("researcher", "researcher", "你是需求分析和研究专家，负责分析背景、目标、约束、风险和事实依据。")
        self._add_member("coder", "coder", "你是资深 Python 工程师，负责给出实现方案、代码结构、边界情况和工程实践。")
        self._add_member("reviewer", "reviewer", "你是代码审查专家，负责发现漏洞、风险、可维护性问题并提出改进建议。")

        task_card = self._card()
        task_layout = QVBoxLayout(task_card)
        task_layout.setContentsMargins(16, 14, 16, 14)
        task_layout.setSpacing(10)
        task_layout.addWidget(self._label("Task"))
        self._task = QTextEdit()
        self._task.setPlaceholderText("输入希望团队协作完成的任务，例如：设计一个插件市场功能，并给出实现方案。")
        self._task.setMinimumHeight(110)
        self._task.setStyleSheet(input_style())
        task_layout.addWidget(self._task)

        run_row = QHBoxLayout()
        self._run_btn = QPushButton("运行团队协作")
        self._run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._run_btn.clicked.connect(self._run_team)
        self._run_btn.setStyleSheet(primary_button_style())
        run_row.addWidget(self._run_btn)
        clear_btn = QPushButton("清空结果")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(lambda: self._output.clear())
        clear_btn.setStyleSheet(secondary_button_style())
        run_row.addWidget(clear_btn)
        run_row.addStretch()
        task_layout.addLayout(run_row)
        layout.addWidget(task_card)

        workflow_card = self._card()
        workflow_layout = QVBoxLayout(workflow_card)
        workflow_layout.setContentsMargins(16, 14, 16, 14)
        workflow_layout.setSpacing(10)
        workflow_layout.addWidget(self._label("Workflow"))
        self._workflow_layout = QHBoxLayout()
        self._workflow_layout.setSpacing(8)
        workflow_layout.addLayout(self._workflow_layout)
        layout.addWidget(workflow_card)

        result_card = self._card()
        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(16, 14, 16, 14)
        result_layout.setSpacing(10)
        result_header = QHBoxLayout()
        result_header.addWidget(self._label("Result"))
        result_header.addStretch()
        self._status = QLabel("Ready")
        self._status.setStyleSheet(f"background-color: {C['panel']}; border: none; color: {C['success']}; font-size: 11px; font-weight: 800;")
        result_header.addWidget(self._status)
        result_layout.addLayout(result_header)
        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setMinimumHeight(260)
        self._output.setStyleSheet(input_style())
        result_layout.addWidget(self._output)
        layout.addWidget(result_card)

        layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll)

    def _add_member(self, name: str, role: str, prompt: str) -> None:
        row_card = QFrame()
        row_card.setObjectName("Card")
        row_card.setStyleSheet(card_style(radius=14, bg=C["panel_soft"]))
        row = QVBoxLayout(row_card)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(8)

        top = QHBoxLayout()
        name_input = QLineEdit(name)
        name_input.setStyleSheet(input_style())
        role_input = QLineEdit(role)
        role_input.setStyleSheet(input_style())
        top.addWidget(self._label("Name"))
        top.addWidget(name_input, 1)
        top.addWidget(self._label("Role"))
        top.addWidget(role_input, 1)
        remove_btn = QPushButton("删除")
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.setStyleSheet(secondary_button_style(9))
        top.addWidget(remove_btn)
        row.addLayout(top)

        prompt_input = QTextEdit(prompt)
        prompt_input.setMinimumHeight(70)
        prompt_input.setStyleSheet(input_style())
        row.addWidget(prompt_input)
        remove_btn.clicked.connect(lambda: self._remove_member(row_card, name_input, role_input, prompt_input))

        self._member_rows.append((name_input, role_input, prompt_input))
        self._members_layout.addWidget(row_card)

    def _remove_member(self, widget: QWidget, name_input: QLineEdit, role_input: QLineEdit, prompt_input: QTextEdit) -> None:
        if len(self._member_rows) <= 1:
            QMessageBox.information(self, "提示", "至少需要保留一个团队成员。")
            return
        self._member_rows = [row for row in self._member_rows if row != (name_input, role_input, prompt_input)]
        widget.deleteLater()

    def _collect_members(self) -> list[TeamMember]:
        members: list[TeamMember] = []
        for name_input, role_input, prompt_input in self._member_rows:
            name = name_input.text().strip()
            role = role_input.text().strip()
            prompt = prompt_input.toPlainText().strip()
            if name and role and prompt:
                members.append(TeamMember(name=name, role=role, system_prompt=prompt, model=self._model))
        return members

    def _build_workflow(self, members: list[TeamMember]) -> None:
        while self._workflow_layout.count():
            item = self._workflow_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._stage_labels = {}
        stages = [member.name for member in members] + ["Leader"]
        for index, name in enumerate(stages):
            label = QLabel(f"{name}\nPending")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setMinimumHeight(56)
            label.setStyleSheet(self._stage_style("pending"))
            self._stage_labels[name] = label
            self._workflow_layout.addWidget(label, 1)
            if index < len(stages) - 1:
                arrow = QLabel("→")
                arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                arrow.setStyleSheet(f"background: transparent; border: none; color: {C['muted']}; font-size: 18px; font-weight: 900;")
                self._workflow_layout.addWidget(arrow)

    def _update_stage(self, name: str, state: str) -> None:
        label = self._stage_labels.get(name)
        if not label:
            return
        display = {"pending": "Pending", "running": "Running", "done": "Done", "failed": "Failed"}.get(state, state)
        label.setText(f"{name}\n{display}")
        label.setStyleSheet(self._stage_style(state))

    def _stage_style(self, state: str) -> str:
        color = {
            "pending": C["muted"],
            "running": C["warning"],
            "done": C["success"],
            "failed": C["danger"],
        }.get(state, C["muted"])
        return f"background-color: {C['panel_soft']}; color: {color}; border: 1px solid {color}; border-radius: 14px; padding: 8px; font-size: 11px; font-weight: 900;"

    def _run_team(self) -> None:
        task = self._task.toPlainText().strip()
        if not task:
            QMessageBox.warning(self, "提示", "请先输入团队任务。")
            return
        if not self._api_key:
            QMessageBox.warning(self, "提示", "请先在左侧配置 API Key 并应用。")
            return
        members = self._collect_members()
        if not members:
            QMessageBox.warning(self, "提示", "请至少配置一个团队成员。")
            return
        self._run_btn.setEnabled(False)
        self._status.setText("Running...")
        self._build_workflow(members)
        self._output.clear()
        self._append_output("团队协作开始，成员结果会逐步输出...\n\n")
        team_name = self._team_name.text().strip() or "agent_team"
        mode = self._mode.currentText()
        rounds = int(self._rounds.value())
        threading.Thread(target=self._run_team_thread, args=(task, members, team_name, mode, rounds), daemon=True).start()

    def _run_team_thread(self, task: str, members: list[TeamMember], team_name: str, mode: str, rounds: int) -> None:
        try:
            self._worker.status.emit("Preparing team...")
            load_dotenv()
            os.environ["DEEPSEEK_API_KEY"] = self._api_key
            os.environ["DEEPSEEK_BASE_URL"] = self._base_url
            os.environ["DEEPSEEK_MODEL"] = self._model
            if mode == "parallel":
                result = self._run_parallel(task, members, team_name)
            elif mode == "debate":
                result = self._run_debate(task, members, team_name, rounds)
            else:
                result = self._run_sequential(task, members, team_name)
            self._worker.finished.emit(result)
        except Exception as exc:
            self._worker.failed.emit(str(exc))

    def _run_sequential(self, task: str, members: list[TeamMember], team_name: str) -> str:
        results: list[str] = []
        carry = task
        for index, member in enumerate(members, 1):
            prompt = task if index == 1 else f"Previous output:\n{carry}\n\nOriginal task: {task}\n\nBuild upon or refine the previous output. Improve it."
            result = self._stream_agent(member.system_prompt, prompt, f"[{index}/{len(members)}] {member.name}")
            results.append(f"[{member.name}] {result}")
            carry = result
        return self._stream_leader(team_name, members, task, results, "Synthesize the sequential team results into a final answer.")

    def _run_parallel(self, task: str, members: list[TeamMember], team_name: str) -> str:
        results: list[str] = []
        for index, member in enumerate(members, 1):
            result = self._stream_agent(member.system_prompt, task, f"[{index}/{len(members)}] {member.name}")
            results.append(f"[{member.name}] {result}")
        return self._stream_leader(team_name, members, task, results, "Synthesize these independent analyses into a comprehensive final answer.")

    def _run_debate(self, task: str, members: list[TeamMember], team_name: str, rounds: int) -> str:
        history: list[str] = []
        for round_index in range(1, rounds + 1):
            for member in members:
                if not history:
                    prompt = f"Debate topic: {task}\n\nYou are the opening speaker. Present your initial position clearly."
                else:
                    prompt = f"Debate topic: {task}\n\nDebate so far:\n" + "\n".join(history) + "\n\nRespond to the previous arguments. Be concise and substantive."
                result = self._stream_agent(member.system_prompt, prompt, f"Round {round_index} · {member.name}")
                entry = f"[Round {round_index}] {member.name}: {result}"
                history.append(entry)
        return self._stream_leader(team_name, members, task, history, "You moderated this debate. Provide a final verdict synthesizing the best arguments.")

    def _stream_agent(self, system_prompt: str, prompt: str, title: str) -> str:
        stage_name = "Leader" if title == "Leader synthesis" else title.split("] ", 1)[-1].split("·")[-1].strip()
        self._worker.stage.emit(stage_name, "running")
        self._worker.status.emit(f"Running {title}...")
        self._worker.chunk.emit(f"\n## {title}\n")
        agent = DeepSeekAgent(system_prompt=system_prompt, model=self._model, enable_tools=False, enable_rag=False, enable_long_term_memory=False)
        agent.reasoning_effort = "medium"
        chunks: list[str] = []
        for chunk in agent.ask_stream(prompt):
            chunks.append(chunk)
            self._worker.chunk.emit(chunk)
        self._worker.chunk.emit("\n")
        self._worker.stage.emit(stage_name, "done")
        return "".join(chunks)

    def _stream_leader(self, team_name: str, members: list[TeamMember], task: str, results: list[str], instruction: str) -> str:
        member_names = ", ".join(member.name for member in members)
        prompt = instruction + "\n\n" + "\n\n---\n\n".join(results) + f"\n\nOriginal task: {task}"
        system_prompt = (
            f"You are the leader of team '{team_name}'. Your team members are: {member_names}. "
            "Synthesize their outputs into a clear, comprehensive final answer. "
            "Resolve conflicts, fill gaps, and make the final output actionable."
        )
        return self._stream_agent(system_prompt, prompt, "Leader synthesis")

    def _append_output(self, text: str) -> None:
        self._output.moveCursor(QTextCursor.MoveOperation.End)
        self._output.insertPlainText(text)
        self._output.moveCursor(QTextCursor.MoveOperation.End)

    def _on_finished(self, result: str) -> None:
        self._run_btn.setEnabled(True)
        self._status.setText("Done")
        if result and result not in self._output.toPlainText():
            self._append_output(f"\n\n## Final Result\n{result}")

    def _on_failed(self, error: str) -> None:
        self._run_btn.setEnabled(True)
        self._status.setText("Failed")
        self._append_output(f"\n\n团队协作失败：{error}")

    def _card(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Card")
        frame.setStyleSheet(card_style(radius=18))
        frame.setGraphicsEffect(shadow(18, 28, 4))
        return frame

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"background: transparent; border: none; color: {C['muted']}; font-size: 10px; font-weight: 900;")
        return label
