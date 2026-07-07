from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
from typing import Any

from .base import BaseTool, ToolDefinition, ToolParameter, ToolRegistry


class CalculatorTool(BaseTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="calculator",
            description="Evaluate a mathematical expression. Supports + - * / ** and common math functions.",
            parameters=[
                ToolParameter("expression", "string", "Math expression, e.g. '2 + 3 * 4'"),
            ],
        )

    def execute(self, expression: str = "", **_: Any) -> str:
        allowed = {
            "abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "pow": pow, "int": int, "float": float,
        }
        try:
            import math
            allowed.update({k: getattr(math, k) for k in ["sqrt", "sin", "cos", "pi", "log", "log10"]})
        except ImportError:
            pass
        try:
            result = eval(expression, {"__builtins__": {}}, allowed)
            return str(result)
        except Exception as exc:
            return f"Calculation error: {exc}"


class DateTimeTool(BaseTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="datetime",
            description="Get the current date and time, or compute a relative date.",
            parameters=[
                ToolParameter("action", "string", "Action: 'now', 'today', or 'offset'",
                              enum=["now", "today", "offset"]),
                ToolParameter("days", "integer", "Days offset. Used with 'offset'.", required=False),
            ],
        )

    def execute(self, action: str = "now", days: int = 0, **_: Any) -> str:
        now = dt.datetime.now()
        if action == "today":
            return now.strftime("%Y-%m-%d")
        if action == "offset":
            target = now + dt.timedelta(days=days)
            return target.strftime("%Y-%m-%d %H:%M:%S")
        return now.strftime("%Y-%m-%d %H:%M:%S")


class FileToolMixin:
    def __init__(self, workspace_root: str = ".") -> None:
        self.workspace_root = os.path.abspath(workspace_root)

    def _resolve_path(self, path: str) -> str:
        if os.path.isabs(path):
            return os.path.abspath(path)
        return os.path.abspath(os.path.join(self.workspace_root, path))


class ReadFileTool(BaseTool):
    def __init__(self, workspace_root: str = ".") -> None:
        self.workspace_root = os.path.abspath(workspace_root)

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="read_file",
            description="Read the contents of any text file. Supports both relative paths (resolved from workspace) and absolute paths (e.g. D:\\path\\to\\file.txt).",
            parameters=[
                ToolParameter("path", "string", "File path. Can be relative (e.g. 'src/main.py') or absolute (e.g. 'D:\\data\\doc.txt')."),
                ToolParameter("max_lines", "integer", "Maximum lines to return (default 200).", required=False),
            ],
        )

    def execute(self, path: str = "", max_lines: int = 200, **_: Any) -> str:
        # Resolve path: absolute paths used as-is; relative paths resolved from workspace
        if os.path.isabs(path):
            full = os.path.abspath(path)
        else:
            full = os.path.abspath(os.path.join(self.workspace_root, path))
        try:
            lines: list[str] = []
            with open(full, encoding="utf-8", errors="replace") as fh:
                for index, line in enumerate(fh):
                    if index >= max_lines:
                        break
                    lines.append(line)
            return "".join(lines)
        except FileNotFoundError:
            return f"File not found: {path}"
        except PermissionError:
            return f"Permission denied: {path}"
        except Exception as exc:
            return f"Read error: {exc}"



class ListDirectoryTool(BaseTool):
    def __init__(self, workspace_root: str = ".") -> None:
        self.workspace_root = os.path.abspath(workspace_root)

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="list_directory",
            description="List files and subdirectories in a directory. Supports absolute paths and relative paths (resolved from workspace).",
            parameters=[
                ToolParameter("path", "string", "Directory path. Can be relative (e.g. 'src') or absolute (e.g. 'D:\\data'). Use '.' for current workspace root."),
                ToolParameter("recursive", "boolean", "Whether to list recursively (default false).", required=False),
                ToolParameter("max_items", "integer", "Maximum items to return (default 100).", required=False),
            ],
        )

    def execute(self, path: str = ".", recursive: bool = False, max_items: int = 100, **_: Any) -> str:
        if os.path.isabs(path):
            full = os.path.abspath(path)
        else:
            full = os.path.abspath(os.path.join(self.workspace_root, path))

        if not os.path.isdir(full):
            return f"Not a directory: {path}"

        try:
            lines: list[str] = []
            count = 0
            for root, dirs, files in os.walk(full):
                level = root.replace(full, "").count(os.sep)
                indent = "  " * level
                folder_name = os.path.basename(root) or root
                lines.append(f"{indent}{folder_name}/")
                for name in sorted(dirs + files):
                    if count >= max_items:
                        break
                    full_child = os.path.join(root, name)
                    marker = "/" if os.path.isdir(full_child) else ""
                    lines.append(f"{indent}  {name}{marker}")
                    count += 1
                if not recursive:
                    break
                if count >= max_items:
                    break
            if count >= max_items:
                lines.append(f"... (truncated, showing first {max_items} items)")
            return "\n".join(lines)
        except PermissionError:
            return f"Permission denied: {path}"
        except Exception as exc:
            return f"List error: {exc}"


