"""Tests for src/memory/ledger.py — MemoryLedgerWriter (mock session factory)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infra.errors import LedgerWriteError
from src.memory.ledger import MemoryLedgerWriter


def _make_session_factory(*, rows=None, scalar=None, exec_side_effect=None):
    """Create a mock async session factory that supports `async with factory() as db:`."""
    mock_result = MagicMock()
    if rows is not None:
        mock_result.fetchone.return_value = rows[0] if rows else None
        mock_result.__iter__ = lambda self: iter(rows)
    if scalar is not None:
        mock_result.scalar.return_value = scalar

    session = AsyncMock()
    if exec_side_effect:
        session.execute.side_effect = exec_side_effect
    else:
        session.execute.return_value = mock_result
    session.commit = AsyncMock()

    # async context manager: `async with factory() as db:`
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock()
    factory.return_value = ctx
    return factory, session


class TestAppend:
    @pytest.mark.asyncio
    async def test_append_returns_true_on_insert(self) -> None:
        row = MagicMock()
        row.event_id = "some-event-id"
        factory, _ = _make_session_factory(rows=[row])
        writer = MemoryLedgerWriter(factory)
        result = await writer.append(
            entry_id="test-entry", content="hello", source="user",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_append_returns_false_on_noop(self) -> None:
        factory, _ = _make_session_factory(rows=[])
        writer = MemoryLedgerWriter(factory)
        result = await writer.append(
            entry_id="dup-entry", content="hello", source="user",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_append_raises_ledger_write_error(self) -> None:
        factory, _ = _make_session_factory(exec_side_effect=Exception("db down"))
        writer = MemoryLedgerWriter(factory)
        with pytest.raises(LedgerWriteError, match="Failed to append"):
            await writer.append(entry_id="e1", content="x", source="user")

    @pytest.mark.asyncio
    async def test_append_passes_all_fields(self) -> None:
        row = MagicMock()
        row.event_id = "ev-1"
        factory, session = _make_session_factory(rows=[row])
        writer = MemoryLedgerWriter(factory)
        await writer.append(
            entry_id="e1", content="hello", scope_key="test-scope",
            source="compaction_flush", source_session_id="sess-42",
            metadata={"tag": "x"},
        )
        call_args = session.execute.call_args
        params = call_args[0][1]
        assert params["entry_id"] == "e1"
        assert params["content"] == "hello"
        assert params["scope_key"] == "test-scope"
        assert params["source"] == "compaction_flush"
        assert params["source_session_id"] == "sess-42"


class TestCount:
    @pytest.mark.asyncio
    async def test_count_all(self) -> None:
        factory, _ = _make_session_factory(scalar=5)
        writer = MemoryLedgerWriter(factory)
        assert await writer.count() == 5

    @pytest.mark.asyncio
    async def test_count_with_scope(self) -> None:
        factory, session = _make_session_factory(scalar=3)
        writer = MemoryLedgerWriter(factory)
        assert await writer.count(scope_key="test") == 3
        sql_text = str(session.execute.call_args[0][0])
        assert "scope_key" in sql_text


class TestListEntryIds:
    @pytest.mark.asyncio
    async def test_list_entry_ids(self) -> None:
        rows = [("e1",), ("e2",)]
        factory, _ = _make_session_factory(rows=rows)
        writer = MemoryLedgerWriter(factory)
        ids = await writer.list_entry_ids()
        assert ids == ["e1", "e2"]

    @pytest.mark.asyncio
    async def test_list_entry_ids_with_since(self) -> None:
        factory, session = _make_session_factory(rows=[])
        writer = MemoryLedgerWriter(factory)
        since = datetime(2026, 1, 1, tzinfo=UTC)
        await writer.list_entry_ids(since=since)
        sql_text = str(session.execute.call_args[0][0])
        assert "created_at" in sql_text


class TestGetEntriesForParity:
    @pytest.mark.asyncio
    async def test_get_entries_for_parity(self) -> None:
        row = MagicMock()
        row.entry_id = "e1"
        row.content = "hello"
        row.scope_key = "main"
        row.source = "user"
        row.source_session_id = "sess-1"
        factory, _ = _make_session_factory(rows=[row])
        writer = MemoryLedgerWriter(factory)
        result = await writer.get_entries_for_parity()
        assert "e1" in result
        assert result["e1"]["content"] == "hello"
        assert result["e1"]["scope_key"] == "main"
        assert result["e1"]["source"] == "user"
        assert result["e1"]["source_session_id"] == "sess-1"
