from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


class FileWorkbench:
    def __init__(self, workspace_root: str = ".") -> None:
        self.workspace_root = Path(workspace_root).resolve()

    def resolve(self, path: str) -> Path:
        target = Path(path)
        if not target.is_absolute():
            target = self.workspace_root / target
        target = target.resolve()
        if os.path.commonpath([str(self.workspace_root), str(target)]) != str(self.workspace_root):
            raise PermissionError("路径必须位于工作区内")
        return target

    def list_directory(self, path: str = ".") -> list[dict[str, object]]:
        directory = self.resolve(path)
        return [{"name": item.name, "path": str(item), "directory": item.is_dir(), "size": item.stat().st_size if item.is_file() else 0, "modified": item.stat().st_mtime} for item in sorted(directory.iterdir(), key=lambda value: (not value.is_dir(), value.name.lower()))]

    def preview(self, path: str, max_chars: int = 100_000) -> str:
        target = self.resolve(path)
        if target.suffix.lower() not in {".txt", ".md", ".markdown", ".csv", ".json", ".yaml", ".yml", ".py", ".js", ".ts", ".toml"}:
            return "该文件类型需要文档解析器或 OCR 预览。"
        return target.read_text(encoding="utf-8", errors="replace")[:max_chars]

    def reveal(self, path: str) -> None:
        target = self.resolve(path)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(target)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target.parent)])

    def open_default(self, path: str) -> None:
        target = self.resolve(path)
        if sys.platform == "win32":
            os.startfile(str(target))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])

    def copy_path(self, path: str, target: str) -> str:
        source = self.resolve(path)
        destination = self.resolve(target)
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=False)
        else:
            shutil.copy2(source, destination)
        return str(destination)
