from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from .plugin_store import PluginInfo, PluginStore


@dataclass(frozen=True)
class ImportResult:
    plugin: PluginInfo
    message: str


class PluginImportError(RuntimeError):
    pass


class PluginImporter:
    MAX_ZIP_SIZE = 10 * 1024 * 1024
    MAX_FILES = 100
    SKILL_EXTENSIONS = {".json", ".yaml", ".yml", ".md", ".txt"}
    TOOL_EXTENSIONS = {".py", ".json", ".yaml", ".yml", ".md", ".txt"}

    def __init__(self, store: PluginStore, plugins_root: str | Path = "data/plugins") -> None:
        self.store = store
        self.plugins_root = Path(plugins_root)
        self.plugins_root.mkdir(parents=True, exist_ok=True)

    def import_zip(self, zip_path: str | Path) -> ImportResult:
        zip_path = Path(zip_path)
        if not zip_path.exists():
            raise PluginImportError("ZIP 文件不存在。")
        if zip_path.stat().st_size > self.MAX_ZIP_SIZE:
            raise PluginImportError("ZIP 文件过大，最大支持 10MB。")

        with zipfile.ZipFile(zip_path) as zf:
            infos = [info for info in zf.infolist() if not info.is_dir()]
            if len(infos) > self.MAX_FILES:
                raise PluginImportError("ZIP 内文件数量过多，最大支持 100 个文件。")
            self._validate_paths(infos)
            manifest_name = self._find_manifest(infos)
            manifest = self._read_manifest(zf, manifest_name)
            plugin_type = self._validate_manifest(manifest)
            self._validate_extensions(infos, plugin_type)
            entry_name = self._resolve_entry_name(infos, manifest_name, str(manifest["entry"]))

            plugin_id = self._safe_id(str(manifest["id"]))
            target_dir = self.plugins_root / ("skills" if plugin_type == "skill" else "tools") / plugin_id
            if target_dir.exists():
                shutil.rmtree(target_dir)
            target_dir.mkdir(parents=True, exist_ok=True)
            self._extract_safe(zf, infos, target_dir)

        entry_path = target_dir / PurePosixPath(entry_name).name
        if not entry_path.exists():
            nested_entry = next(target_dir.rglob(PurePosixPath(entry_name).name), None)
            if nested_entry:
                entry_path = nested_entry
        if not entry_path.exists():
            raise PluginImportError("导入后未找到入口文件。")
        if plugin_type == "tool":
            self._validate_tool_entry(entry_path)

        trusted = plugin_type == "skill"
        enabled = plugin_type == "skill"
        plugin = PluginInfo(
            id=f"{plugin_type}.{plugin_id}",
            type=plugin_type,
            name=str(manifest["name"]),
            version=str(manifest.get("version", "1.0.0")),
            description=str(manifest.get("description", "")),
            source="imported",
            entry_path=str(entry_path.resolve()),
            enabled=enabled,
            trusted=trusted,
            installed_at=datetime.now().isoformat(timespec="seconds"),
        )
        self.store.upsert_plugin(plugin)

        if plugin_type == "tool":
            return ImportResult(plugin, "Tool 已导入。请在 Tools 页面查看详情、确认信任后再启用执行。")
        return ImportResult(plugin, "Skill 已导入并启用。")

    def _validate_paths(self, infos: list[zipfile.ZipInfo]) -> None:
        for info in infos:
            name = info.filename.replace("\\", "/")
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts:
                raise PluginImportError(f"ZIP 包含不安全路径：{info.filename}")

    def _find_manifest(self, infos: list[zipfile.ZipInfo]) -> str:
        manifests = [info.filename for info in infos if PurePosixPath(info.filename).name == "manifest.json"]
        if not manifests:
            raise PluginImportError("ZIP 中缺少 manifest.json。")
        return manifests[0]

    def _read_manifest(self, zf: zipfile.ZipFile, name: str) -> dict[str, Any]:
        try:
            return json.loads(zf.read(name).decode("utf-8"))
        except Exception as exc:
            raise PluginImportError(f"manifest.json 无法解析：{exc}") from exc

    def _validate_manifest(self, manifest: dict[str, Any]) -> str:
        required = ["id", "type", "name", "entry"]
        missing = [key for key in required if not manifest.get(key)]
        if missing:
            raise PluginImportError(f"manifest.json 缺少字段：{', '.join(missing)}")
        plugin_type = str(manifest["type"]).lower()
        if plugin_type not in {"skill", "tool"}:
            raise PluginImportError("manifest.type 只能是 skill 或 tool。")
        self._safe_id(str(manifest["id"]))
        return plugin_type

    def _validate_extensions(self, infos: list[zipfile.ZipInfo], plugin_type: str) -> None:
        allowed = self.SKILL_EXTENSIONS if plugin_type == "skill" else self.TOOL_EXTENSIONS
        for info in infos:
            suffix = PurePosixPath(info.filename).suffix.lower()
            if suffix and suffix not in allowed:
                raise PluginImportError(f"不允许的文件类型：{info.filename}")

    def _resolve_entry_name(self, infos: list[zipfile.ZipInfo], manifest_name: str, entry: str) -> str:
        manifest_dir = str(PurePosixPath(manifest_name).parent)
        candidates = [entry]
        if manifest_dir != ".":
            candidates.append(str(PurePosixPath(manifest_dir) / entry))
        names = {info.filename.replace("\\", "/") for info in infos}
        for candidate in candidates:
            if candidate.replace("\\", "/") in names:
                return candidate.replace("\\", "/")
        raise PluginImportError(f"入口文件不存在：{entry}")

    def _extract_safe(self, zf: zipfile.ZipFile, infos: list[zipfile.ZipInfo], target_dir: Path) -> None:
        target_root = target_dir.resolve()
        for info in infos:
            relative = PurePosixPath(info.filename.replace("\\", "/"))
            parts = relative.parts
            if len(parts) > 1:
                relative = PurePosixPath(*parts[1:])
            destination = (target_dir / Path(*relative.parts)).resolve()
            if not str(destination).startswith(str(target_root)):
                raise PluginImportError(f"ZIP 包含不安全解压路径：{info.filename}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, destination.open("wb") as dst:
                shutil.copyfileobj(src, dst)

    def _validate_tool_entry(self, entry_path: Path) -> None:
        if entry_path.suffix.lower() != ".py":
            raise PluginImportError("外部 Tool 入口文件必须是 .py 文件。")
        text = entry_path.read_text(encoding="utf-8", errors="replace")
        if "class Tool" not in text and "def create_tool" not in text:
            raise PluginImportError("外部 Tool 必须定义 Tool 类或 create_tool() 函数。")

    def _safe_id(self, value: str) -> str:
        clean = value.strip().replace(" ", "_")
        if not clean or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for ch in clean):
            raise PluginImportError("插件 id 只能包含字母、数字、下划线和连字符。")
        return clean
