"""Tests for MemoryWriter: append_daily_note and process_flush_candidates.

Covers both no-ledger fallback mode (pre-M2d behavior) and ledger-wired mode (P2-M2d).
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.config.settings import MemorySettings
from src.infra.errors import LedgerWriteError, MemoryWriteError
from src.memory.contracts import ResolvedFlushCandidate
from src.memory.writer import MemoryWriter, MemoryWriteResult, _uuid7


def _make_settings(**overrides) -> MemorySettings:
    defaults = {
        "workspace_path": Path("workspace"),
        "max_daily_note_bytes": 32_768,
        "daily_notes_load_days": 2,
        "daily_notes_max_tokens": 4000,
        "flush_min_confidence": 0.5,
    }
    defaults.update(overrides)
    return MemorySettings(**defaults)


def _make_mock_ledger(*, return_value: bool = True, side_effect=None) -> AsyncMock:
    ledger = AsyncMock()
    if side_effect:
        ledger.append.side_effect = side_effect
    else:
        ledger.append.return_value = return_value
    return ledger


# ── No-ledger fallback mode (preserves pre-M2d behavior) ──


class TestAppendDailyNote:
    @pytest.mark.asyncio
    async def test_creates_file_and_writes(self, tmp_path: Path) -> None:
        settings = _make_settings()
        writer = MemoryWriter(tmp_path, settings)
        target_date = date(2026, 2, 22)

        result = await writer.append_daily_note(
            "Test note", scope_key="main", source="user", target_date=target_date
        )

        assert isinstance(result, MemoryWriteResult)
        assert result.ledger_written is False
        assert result.projection_written is True
        assert result.projection_path is not None
        assert result.projection_path.exists()
        assert result.projection_path.name == "2026-02-22.md"
        content = result.projection_path.read_text(encoding="utf-8")
        assert "Test note" in content
        assert "scope: main" in content
        assert "source: user" in content
        assert content.startswith("---\n")

    @pytest.mark.asyncio
    async def test_appends_to_existing(self, tmp_path: Path) -> None:
        settings = _make_settings()
        writer = MemoryWriter(tmp_path, settings)
        target_date = date(2026, 2, 22)

        await writer.append_daily_note(
            "First", scope_key="main", source="user", target_date=target_date
        )
        await writer.append_daily_note(
            "Second", scope_key="main", source="system", target_date=target_date
        )

        path = tmp_path / "memory" / "2026-02-22.md"
        content = path.read_text(encoding="utf-8")
        assert "First" in content
        assert "Second" in content
        assert content.count("---") == 2

    @pytest.mark.asyncio
    async def test_size_limit_raises(self, tmp_path: Path) -> None:
        settings = _make_settings(max_daily_note_bytes=200)
        writer = MemoryWriter(tmp_path, settings)
        target_date = date(2026, 2, 22)

        await writer.append_daily_note(
            "hi", scope_key="main", source="user", target_date=target_date
        )

        with pytest.raises(MemoryWriteError, match="exceed size limit"):
            await writer.append_daily_note(
                "A very long note " * 10,
                scope_key="main",
                source="user",
                target_date=target_date,
            )

    @pytest.mark.asyncio
    async def test_utf8_cjk(self, tmp_path: Path) -> None:
        settings = _make_settings()
        writer = MemoryWriter(tmp_path, settings)
        target_date = date(2026, 2, 22)

        result = await writer.append_daily_note(
            "用户偏好：中文回复", scope_key="main", source="user", target_date=target_date
        )

        content = result.projection_path.read_text(encoding="utf-8")
        assert "用户偏好：中文回复" in content

    @pytest.mark.asyncio
    async def test_scope_key_in_metadata(self, tmp_path: Path) -> None:
        settings = _make_settings()
        writer = MemoryWriter(tmp_path, settings)
        target_date = date(2026, 2, 22)

        result = await writer.append_daily_note(
            "note", scope_key="main", source="user", target_date=target_date
        )

        content = result.projection_path.read_text(encoding="utf-8")
        assert "scope: main" in content

    @pytest.mark.asyncio
    async def test_creates_memory_directory(self, tmp_path: Path) -> None:
        settings = _make_settings()
        writer = MemoryWriter(tmp_path, settings)
        target_date = date(2026, 2, 22)

        memory_dir = tmp_path / "memory"
        assert not memory_dir.exists()

        await writer.append_daily_note(
            "test", scope_key="main", source="user", target_date=target_date
        )

        assert memory_dir.is_dir()

    @pytest.mark.asyncio
    async def test_default_date_is_today(self, tmp_path: Path) -> None:
        settings = _make_settings()
        writer = MemoryWriter(tmp_path, settings)

        result = await writer.append_daily_note(
            "today note", scope_key="main", source="user"
        )

        today = date.today()
        assert result.projection_path.name == f"{today.isoformat()}.md"


class TestProcessFlushCandidates:
    @pytest.mark.asyncio
    async def test_filters_low_confidence(self, tmp_path: Path) -> None:
        settings = _make_settings()
        writer = MemoryWriter(tmp_path, settings)

        candidates = [
            ResolvedFlushCandidate(
                candidate_text="low conf", scope_key="main",
                source_session_id="s1", confidence=0.3,
            ),
            ResolvedFlushCandidate(
                candidate_text="high conf", scope_key="main",
                source_session_id="s1", confidence=0.8,
            ),
        ]

        written = await writer.process_flush_candidates(candidates, min_confidence=0.5)
        assert written == 1

        path = tmp_path / "memory" / f"{date.today().isoformat()}.md"
        content = path.read_text(encoding="utf-8")
        assert "high conf" in content
        assert "low conf" not in content

    @pytest.mark.asyncio
    async def test_empty_list(self, tmp_path: Path) -> None:
        settings = _make_settings()
        writer = MemoryWriter(tmp_path, settings)

        written = await writer.process_flush_candidates([])
        assert written == 0

    @pytest.mark.asyncio
    async def test_skips_empty_text(self, tmp_path: Path) -> None:
        settings = _make_settings()
        writer = MemoryWriter(tmp_path, settings)

        candidates = [
            ResolvedFlushCandidate(
                candidate_text="   ", scope_key="main",
                source_session_id="s1", confidence=0.9,
            ),
        ]

        written = await writer.process_flush_candidates(candidates)
        assert written == 0

    @pytest.mark.asyncio
    async def test_scope_key_propagation(self, tmp_path: Path) -> None:
        settings = _make_settings()
        writer = MemoryWriter(tmp_path, settings)

        candidates = [
            ResolvedFlushCandidate(
                candidate_text="scoped note", scope_key="main",
                source_session_id="s1", confidence=0.9,
            ),
        ]

        written = await writer.process_flush_candidates(candidates)
        assert written == 1

        path = tmp_path / "memory" / f"{date.today().isoformat()}.md"
        content = path.read_text(encoding="utf-8")
        assert "scope: main" in content
        assert "source: compaction_flush" in content

    @pytest.mark.asyncio
    async def test_stops_on_size_limit(self, tmp_path: Path) -> None:
        settings = _make_settings(max_daily_note_bytes=500)
        writer = MemoryWriter(tmp_path, settings)

        candidates = [
            ResolvedFlushCandidate(
                candidate_text=f"note {i}" * 5, scope_key="main",
                source_session_id="s1", confidence=0.9,
            )
            for i in range(10)
        ]

        written = await writer.process_flush_candidates(candidates)
        assert 0 < written < 10

    @pytest.mark.asyncio
    async def test_flush_propagates_source_session_id(self, tmp_path: Path) -> None:
        settings = _make_settings()
        writer = MemoryWriter(tmp_path, settings)

        candidates = [
            ResolvedFlushCandidate(
                candidate_text="flushed note", scope_key="main",
                source_session_id="telegram:peer:42", confidence=0.9,
            ),
        ]

        await writer.process_flush_candidates(candidates)

        path = tmp_path / "memory" / f"{date.today().isoformat()}.md"
        content = path.read_text(encoding="utf-8")
        assert "source_session_id: telegram:peer:42" in content


class TestUuid7:
    def test_returns_valid_uuid(self) -> None:
        uid = _uuid7()
        assert uid.version == 7

    def test_uniqueness(self) -> None:
        ids = {str(_uuid7()) for _ in range(100)}
        assert len(ids) == 100

    def test_time_ordered(self) -> None:
        prev = _uuid7()
        for _ in range(50):
            curr = _uuid7()
            assert curr.int > prev.int
            prev = curr


class TestAdr0053EntryId:
    @pytest.mark.asyncio
    async def test_entry_id_in_metadata(self, tmp_path: Path) -> None:
        settings = _make_settings()
        writer = MemoryWriter(tmp_path, settings)
        target_date = date(2026, 2, 22)

        result = await writer.append_daily_note(
            "test", scope_key="main", source="user", target_date=target_date
        )

        content = result.projection_path.read_text(encoding="utf-8")
        match = re.search(r"entry_id:\s*([\w-]+)", content)
        assert match is not None
        entry_id = match.group(1)
        assert len(entry_id) == 36

    @pytest.mark.asyncio
    async def test_source_session_id_in_metadata(self, tmp_path: Path) -> None:
        settings = _make_settings()
        writer = MemoryWriter(tmp_path, settings)
        target_date = date(2026, 2, 22)

        result = await writer.append_daily_note(
            "test", scope_key="main", source="user",
            source_session_id="telegram:peer:123", target_date=target_date,
        )

        content = result.projection_path.read_text(encoding="utf-8")
        assert "source_session_id: telegram:peer:123" in content

    @pytest.mark.asyncio
    async def test_no_source_session_id_when_none(self, tmp_path: Path) -> None:
        settings = _make_settings()
        writer = MemoryWriter(tmp_path, settings)
        target_date = date(2026, 2, 22)

        result = await writer.append_daily_note(
            "test", scope_key="main", source="user", target_date=target_date
        )

        content = result.projection_path.read_text(encoding="utf-8")
        assert "source_session_id" not in content

    @pytest.mark.asyncio
    async def test_unique_entry_ids_per_write(self, tmp_path: Path) -> None:
        settings = _make_settings()
        writer = MemoryWriter(tmp_path, settings)
        target_date = date(2026, 2, 22)

        await writer.append_daily_note(
            "first", scope_key="main", source="user", target_date=target_date
        )
        await writer.append_daily_note(
            "second", scope_key="main", source="user", target_date=target_date
        )

        path = tmp_path / "memory" / "2026-02-22.md"
        content = path.read_text(encoding="utf-8")
        ids = re.findall(r"entry_id:\s*([\w-]+)", content)
        assert len(ids) == 2
        assert ids[0] != ids[1]

    @pytest.mark.asyncio
    async def test_entry_id_in_result(self, tmp_path: Path) -> None:
        settings = _make_settings()
        writer = MemoryWriter(tmp_path, settings)

        result = await writer.append_daily_note(
            "test", scope_key="main", source="user", target_date=date(2026, 2, 22),
        )
        assert result.entry_id is not None
        assert len(result.entry_id) == 36


# ── Ledger-wired mode (P2-M2d) ──


class TestLedgerWiredMode:
    @pytest.mark.asyncio
    async def test_writes_to_ledger_then_file(self, tmp_path: Path) -> None:
        settings = _make_settings()
        ledger = _make_mock_ledger(return_value=True)
        writer = MemoryWriter(tmp_path, settings, ledger=ledger)

        result = await writer.append_daily_note(
            "hello", scope_key="main", source="user", target_date=date(2026, 2, 22),
        )

        assert result.ledger_written is True
        assert result.projection_written is True
        assert result.projection_path is not None
        assert result.projection_path.exists()
        ledger.append.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ledger_failure_blocks_write(self, tmp_path: Path) -> None:
        settings = _make_settings()
        ledger = _make_mock_ledger(side_effect=LedgerWriteError("db down"))
        writer = MemoryWriter(tmp_path, settings, ledger=ledger)

        with pytest.raises(LedgerWriteError):
            await writer.append_daily_note(
                "hello", scope_key="main", source="user",
                target_date=date(2026, 2, 22),
            )

        # Projection should NOT have been written
        daily_note = tmp_path / "memory" / "2026-02-22.md"
        assert not daily_note.exists()

    @pytest.mark.asyncio
    async def test_projection_size_limit_skip(self, tmp_path: Path) -> None:
        settings = _make_settings(max_daily_note_bytes=10)
        ledger = _make_mock_ledger(return_value=True)
        writer = MemoryWriter(tmp_path, settings, ledger=ledger)

        result = await writer.append_daily_note(
            "A very long note that exceeds the tiny limit",
            scope_key="main", source="user", target_date=date(2026, 2, 22),
        )

        # Ledger succeeds, projection skipped due to size
        assert result.ledger_written is True
        assert result.projection_written is False
        assert result.projection_path is None

    @pytest.mark.asyncio
    async def test_idempotent_noop(self, tmp_path: Path) -> None:
        settings = _make_settings()
        ledger = _make_mock_ledger(return_value=False)  # duplicate
        writer = MemoryWriter(tmp_path, settings, ledger=ledger)

        result = await writer.append_daily_note(
            "dup", scope_key="main", source="user", target_date=date(2026, 2, 22),
        )

        assert result.ledger_written is False
        assert result.projection_written is False
        assert result.projection_path is None

    @pytest.mark.asyncio
    async def test_flush_candidates_ledger_wired(self, tmp_path: Path) -> None:
        settings = _make_settings()
        ledger = _make_mock_ledger(return_value=True)
        writer = MemoryWriter(tmp_path, settings, ledger=ledger)

        candidates = [
            ResolvedFlushCandidate(
                candidate_text="flushed", scope_key="main",
                source_session_id="s1", confidence=0.9,
            ),
        ]

        written = await writer.process_flush_candidates(candidates)
        assert written == 1
        assert ledger.append.await_count == 1

    @pytest.mark.asyncio
    async def test_flush_stops_on_ledger_error(self, tmp_path: Path) -> None:
        settings = _make_settings()
        ledger = _make_mock_ledger(side_effect=LedgerWriteError("db down"))
        writer = MemoryWriter(tmp_path, settings, ledger=ledger)

        candidates = [
            ResolvedFlushCandidate(
                candidate_text="note", scope_key="main",
                source_session_id="s1", confidence=0.9,
            ),
        ]

        written = await writer.process_flush_candidates(candidates)
        assert written == 0