class WriteFileTool(FileToolMixin, BaseTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="write_file",
            description="Create or write a text file. Supports relative paths resolved from workspace and absolute paths. Can append or overwrite.",
            parameters=[
                ToolParameter("path", "string", "Target file path."),
                ToolParameter("content", "string", "Text content to write."),
                ToolParameter("append", "boolean", "Append instead of overwrite (default false).", required=False),
                ToolParameter("create_dirs", "boolean", "Create parent directories if needed (default true).", required=False),
            ],
        )

    def execute(self, path: str = "", content: str = "", append: bool = False, create_dirs: bool = True, **_: Any) -> str:
        if not path:
            return "Error: path is required"
        full = self._resolve_path(path)
        try:
            parent = os.path.dirname(full)
            if create_dirs and parent:
                os.makedirs(parent, exist_ok=True)
            mode = "a" if append else "w"
            with open(full, mode, encoding="utf-8", errors="replace") as fh:
                fh.write(content)
            action = "Appended to" if append else "Wrote"
            return f"{action} file: {full} ({len(content)} chars)"
        except Exception as exc:
            return f"Write error: {exc}"


class EditFileTool(FileToolMixin, BaseTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="edit_file",
            description="Edit an existing text file by replacing text, inserting text, deleting text, appending/prepending, or replacing a line range.",
            parameters=[
                ToolParameter("path", "string", "Target file path."),
                ToolParameter("operation", "string", "Edit operation.", enum=["replace", "insert_before", "insert_after", "delete_text", "append", "prepend", "replace_range"]),
                ToolParameter("old_text", "string", "Text to find for replace/insert/delete operations.", required=False),
                ToolParameter("new_text", "string", "Replacement or inserted text.", required=False),
                ToolParameter("start_line", "integer", "1-based start line for replace_range.", required=False),
                ToolParameter("end_line", "integer", "1-based end line for replace_range.", required=False),
                ToolParameter("replace_all", "boolean", "Replace or delete all occurrences instead of only the first (default false).", required=False),
                ToolParameter("create_backup", "boolean", "Create a .bak backup before editing (default true).", required=False),
            ],
        )

    def execute(
        self,
        path: str = "",
        operation: str = "replace",
        old_text: str = "",
        new_text: str = "",
        start_line: int = 0,
        end_line: int = 0,
        replace_all: bool = False,
        create_backup: bool = True,
        **kwargs: Any,
    ) -> str:
        if not path:
            return "Error: path is required"
        if "content" in kwargs and not new_text:
            new_text = str(kwargs.get("content") or "")
        if "text" in kwargs and not new_text:
            new_text = str(kwargs.get("text") or "")
        full = self._resolve_path(path)
        if not os.path.isfile(full):
            return f"File not found: {path}"
        try:
            with open(full, encoding="utf-8", errors="replace") as fh:
                original = fh.read()
            edited = self._apply_edit(original, operation, old_text, new_text, start_line, end_line, replace_all)
            if edited == original:
                return "No changes made. Check operation, old_text, or line range."
            if create_backup:
                shutil.copy2(full, f"{full}.bak")
            with open(full, "w", encoding="utf-8", errors="replace") as fh:
                fh.write(edited)
            return f"Edited file: {full} ({len(original)} -> {len(edited)} chars)"
        except Exception as exc:
            return f"Edit error: {exc}"

    def _apply_edit(self, original: str, operation: str, old_text: str, new_text: str, start_line: int, end_line: int, replace_all: bool) -> str:
        op = operation.strip().lower()
        op_aliases = {
            "replace_text": "replace",
            "substitute": "replace",
            "insert": "insert_after",
            "add_after": "insert_after",
            "add_before": "insert_before",
            "delete": "delete_text",
            "remove": "delete_text",
            "remove_text": "delete_text",
            "add_end": "append",
            "append_text": "append",
            "add_start": "prepend",
            "prepend_text": "prepend",
            "replace_lines": "replace_range",
            "replace_line_range": "replace_range",
        }
        op = op_aliases.get(op, op)
        if op == "replace":
            if not old_text:
                return original
            count = -1 if replace_all else 1
            return original.replace(old_text, new_text, count)
        if op == "insert_before":
            if not old_text or old_text not in original:
                return original
            return original.replace(old_text, new_text + old_text, 1)
        if op == "insert_after":
            if not old_text or old_text not in original:
                return original
            return original.replace(old_text, old_text + new_text, 1)
        if op == "delete_text":
            if not old_text:
                return original
            count = -1 if replace_all else 1
            return original.replace(old_text, "", count)
        if op == "append":
            return original + new_text
        if op == "prepend":
            return new_text + original
        if op == "replace_range":
            lines = original.splitlines(keepends=True)
            if start_line < 1 or end_line < start_line or start_line > len(lines):
                return original
            end = min(end_line, len(lines))
            replacement = new_text
            if replacement and not replacement.endswith(("\n", "\r")) and end < len(lines):
                replacement += "\n"
            return "".join(lines[: start_line - 1] + [replacement] + lines[end:])
        return original


