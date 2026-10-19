"""Project Aura - Coder Agent tools

Read-only tools the Coder Agent can call while it works (Claude tool use), so it gathers the
context it needs instead of relying on one retrieval made before it starts:

    search_code      hybrid GraphRAG search (call graph + semantic), the orchestrator's own
                     context retrieval, on demand
    read_file        a file in the project, with line numbers, optionally a line range
    list_directory   the entries of a project directory

Every path is confined to the project root (no traversal, no symlinks out of it), output is
size-capped, and nothing is written: the coder's only output is the code it submits, which
then goes through security review, validation, sandbox tests, and human approval.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .agent_orchestrator import ContextRetrievalService

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 256_000  # files larger than this are not read whole
MAX_READ_LINES = 400  # lines returned per read_file call
MAX_DIR_ENTRIES = 200
MAX_SEARCH_RESULTS = 8
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "search_code",
        "description": (
            "Search the codebase for code related to a query: structural matches from the "
            "call graph (callers, callees, dependencies of an entity) and semantically "
            "similar code and policy documents. Use it to find where something is defined "
            "or used before reading files."
        ),
        "input_schema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "What to look for"},
                "entity": {
                    "type": "string",
                    "description": "Optional function or class name for structural search",
                },
            },
        },
    },
    {
        "name": "read_file",
        "description": (
            "Read a file in the project, with line numbers. Paths are relative to the "
            f"project root. Returns at most {MAX_READ_LINES} lines; use start_line and "
            "end_line to read further."
        ),
        "input_schema": {
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {"type": "string"},
                "start_line": {"type": "integer", "description": "1-based, inclusive"},
                "end_line": {"type": "integer", "description": "1-based, inclusive"},
            },
        },
    },
    {
        "name": "list_directory",
        "description": "List a project directory (relative to the project root).",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Default: root"}},
        },
    },
]


class ToolError(Exception):
    """A tool call that cannot be served; its message goes back to the model."""


class CoderWorkspace:
    """The project the Coder Agent works on, exposed through read-only tools."""

    def __init__(
        self,
        root: Path | str,
        context_service: "ContextRetrievalService | None" = None,
    ):
        self.root = Path(root).resolve()
        self.context_service = context_service

    def tool_definitions(self) -> list[dict[str, Any]]:
        tools = TOOL_DEFINITIONS
        if self.context_service is None:
            tools = [t for t in tools if t["name"] != "search_code"]
        return [dict(t) for t in tools]

    def execute(self, name: str, tool_input: dict[str, Any]) -> tuple[str, bool]:
        """Run a tool. Returns (result text, is_error)."""
        handlers = {
            "search_code": self.search_code,
            "read_file": self.read_file,
            "list_directory": self.list_directory,
        }
        handler = handlers.get(name)
        if handler is None:
            return f"Unknown tool: {name}", True
        try:
            return handler(**(tool_input or {})), False
        except ToolError as e:
            return str(e), True
        except TypeError as e:  # unexpected or missing arguments
            return f"Invalid arguments for {name}: {e}", True

    # -- tools ---------------------------------------------------------------

    def search_code(self, query: str, entity: str | None = None) -> str:
        if self.context_service is None:
            raise ToolError("Code search is not available in this workspace")
        context = self.context_service.get_hybrid_context(entity or query, query)
        items = sorted(context.items, key=lambda i: i.confidence, reverse=True)
        if not items:
            return "No results."
        lines = []
        for item in items[:MAX_SEARCH_RESULTS]:
            source = getattr(item.source, "value", item.source)
            lines.append(
                f"[{source}, confidence {item.confidence:.2f}]\n{item.content}"
            )
        return "\n\n".join(lines)

    def read_file(
        self, path: str, start_line: int | None = None, end_line: int | None = None
    ) -> str:
        target = self._resolve(path)
        if not target.is_file():
            raise ToolError(f"Not a file: {path}")
        if target.stat().st_size > MAX_FILE_BYTES and start_line is None:
            raise ToolError(
                f"{path} is larger than {MAX_FILE_BYTES} bytes; read it in ranges with "
                "start_line and end_line"
            )
        try:
            lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as e:
            raise ToolError(f"Cannot read {path}: {e}") from e
        first = max(1, start_line or 1)
        last = min(len(lines), end_line or len(lines), first + MAX_READ_LINES - 1)
        if first > len(lines):
            return f"{path} has {len(lines)} lines."
        body = "\n".join(f"{n:>5}  {lines[n - 1]}" for n in range(first, last + 1))
        more = (
            f"\n[lines {last + 1}-{len(lines)} not shown]" if last < len(lines) else ""
        )
        return f"{path} (lines {first}-{last} of {len(lines)})\n{body}{more}"

    def list_directory(self, path: str = ".") -> str:
        target = self._resolve(path)
        if not target.is_dir():
            raise ToolError(f"Not a directory: {path}")
        entries = []
        for child in sorted(target.iterdir(), key=lambda c: (c.is_file(), c.name)):
            if child.name in SKIP_DIRS or child.name.startswith("."):
                continue
            if child.is_symlink() and not self._inside(child.resolve()):
                continue
            entries.append(child.name + ("/" if child.is_dir() else ""))
            if len(entries) >= MAX_DIR_ENTRIES:
                entries.append("[more entries not shown]")
                break
        return "\n".join(entries) or "(empty)"

    # -- path safety ---------------------------------------------------------

    def _inside(self, path: Path) -> bool:
        return path == self.root or self.root in path.parents

    def _resolve(self, path: str) -> Path:
        """A path inside the project root, after resolving `..` and symlinks."""
        candidate = (self.root / (path or ".")).resolve()
        if not self._inside(candidate):
            raise ToolError(f"Path is outside the project: {path}")
        return candidate
