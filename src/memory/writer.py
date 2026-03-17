"""Memory writer: append entries to workspace daily notes files.

Responsibilities:
- Append text to memory/YYYY-MM-DD.md (create if not exist)
- Process flush candidates from compaction → daily notes
- Enforce file size limits
- UTF-8 safe writes (CJK compatible)
- Carry scope_key metadata on every write (ADR 0034)
- Trigger incremental index after write (best-effort)
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from src.infra.errors import MemoryWriteError
from src.memory.contracts import ResolvedFlushCandidate

if TYPE_CHECKING:
    from src.config.settings import MemorySettings
    from src.memory.indexer import MemoryIndexer

logger = structlog.get_logger()


_uuid7_last_ms: int = 0
_uuid7_seq: int = 0


def _uuid7() -> uuid.UUID:
    """Generate a UUIDv7 (time-ordered, monotonic within ms). Minimal local helper (ADR 0053).

    Uses a 12-bit monotonic counter (rand_a) within the same millisecond to
    guarantee strict ordering for back-to-back calls.  The counter resets to a
    random base on each new millisecond tick.
    """
    global _uuid7_last_ms, _uuid7_seq  # noqa: PLW0603
    timestamp_ms = int(time.time() * 1000)
    if timestamp_ms <= _uuid7_last_ms:
        _uuid7_seq += 1
        timestamp_ms = _uuid7_last_ms
    else:
        _uuid7_last_ms = timestamp_ms
        _uuid7_seq = int.from_bytes(os.urandom(2), "big") & 0x0FFF
    seq = _uuid7_seq & 0x0FFF
    rand_b = int.from_bytes(os.urandom(8), "big") & 0x3FFFFFFFFFFFFFFF
    uuid_int = (timestamp_ms << 80) | (0x7 << 76) | (seq << 64) | (0x2 << 62) | rand_b
    return uuid.UUID(int=uuid_int)


class MemoryWriter:
    """Write memory entries to workspace daily notes files."""

    def __init__(
        self,
        workspace_path: Path,
        settings: MemorySettings,
        indexer: MemoryIndexer | None = None,
    ) -> None:
        self._workspace_path = workspace_path
        self._settings = settings
        self._indexer = indexer

    async def append_daily_note(
        self,
        text: str,
        *,
        scope_key: str = "main",
        source: str = "user",
        source_session_id: str | None = None,
        target_date: date | None = None,
    ) -> Path:
        """Append a timestamped entry to daily note file.

        Returns: path to the written file.
        Raises: MemoryWriteError if file exceeds max size.
        """
        today = target_date or date.today()
        filename = f"{today.isoformat()}.md"
        memory_dir = self._workspace_path / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        filepath = memory_dir / filename

        entry_id = str(_uuid7())
        now = datetime.now(UTC)
        meta_parts = [
            f"entry_id: {entry_id}",
            f"source: {source}",
            f"scope: {scope_key}",
        ]
        if source_session_id:
            meta_parts.append(f"source_session_id: {source_session_id}")
        meta_line = f"[{now.strftime('%H:%M')}] ({', '.join(meta_parts)})"
        entry = f"---\n{meta_line}\n{text}\n"
        entry_bytes = entry.encode("utf-8")

        self._check_size_limit(filepath, entry_bytes, filename)

        with filepath.open("a", encoding="utf-8") as f:
            f.write(entry)

        logger.info("daily_note_appended", path=str(filepath), entry_id=entry_id,
                     scope_key=scope_key, source=source, bytes_written=len(entry_bytes))

        await self._try_incremental_index(
            filepath, text, scope_key, today,
            entry_id=entry_id, source_session_id=source_session_id,
        )
        return filepath

    def _check_size_limit(
        self, filepath: Path, entry_bytes: bytes, filename: str,
    ) -> None:
        """Raise MemoryWriteError if appending would exceed daily note size limit."""
        current_size = filepath.stat().st_size if filepath.exists() else 0
        if current_size + len(entry_bytes) > self._settings.max_daily_note_bytes:
            logger.warning(
                "daily_note_size_limit", path=str(filepath),
                current_size=current_size, entry_size=len(entry_bytes),
                max_bytes=self._settings.max_daily_note_bytes,
            )
            raise MemoryWriteError(
                f"Daily note {filename} would exceed size limit "
                f"({current_size + len(entry_bytes)} > {self._settings.max_daily_note_bytes})"
            )

    async def _try_incremental_index(
        self, filepath: Path, text: str, scope_key: str, today: date,
        *, entry_id: str | None = None, source_session_id: str | None = None,
    ) -> None:
        """Best-effort incremental index after write."""
        if not self._indexer:
            return
        try:
            rel_path = str(filepath.relative_to(self._workspace_path))
            await self._indexer.index_entry_direct(
                content=text, scope_key=scope_key, source_type="daily_note",
                source_path=rel_path, source_date=today,
                entry_id=entry_id, source_session_id=source_session_id,
            )
        except Exception:
            logger.warning("memory_index_after_write_failed",
                           path=str(filepath), scope_key=scope_key)

    async def process_flush_candidates(
        self,
        candidates: list[ResolvedFlushCandidate],
        *,
        min_confidence: float = 0.5,
    ) -> int:
        """Filter and persist flush candidates to today's daily note.

        Filters:
        - candidate.confidence >= min_confidence
        - candidate.candidate_text non-empty

        Returns: number of candidates written.
        """
        written = 0
        for candidate in candidates:
            if candidate.confidence < min_confidence:
                logger.debug(
                    "flush_candidate_filtered",
                    confidence=candidate.confidence,
                    min_confidence=min_confidence,
                )
                continue
            if not candidate.candidate_text.strip():
                continue

            try:
                await self.append_daily_note(
                    text=candidate.candidate_text,
                    scope_key=candidate.scope_key,
                    source="compaction_flush",
                    source_session_id=candidate.source_session_id,
                )
                written += 1
            except MemoryWriteError:
                logger.warning(
                    "flush_candidate_write_failed",
                    scope_key=candidate.scope_key,
                    source_session_id=candidate.source_session_id,
                )
                break  # Stop writing if file limit reached

        logger.info(
            "flush_candidates_processed",
            total=len(candidates),
            written=written,
        )
        return written