class CreateDirectoryTool(FileToolMixin, BaseTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="create_directory",
            description="Create a directory, including parent directories when needed.",
            parameters=[ToolParameter("path", "string", "Directory path to create.")],
        )

    def execute(self, path: str = "", **_: Any) -> str:
        if not path:
            return "Error: path is required"
        full = self._resolve_path(path)
        try:
            os.makedirs(full, exist_ok=True)
            return f"Created directory: {full}"
        except Exception as exc:
            return f"Create directory error: {exc}"


class DeletePathTool(FileToolMixin, BaseTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="delete_path",
            description="Delete a file or directory. Directories require recursive=true when not empty.",
            parameters=[
                ToolParameter("path", "string", "File or directory path to delete."),
                ToolParameter("recursive", "boolean", "Delete non-empty directories recursively (default false).", required=False),
            ],
        )

    def execute(self, path: str = "", recursive: bool = False, **_: Any) -> str:
        if not path:
            return "Error: path is required"
        full = self._resolve_path(path)
        if not os.path.exists(full):
            return f"Path not found: {path}"
        try:
            if os.path.isdir(full) and not os.path.islink(full):
                if recursive:
                    shutil.rmtree(full)
                else:
                    os.rmdir(full)
                return f"Deleted directory: {full}"
            os.remove(full)
            return f"Deleted file: {full}"
        except OSError as exc:
            return f"Delete error: {exc}. For non-empty directories, set recursive=true."
        except Exception as exc:
            return f"Delete error: {exc}"


class CopyPathTool(FileToolMixin, BaseTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="copy_path",
            description="Copy a file or directory to a destination path.",
            parameters=[
                ToolParameter("source", "string", "Source file or directory path."),
                ToolParameter("destination", "string", "Destination path."),
                ToolParameter("overwrite", "boolean", "Overwrite existing destination when possible (default false).", required=False),
            ],
        )

    def execute(self, source: str = "", destination: str = "", overwrite: bool = False, **_: Any) -> str:
        if not source or not destination:
            return "Error: source and destination are required"
        src = self._resolve_path(source)
        dst = self._resolve_path(destination)
        if not os.path.exists(src):
            return f"Source not found: {source}"
        if os.path.exists(dst) and not overwrite:
            return f"Destination already exists: {destination}. Set overwrite=true to replace or merge."
        try:
            parent = os.path.dirname(dst)
            if parent:
                os.makedirs(parent, exist_ok=True)
            if os.path.isdir(src) and not os.path.islink(src):
                shutil.copytree(src, dst, dirs_exist_ok=overwrite)
                return f"Copied directory: {src} -> {dst}"
            if os.path.isdir(dst):
                dst = os.path.join(dst, os.path.basename(src))
            shutil.copy2(src, dst)
            return f"Copied file: {src} -> {dst}"
        except Exception as exc:
            return f"Copy error: {exc}"


