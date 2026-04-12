"""Memory parity checker: compare DB ledger with workspace daily note files (P2-M2d).

Two-layer comparison (ADR 0060 D4):
1. ID-level: entry_id set difference between ledger and workspace.
2. Content-level: for matched entry_ids, compare content + scope_key + source + source_session_id.

Read-only, no side effects, no auto-repair.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from src.memory.indexer import MemoryIndexer

if TYPE_CHECKING:
    from src.memory.ledger import MemoryLedgerWriter

logger = structlog.get_logger()


@dataclass(frozen=True)
class ParityReport:
    """Comparison result between DB ledger and workspace files."""

    ledger_count: int
    workspace_count: int
    only_in_ledger: list[str] = field(default_factory=list)
    only_in_workspace: list[str] = field(default_factory=list)
    matched: int = 0
    content_mismatch: list[str] = field(default_factory=list)
    metadata_mismatch: list[str] = field(default_factory=list)

    @property
    def is_consistent(self) -> bool:
        return (
            not self.only_in_ledger
            and not self.only_in_workspace
            and not self.content_mismatch
            and not self.metadata_mismatch
        )


class MemoryParityChecker:
    """Compare memory source ledger with workspace daily note files.

    Two-layer comparison:
    1. ID-level: entry_id set difference
    2. Content-level: for matched entry_ids, compare content + metadata
    """

    def __init__(
        self,
        ledger: MemoryLedgerWriter,
        workspace_path: Path,
    ) -> None:
        self._ledger = ledger
        self._workspace_path = workspace_path

    async def check(self, *, scope_key: str | None = None) -> ParityReport:
        """Run parity comparison. Read-only, no side effects."""
        ledger_entries = await self._ledger.get_entries_for_parity(scope_key=scope_key)
        workspace_entries = self._scan_workspace(scope_key=scope_key)

        ledger_ids = set(ledger_entries.keys())
        workspace_ids = set(workspace_entries.keys())

        only_in_ledger = sorted(ledger_ids - workspace_ids)
        only_in_workspace = sorted(workspace_ids - ledger_ids)
        matched_ids = ledger_ids & workspace_ids

        content_mismatch: list[str] = []
        metadata_mismatch: list[str] = []

        for eid in sorted(matched_ids):
            le = ledger_entries[eid]
            we = workspace_entries[eid]
            if le["content"] != we["content"]:
                content_mismatch.append(eid)
            if (
                le["scope_key"] != we.get("scope_key")
                or le["source"] != we.get("source")
                or le["source_session_id"] != we.get("source_session_id")
            ):
                metadata_mismatch.append(eid)

        return ParityReport(
            ledger_count=len(ledger_entries),
            workspace_count=len(workspace_entries),
            only_in_ledger=only_in_ledger,
            only_in_workspace=only_in_workspace,
            matched=len(matched_ids),
            content_mismatch=content_mismatch,
            metadata_mismatch=metadata_mismatch,
        )

    def _scan_workspace(self, *, scope_key: str | None = None) -> dict[str, dict]:
        """Scan workspace/memory/*.md and extract entries with entry_id.

        Args:
            scope_key: If provided, only return entries matching this scope.

        Returns: {entry_id: {content, scope_key, source, source_session_id}}
        Skips entries without entry_id (pre-ADR 0053 artifacts).
        """
        memory_dir = self._workspace_path / "memory"
        if not memory_dir.is_dir():
            return {}

        entries: dict[str, dict] = {}
        for filepath in sorted(memory_dir.glob("*.md")):
            content = filepath.read_text(encoding="utf-8").strip()
            if not content:
                continue
            raw_entries = re.split(r"^---$", content, flags=re.MULTILINE)
            for raw_entry in raw_entries:
                stripped = raw_entry.strip()
                if not stripped:
                    continue
                meta = MemoryIndexer._parse_entry_metadata(stripped)
                entry_id = meta.get("entry_id")
                if not entry_id:
                    continue
                entry_scope = meta.get("scope", "main")
                if scope_key is not None and entry_scope != scope_key:
                    continue
                entry_text = MemoryIndexer._extract_entry_text(stripped)
                entries[entry_id] = {
                    "content": entry_text,
                    "scope_key": entry_scope,
                    "source": meta.get("source"),
                    "source_session_id": meta.get("source_session_id"),
                }

        return entries
