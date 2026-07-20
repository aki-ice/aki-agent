from __future__ import annotations

from deepseek_agent.file_workbench import FileWorkbench
from deepseek_agent.rag.loader import parse_document
from deepseek_agent.search import NgramIndex
from deepseek_agent.workflows import DocumentWorkflowService


def test_chinese_ngram_search():
    index = NgramIndex()
    index.add("a", "中文桌面文档工作流")
    index.add("b", "英文 terminal")
    assert index.search("中文文档")
    assert index.search("中文文档")[0].source == "a"


def test_text_parser_metadata(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("主体：甲方\n金额：100", encoding="utf-8")
    result = parse_document(str(path))
    assert result.parser == "text"
    assert result.documents[0].metadata == {}


def test_file_workbench_preview(tmp_path):
    path = tmp_path / "a.md"
    path.write_text("# 标题", encoding="utf-8")
    workbench = FileWorkbench(str(tmp_path))
    assert "标题" in workbench.preview("a.md")
    assert workbench.list_directory()[0]["name"] == "a.md"


def test_contract_workflow(tmp_path):
    path = tmp_path / "contract.txt"
    path.write_text("主体：甲方与乙方\n金额：100万元\n违约：按合同约定", encoding="utf-8")
    result = DocumentWorkflowService().run("contract_review", str(path))
    assert "甲方" in result.sections["主体"]
    assert "违约" in result.to_markdown()
