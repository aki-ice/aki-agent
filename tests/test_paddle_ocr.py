from __future__ import annotations

import json

import pytest

from deepseek_agent.runtime import CancellationToken
from deepseek_agent.tools.builtin import PaddleOcrTool


class Response:
    def __init__(self, data=None, text="", status=200):
        self._data = data or {}
        self.text = text
        self.status_code = status
        self.ok = status == 200

    def json(self):
        return self._data

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(self.status_code)


def test_paddle_ocr_job_done(monkeypatch, tmp_path):
    monkeypatch.setenv("PADDLEOCR_API_TOKEN", "test-token")
    monkeypatch.setattr("requests.post", lambda *a, **k: Response({"data": {"jobId": "job-1"}}))
    monkeypatch.setattr(
        "requests.get",
        lambda url, **k: Response({"data": {"state": "done", "extractProgress": {"extractedPages": 1, "totalPages": 1}, "resultUrl": {"jsonUrl": "result"}}})
        if "job-1" in url
        else Response(text=json.dumps({"result": {"layoutParsingResults": [{"markdown": {"text": "hello", "images": {}}, "outputImages": {}}]}})),
    )
    source = tmp_path / "doc.pdf"
    source.write_bytes(b"pdf")
    result = PaddleOcrTool(str(tmp_path)).execute(path=str(source), timeout=30)
    assert "hello" in result


def test_paddle_ocr_cancellation(monkeypatch, tmp_path):
    monkeypatch.setenv("PADDLEOCR_API_TOKEN", "test-token")
    monkeypatch.setattr("requests.post", lambda *a, **k: Response({"data": {"jobId": "job-1"}}))
    monkeypatch.setattr("requests.get", lambda *a, **k: Response({"data": {"state": "pending"}}))
    source = tmp_path / "doc.pdf"
    source.write_bytes(b"pdf")
    token = CancellationToken()
    token.cancel()
    result = PaddleOcrTool(str(tmp_path)).execute(path=str(source), timeout=30, _cancellation_token=token)
    assert "cancelled" in result.lower()
