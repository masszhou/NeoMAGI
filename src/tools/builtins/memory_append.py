"""Memory append tool: save user notes to daily notes files."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.tools.base import BaseTool, RiskLevel, ToolGroup, ToolMode

if TYPE_CHECKING:
    from src.memory.writer import MemoryWriter
    from src.tools.context import ToolContext


class MemoryAppendTool(BaseTool):
    """Save a memory note to today's daily notes file.

    scope_key is read from context.scope_key (injected by session_resolver).
    Tool does NOT derive scope on its own (ADR 0034).
    """

    def __init__(self, writer: MemoryWriter) -> None:
        self._writer = writer

    @property
    def name(self) -> str:
        return "memory_append"

    @property
    def description(self) -> str:
        return "Save a memory note to today's daily notes file."

    @property
    def group(self) -> ToolGroup:
        return ToolGroup.memory

    @property
    def allowed_modes(self) -> frozenset[ToolMode]:
        return frozenset({ToolMode.chat_safe, ToolMode.coding})

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.high

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The memory content to save.",
                },
            },
            "required": ["text"],
        }

    async def execute(self, arguments: dict, context: ToolContext | None = None) -> dict:
        text = arguments.get("text", "")
        if not isinstance(text, str) or not text.strip():
            return {
                "error_code": "INVALID_ARGS",
                "message": "text must be a non-empty string.",
            }

        scope_key = context.scope_key if context else "main"
        source_session_id = context.session_id if context else None
        principal_id = context.principal_id if context else None
        result = await self._writer.append_daily_note(
            text=text.strip(),
            scope_key=scope_key,
            source="user",
            source_session_id=source_session_id,
            principal_id=principal_id,
        )

        response: dict = {
            "ok": True,
            "entry_id": result.entry_id,
            "ledger_written": result.ledger_written,
            "projection_written": result.projection_written,
        }

        if result.ledger_written and result.projection_written:
            response["message"] = f"Memory saved (entry_id: {result.entry_id})"
        elif result.ledger_written:
            response["message"] = (
                f"Memory saved to DB ledger (entry_id: {result.entry_id}); "
                "workspace projection pending"
            )
        elif result.projection_written and result.projection_path:
            response["message"] = f"Memory saved to {result.projection_path.name}"
        else:
            response["message"] = "Memory write completed"

        if result.projection_path:
            response["path"] = str(result.projection_path)

        return response
