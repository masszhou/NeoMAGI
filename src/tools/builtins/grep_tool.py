"""Grep text/regex search within workspace files.

Uses asyncio.to_thread for non-blocking filesystem operations.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from src.tools.base import BaseTool, RiskLevel, ToolGroup, ToolMode
from src.tools.read_state import resolve_search_dir

if TYPE_CHECKING:
    from src.tools.context import ToolContext

logger = structlog.get_logger()

_DEFAULT_MAX_RESULTS = 100
_MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB per file
_MAX_LINE_LENGTH = 500  # truncate long matching lines


def _grep_file(resolved: Path, regex: re.Pattern, rel_path: str, cap: int) -> list[dict]:
    """Search a single file for regex matches. Returns at most *cap* hits."""
    try:
        text = resolved.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    hits: list[dict] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not regex.search(line):
            continue
        display = line[:_MAX_LINE_LENGTH] + ("..." if len(line) > _MAX_LINE_LENGTH else "")
        hits.append({"file": rel_path, "line": line_no, "content": display})
        if len(hits) >= cap:
            break
    return hits


class GrepTool(BaseTool):
    """Search for text or regex patterns within workspace files."""

    def __init__(
        self, workspace_dir: Path, *, max_results: int = _DEFAULT_MAX_RESULTS,
    ) -> None:
        self._workspace_dir = workspace_dir.resolve()
        self._max_results = max_results

    @property
    def group(self) -> ToolGroup:
        return ToolGroup.code

    @property
    def allowed_modes(self) -> frozenset[ToolMode]:
        return frozenset({ToolMode.coding})

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.low

    @property
    def is_read_only(self) -> bool:
        return True

    @property
    def is_concurrency_safe(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return "grep"

    @property
    def description(self) -> str:
        return (
            "Search for text or regex patterns in workspace files. "
            f"Returns up to {_DEFAULT_MAX_RESULTS} matching lines."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Search pattern (regex supported).",
                },
                "glob": {
                    "type": "string",
                    "description": (
                        "File glob to filter files, e.g. '**/*.py'. "
                        "Default: '**/*'."
                    ),
                },
                "path": {
                    "type": "string",
                    "description": (
                        "Subdirectory to search in (relative to workspace). "
                        "Default: workspace root."
                    ),
                },
                "case_insensitive": {
                    "type": "boolean",
                    "description": "Case-insensitive search. Default: false.",
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, arguments: dict, context: ToolContext | None = None) -> dict:
        pattern_str = arguments.get("pattern", "")
        if not isinstance(pattern_str, str) or not pattern_str:
            return {"error_code": "INVALID_ARGS", "message": "pattern must be a non-empty string."}

        regex = _compile_regex(pattern_str, arguments.get("case_insensitive", False))
        if isinstance(regex, dict):
            return regex

        dir_result = resolve_search_dir(arguments.get("path", ""), self._workspace_dir)
        if isinstance(dir_result, dict):
            return dir_result
        search_dir, _ = dir_result

        file_glob = arguments.get("glob", "**/*") or "**/*"
        try:
            results = await asyncio.to_thread(
                self._grep_sync, search_dir, regex, file_glob,
            )
        except Exception as e:
            logger.exception("grep_error", pattern=pattern_str)
            return {"error_code": "GREP_ERROR", "message": f"Grep failed: {e}"}

        truncated = len(results) > self._max_results
        return {
            "matches": results[: self._max_results], "count": min(len(results), self._max_results),
            "truncated": truncated, "pattern": pattern_str,
        }

    def _grep_sync(
        self, search_dir: Path, regex: re.Pattern, file_glob: str,
    ) -> list[dict]:
        """Synchronous grep in thread pool. Bounded to max_results + 1."""
        cap = self._max_results + 1
        results: list[dict] = []
        for file_path in search_dir.glob(file_glob):
            if len(results) >= cap:
                break
            resolved = file_path.resolve()
            if not _is_searchable(resolved, self._workspace_dir):
                continue
            rel_path = str(resolved.relative_to(self._workspace_dir))
            results.extend(_grep_file(resolved, regex, rel_path, cap - len(results)))
        return results


def _compile_regex(pattern_str: str, case_insensitive: object) -> re.Pattern | dict:
    flags = re.IGNORECASE if case_insensitive else 0
    try:
        return re.compile(pattern_str, flags)
    except re.error as e:
        return {"error_code": "INVALID_PATTERN", "message": f"Invalid regex: {e}"}


def _is_searchable(resolved: Path, workspace_dir: Path) -> bool:
    return (
        resolved.is_file()
        and resolved.is_relative_to(workspace_dir)
        and resolved.stat().st_size <= _MAX_FILE_SIZE_BYTES
    )
