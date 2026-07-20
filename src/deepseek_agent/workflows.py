from __future__ import annotations

import csv
import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .rag.loader import parse_document


@dataclass(frozen=True)
class WorkflowResult:
    workflow: str
    title: str
    sections: dict[str, Any]
    sources: list[dict[str, Any]] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [f"# {self.title}", "", f"工作流：{self.workflow}", ""]
        for name, value in self.sections.items():
            lines.append(f"## {name}")
            lines.append(str(value))
            lines.append("")
        if self.sources:
            lines.extend(["## 来源", *[f"- {source}" for source in self.sources]])
        return "\n".join(lines)

    def save(self, path: str) -> None:
        target = Path(path)
        if target.suffix.lower() == ".json":
            target.write_text(json.dumps({"workflow": self.workflow, "title": self.title, "sections": self.sections, "sources": self.sources}, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            target.write_text(self.to_markdown(), encoding="utf-8")


class DocumentWorkflowService:
    def run(self, workflow: str, path: str) -> WorkflowResult:
        parsed = parse_document(path)
        text = "\n".join(document.content for document in parsed.documents)
        sources = [{"source": path, "page": document.page, "metadata": document.metadata} for document in parsed.documents]
        if workflow == "contract_review":
            return WorkflowResult(workflow, "合同审查结果", self._contract(text), sources)
        if workflow == "report_summary":
            return WorkflowResult(workflow, "报告总结", self._report(text), sources)
        if workflow == "paper_reading":
            return WorkflowResult(workflow, "论文阅读笔记", self._paper(text), sources)
        if workflow == "spreadsheet_insight":
            return WorkflowResult(workflow, "表格洞察", self._spreadsheet(path), sources)
        raise ValueError(f"未知工作流: {workflow}")

    @staticmethod
    def _contract(text: str) -> dict[str, str]:
        markers = ["主体", "金额", "日期", "义务", "违约", "争议解决", "风险"]
        return {marker: "\n".join(line for line in text.splitlines() if marker in line) or "未在原文中定位到，请人工核对。" for marker in markers}

    @staticmethod
    def _report(text: str) -> dict[str, str]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return {"执行摘要": " ".join(lines[:5]), "关键指标": "\n".join(line for line in lines if any(char.isdigit() for char in line)) or "未检测到数字指标。", "风险": "请结合来源和业务口径复核。", "行动项": "根据摘要和风险清单生成后续任务。"}

    @staticmethod
    def _paper(text: str) -> dict[str, str]:
        sections = {name: "\n".join(line for line in text.splitlines() if keyword in line) for name, keyword in [("摘要", "摘要"), ("方法", "方法"), ("实验", "实验"), ("结论", "结论"), ("限制", "限制") ]}
        sections["术语"] = "；".join(sorted(set(text.split())))[:2000]
        return sections

    @staticmethod
    def _spreadsheet(path: str) -> dict[str, Any]:
        parsed = parse_document(path)
        values = [document.content for document in parsed.documents]
        return {"工作表": [document.metadata.get("sheet", document.title) for document in parsed.documents], "行数": len(values), "缺失值": sum(not value.strip() for value in values), "统计摘要": "已提取表格文本，可进一步生成图表。"}
