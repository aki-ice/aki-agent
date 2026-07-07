from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from .base import BaseTool


class ExternalToolLoadError(RuntimeError):
    pass


def load_external_tool(path: str | Path) -> BaseTool:
    path = Path(path)
    if not path.exists():
        raise ExternalToolLoadError(f"Tool entry file not found: {path}")
    if path.suffix.lower() != ".py":
        raise ExternalToolLoadError("External tool entry must be a .py file.")

    module = _load_module(path)
    tool = _create_tool(module)
    if not isinstance(tool, BaseTool):
        raise ExternalToolLoadError("External tool must return an instance of BaseTool.")
    return tool


def _load_module(path: Path) -> ModuleType:
    module_name = f"deepseek_external_tool_{path.parent.name}_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ExternalToolLoadError(f"Cannot load module from {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    plugin_dir = str(path.parent.resolve())
    inserted = False
    if plugin_dir not in sys.path:
        sys.path.insert(0, plugin_dir)
        inserted = True
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise ExternalToolLoadError(f"Failed to import external tool: {exc}") from exc
    finally:
        if inserted:
            try:
                sys.path.remove(plugin_dir)
            except ValueError:
                pass
    return module


def _create_tool(module: ModuleType) -> BaseTool:
    if hasattr(module, "create_tool"):
        try:
            return module.create_tool()
        except Exception as exc:
            raise ExternalToolLoadError(f"create_tool() failed: {exc}") from exc

    tool_class = getattr(module, "Tool", None)
    if tool_class is None:
        raise ExternalToolLoadError("External tool must define Tool class or create_tool() function.")

    try:
        return tool_class()
    except Exception as exc:
        raise ExternalToolLoadError(f"Tool() initialization failed: {exc}") from exc