class MovePathTool(FileToolMixin, BaseTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="move_path",
            description="Move or rename a file or directory to a destination path.",
            parameters=[
                ToolParameter("source", "string", "Source file or directory path."),
                ToolParameter("destination", "string", "Destination path."),
                ToolParameter("overwrite", "boolean", "Overwrite existing destination (default false).", required=False),
            ],
        )

    def execute(self, source: str = "", destination: str = "", overwrite: bool = False, **_: Any) -> str:
        if not source or not destination:
            return "Error: source and destination are required"
        src = self._resolve_path(source)
        dst = self._resolve_path(destination)
        if not os.path.exists(src):
            return f"Source not found: {source}"
        try:
            if os.path.exists(dst):
                if not overwrite:
                    return f"Destination already exists: {destination}. Set overwrite=true to replace."
                if os.path.isdir(dst) and not os.path.islink(dst):
                    shutil.rmtree(dst)
                else:
                    os.remove(dst)
            parent = os.path.dirname(dst)
            if parent:
                os.makedirs(parent, exist_ok=True)
            shutil.move(src, dst)
            return f"Moved path: {src} -> {dst}"
        except Exception as exc:
            return f"Move error: {exc}"


class WebSearchTool(BaseTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="web_search",
            description="General web search using Tavily first when TAVILY_API_KEY is configured, then public search fallbacks. Use this for explicit search requests, latest news, current events, recent information, source links, or unknown web content. Prefer this over hot_news unless the user specifically asks for hot search rankings/trending lists such as 微博热搜、百度热搜、今日热榜.",
            parameters=[
                ToolParameter("query", "string", "Search query, including keywords, date, or site if useful."),
                ToolParameter("max_results", "integer", "Maximum search results to return (default 5).", required=False),
            ],
        )

    def execute(self, query: str = "", max_results: int = 5, **_: Any) -> str:
        query = query.strip()
        if not query:
            return "Error: query is required"
        max_results = max(1, min(int(max_results or 5), 10))
        errors: list[str] = []

        search_attempts = []
        if os.getenv("TAVILY_API_KEY"):
            search_attempts.append(("Tavily", self._search_tavily))
        search_attempts.extend([
            ("DuckDuckGo", self._search_duckduckgo),
            ("Bing News", self._search_bing_news),
            ("Google News", self._search_google_news),
        ])
        for source, search_func in search_attempts:
            try:
                results = search_func(query, max_results)
                if results:
                    return self._format_results(query, results, source)
            except Exception as exc:
                errors.append(f"{source}: {exc}")

        return (
            "Search failed or returned no results. "
            "Network access to public search engines may be blocked or timed out.\n"
            f"Query: {query}\n"
            f"Errors: {'; '.join(errors) if errors else 'no results'}\n"
            "Suggested direct sources to fetch: https://news.google.com/, https://www.bbc.com/news, "
            "https://www.reuters.com/, https://apnews.com/, https://www.thepaper.cn/, https://www.chinanews.com.cn/"
        )

    def _search_tavily(self, query: str, max_results: int) -> list[dict[str, str]]:
        api_key = os.getenv("TAVILY_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("TAVILY_API_KEY is not configured in the GUI process environment or .env file")
        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=api_key)
            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=max_results,
                include_answer=False,
                include_raw_content=False,
            )
            return self._parse_tavily_response(response, max_results)
        except ImportError:
            return self._search_tavily_rest(api_key, query, max_results)
        except Exception as sdk_exc:
            try:
                return self._search_tavily_rest(api_key, query, max_results)
            except Exception as rest_exc:
                raise RuntimeError(f"SDK failed: {sdk_exc}; REST fallback failed: {rest_exc}") from rest_exc

    def _search_tavily_rest(self, api_key: str, query: str, max_results: int) -> list[dict[str, str]]:
        payload = {
            "api_key": api_key,
            "query": query,
            "search_depth": "advanced",
            "topic": "general",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
        }
        raw = _http_post_json(
            "https://api.tavily.com/search",
            payload,
            timeout=20,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        return self._parse_tavily_response(json.loads(raw), max_results)

    def _parse_tavily_response(self, data: Any, max_results: int) -> list[dict[str, str]]:
        if not isinstance(data, dict):
            return []
        results: list[dict[str, str]] = []
        for item in data.get("results", [])[:max_results]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or item.get("url") or "").strip()
            url = str(item.get("url") or "").strip()
            snippet = str(item.get("content") or item.get("snippet") or "").strip()
            if title or url or snippet:
                results.append({"title": title or url, "url": url, "snippet": snippet})
        return results

    def _search_duckduckgo(self, query: str, max_results: int) -> list[dict[str, str]]:
        encoded = urllib.parse.urlencode({"q": query})
        raw = _http_get(f"https://duckduckgo.com/html/?{encoded}", timeout=12)
        return self._parse_duckduckgo(raw, max_results)

    def _search_bing_news(self, query: str, max_results: int) -> list[dict[str, str]]:
        encoded = urllib.parse.urlencode({"q": query, "format": "rss"})
        raw = _http_get(f"https://www.bing.com/news/search?{encoded}", timeout=12)
        return self._parse_rss(raw, max_results)

    def _search_google_news(self, query: str, max_results: int) -> list[dict[str, str]]:
        encoded = urllib.parse.urlencode({"q": query})
        raw = _http_get(f"https://news.google.com/rss/search?{encoded}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans", timeout=12)
        return self._parse_rss(raw, max_results)

    def _format_results(self, query: str, results: list[dict[str, str]], source: str) -> str:
        lines = [f"Search results for: {query}", f"Source: {source}"]
        for index, result in enumerate(results, 1):
            lines.append(
                f"{index}. {result['title']}\n"
                f"   URL: {result['url']}\n"
                f"   Snippet: {result['snippet']}"
            )
        return "\n".join(lines)

    def _parse_duckduckgo(self, raw: str, max_results: int) -> list[dict[str, str]]:
        blocks = re.findall(r'<div[^>]+class="result[^>]*>(.*?)</div>\s*</div>', raw, flags=re.DOTALL | re.IGNORECASE)
        if not blocks:
            blocks = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', raw, flags=re.DOTALL | re.IGNORECASE)
            parsed = []
            for href, title_html in blocks[:max_results]:
                parsed.append({"title": _html_to_text(title_html), "url": self._clean_duck_url(href), "snippet": ""})
            return parsed

        results: list[dict[str, str]] = []
        for block in blocks:
            link = re.search(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.DOTALL | re.IGNORECASE)
            if not link:
                continue
            snippet = re.search(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>|<div[^>]+class="result__snippet"[^>]*>(.*?)</div>', block, flags=re.DOTALL | re.IGNORECASE)
            snippet_html = ""
            if snippet:
                snippet_html = snippet.group(1) or snippet.group(2) or ""
            results.append(
                {
                    "title": _html_to_text(link.group(2)),
                    "url": self._clean_duck_url(link.group(1)),
                    "snippet": _html_to_text(snippet_html),
                }
            )
            if len(results) >= max_results:
                break
        return results

    def _parse_rss(self, raw: str, max_results: int) -> list[dict[str, str]]:
        items = re.findall(r"<item\b[^>]*>(.*?)</item>", raw, flags=re.DOTALL | re.IGNORECASE)
        results: list[dict[str, str]] = []
        for item in items:
            title = self._extract_xml_text(item, "title")
            link = self._extract_xml_text(item, "link")
            snippet = self._extract_xml_text(item, "description")
            if not title and not link:
                continue
            results.append({"title": _html_to_text(title), "url": html.unescape(link), "snippet": _html_to_text(snippet)})
            if len(results) >= max_results:
                break
        return results

    def _extract_xml_text(self, text: str, tag: str) -> str:
        match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", text, flags=re.DOTALL | re.IGNORECASE)
        if not match:
            return ""
        value = match.group(1).strip()
        if value.startswith("<![CDATA[") and value.endswith("]]>"):
            value = value[9:-3]
        return html.unescape(value.strip())

    def _clean_duck_url(self, href: str) -> str:
        href = html.unescape(href)
        if href.startswith("//"):
            href = "https:" + href
        parsed = urllib.parse.urlparse(href)
        qs = urllib.parse.parse_qs(parsed.query)
        if "uddg" in qs and qs["uddg"]:
            return qs["uddg"][0]
        return href


class HotNewsTool(BaseTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="hot_news",
            description="Fetch Chinese hot-search ranking lists from domestic trend boards, such as 微博热搜、百度热搜、今日热榜. Use only when the user explicitly asks for 热搜、热榜、排行榜、微博热搜、百度热搜 or trending list items. Do not use for general web search, latest news search, or source-based news retrieval; use web_search for those.",
            parameters=[
                ToolParameter("source", "string", "Source: 'auto', 'weibo', 'baidu', or 'tophub' (default auto).", required=False, enum=["auto", "weibo", "baidu", "tophub"]),
                ToolParameter("max_results", "integer", "Maximum items to return (default 10).", required=False),
            ],
        )

    def execute(self, source: str = "auto", max_results: int = 10, **_: Any) -> str:
        source = (source or "auto").lower().strip()
        max_results = max(1, min(int(max_results or 10), 20))
        sources = [source] if source != "auto" else ["weibo", "baidu", "tophub"]
        errors: list[str] = []
        for item in sources:
            try:
                if item == "weibo":
                    results = self._fetch_weibo(max_results)
                elif item == "baidu":
                    results = self._fetch_baidu(max_results)
                elif item == "tophub":
                    results = self._fetch_tophub(max_results)
                else:
                    continue
                if results:
                    return self._format_hot_news(item, results)
            except Exception as exc:
                errors.append(f"{item}: {exc}")
        return "Hot news fetch failed. " + ("; ".join(errors) if errors else "No results.")

    def _fetch_weibo(self, max_results: int) -> list[dict[str, str]]:
        raw = _http_get("https://m.weibo.cn/api/container/getIndex?containerid=102803", timeout=12)
        data = json.loads(raw)
        cards = data.get("data", {}).get("cards", [])
        results: list[dict[str, str]] = []
        for card in cards:
            group = card.get("card_group") or []
            for item in group:
                title = str(item.get("desc") or item.get("card_type_name") or "").strip()
                if not title or title in {"热搜", "更多"}:
                    continue
                url = item.get("scheme") or f"https://s.weibo.com/weibo?q={urllib.parse.quote(title)}"
                results.append({"title": title, "url": str(url), "snippet": str(item.get("desc_extr") or "")})
                if len(results) >= max_results:
                    return results
        return results

    def _fetch_baidu(self, max_results: int) -> list[dict[str, str]]:
        raw = _http_get("https://top.baidu.com/board?tab=realtime", timeout=12)
        titles = re.findall(r'<div[^>]+class="[^"]*c-single-text-ellipsis[^"]*"[^>]*>(.*?)</div>', raw, flags=re.DOTALL | re.IGNORECASE)
        results: list[dict[str, str]] = []
        for title_html in titles:
            title = _html_to_text(title_html)
            if not title or len(title) < 2:
                continue
            results.append({"title": title, "url": f"https://www.baidu.com/s?wd={urllib.parse.quote(title)}", "snippet": "百度热搜"})
            if len(results) >= max_results:
                break
        return results

    def _fetch_tophub(self, max_results: int) -> list[dict[str, str]]:
        raw = _http_get("https://tophub.today/n/KqndgxeLl9", timeout=12)
        rows = re.findall(r'<td[^>]*class="al"[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', raw, flags=re.DOTALL | re.IGNORECASE)
        results: list[dict[str, str]] = []
        for href, title_html in rows:
            title = _html_to_text(title_html)
            if not title:
                continue
            url = href if href.startswith("http") else f"https://tophub.today{href}"
            results.append({"title": title, "url": url, "snippet": "今日热榜"})
            if len(results) >= max_results:
                break
        return results

    def _format_hot_news(self, source: str, results: list[dict[str, str]]) -> str:
        lines = [f"Hot news source: {source}"]
        for index, result in enumerate(results, 1):
            lines.append(
                f"{index}. {result['title']}\n"
                f"   URL: {result['url']}\n"
                f"   Info: {result['snippet']}"
            )
        return "\n".join(lines)


class WebFetchTool(BaseTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="web_fetch",
            description="Fetch the text content of a web page.",
            parameters=[
                ToolParameter("url", "string", "URL to fetch (http:// or https://)."),
                ToolParameter("max_chars", "integer", "Max characters to return (default 5000).", required=False),
            ],
        )

    def execute(self, url: str = "", max_chars: int = 5000, **_: Any) -> str:
        if not url.startswith(("http://", "https://")):
            return "Error: URL must start with http:// or https://"
        try:
            raw = _http_get(url, timeout=12)
            text = _html_to_text(raw)
            if len(text) > max_chars:
                text = text[:max_chars] + "... [truncated]"
            return text
        except Exception as exc:
            return f"Fetch error: {exc}"


def _http_post_json(url: str, payload: dict[str, Any], timeout: int = 10, headers: dict[str, str] | None = None) -> str:
    body = json.dumps(payload).encode("utf-8")
    request_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(url, data=body, headers=request_headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except Exception as urllib_exc:
        try:
            return _http_post_json_powershell(url, payload, timeout, request_headers)
        except Exception as ps_exc:
            raise RuntimeError(f"urllib failed: {urllib_exc}; powershell failed: {ps_exc}") from ps_exc


def _http_post_json_powershell(url: str, payload: dict[str, Any], timeout: int, headers: dict[str, str]) -> str:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        raise RuntimeError("PowerShell executable not found")
    safe_headers = {key: value for key, value in headers.items() if key.lower() not in {"content-type", "accept", "user-agent"}}
    script = (
        "$ProgressPreference='SilentlyContinue'; "
        "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; "
        f"$headersObj = ConvertFrom-Json {json_escape_ps(json.dumps(safe_headers))}; "
        "$headers = @{}; foreach ($p in $headersObj.psobject.Properties) { $headers[$p.Name] = [string]$p.Value }; "
        f"$body = {json_escape_ps(json.dumps(payload, ensure_ascii=False))}; "
        f"Invoke-RestMethod -Uri {json_escape_ps(url)} -Method Post -Body $body -ContentType 'application/json' "
        f"-Headers $headers -TimeoutSec {timeout} | ConvertTo-Json -Depth 20"
    )
    completed = subprocess.run(
        [powershell, "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout + 5,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"PowerShell exit code {completed.returncode}")
    return completed.stdout


def _http_get(url: str, timeout: int = 10) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except Exception as urllib_exc:
        try:
            return _http_get_powershell(url, timeout)
        except Exception as ps_exc:
            raise RuntimeError(f"urllib failed: {urllib_exc}; powershell failed: {ps_exc}") from ps_exc


def _http_get_powershell(url: str, timeout: int = 10) -> str:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        raise RuntimeError("PowerShell executable not found")
    script = (
        "$ProgressPreference='SilentlyContinue'; "
        "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; "
        f"$r = Invoke-WebRequest -Uri {json_escape_ps(url)} -TimeoutSec {timeout} -UseBasicParsing; "
        "$r.Content"
    )
    completed = subprocess.run(
        [powershell, "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout + 5,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"PowerShell exit code {completed.returncode}")
    return completed.stdout


def json_escape_ps(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _html_to_text(raw: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<noscript\b[^>]*>.*?</noscript>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>|</div>|</li>|</h[1-6]>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def register_builtin_tools(registry: ToolRegistry, workspace_root: str = ".", enabled_tools: list[str] | None = None) -> None:
    enabled = set(enabled_tools) if enabled_tools is not None else None
    tools = [
        CalculatorTool(),
        DateTimeTool(),
        ReadFileTool(workspace_root),
        ListDirectoryTool(workspace_root),
        WriteFileTool(workspace_root),
        EditFileTool(workspace_root),
        CreateDirectoryTool(workspace_root),
        DeletePathTool(workspace_root),
        CopyPathTool(workspace_root),
        MovePathTool(workspace_root),
        WebSearchTool(),
        HotNewsTool(),
        WebFetchTool(),
    ]
    for tool in tools:
        if enabled is None or tool.definition.name in enabled:
            registry.register(tool)
