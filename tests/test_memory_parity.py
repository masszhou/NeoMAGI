"""Tests for src/memory/parity.py — MemoryParityChecker."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.memory.parity import MemoryParityChecker, ParityReport


def _make_ledger(entries: dict[str, dict] | None = None):
    """Create a mock MemoryLedgerWriter."""
    ledger = AsyncMock()
    ledger.get_entries_for_parity.return_value = entries or {}
    return ledger


def _write_daily_note(workspace: Path, date: str, entries: list[str]) -> None:
    """Write a daily note file with entries."""
    memory_dir = workspace / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    filepath = memory_dir / f"{date}.md"
    content = ""
    for entry_text in entries:
        content += entry_text
    filepath.write_text(content, encoding="utf-8")


def _make_entry_block(
    entry_id: str,
    text: str,
    source: str = "user",
    scope: str = "main",
    session_id: str | None = None,
) -> str:
    parts = [f"entry_id: {entry_id}", f"source: {source}", f"scope: {scope}"]
    if session_id:
        parts.append(f"source_session_id: {session_id}")
    meta = f"[10:00] ({', '.join(parts)})"
    return f"---\n{meta}\n{text}\n"


class TestParityReport:
    def test_consistent(self) -> None:
        report = ParityReport(ledger_count=2, workspace_count=2, matched=2)
        assert report.is_consistent is True

    def test_not_consistent_only_in_ledger(self) -> None:
        report = ParityReport(
            ledger_count=3, workspace_count=2, only_in_ledger=["e3"], matched=2,
        )
        assert report.is_consistent is False

    def test_not_consistent_content_mismatch(self) -> None:
        report = ParityReport(
            ledger_count=2, workspace_count=2, matched=2, content_mismatch=["e1"],
        )
        assert report.is_consistent is False


class TestMemoryParityChecker:
    @pytest.mark.asyncio
    async def test_consistent_state(self, tmp_path: Path) -> None:
        ledger = _make_ledger({
            "e1": {"content": "hello", "scope_key": "main", "source": "user",
                   "source_session_id": None,
                   "principal_id": None, "visibility": "private_to_principal"},
        })
        _write_daily_note(tmp_path, "2026-04-12", [
            _make_entry_block("e1", "hello"),
        ])
        checker = MemoryParityChecker(ledger, tmp_path)
        report = await checker.check()
        assert report.is_consistent is True
        assert report.matched == 1

    @pytest.mark.asyncio
    async def test_only_in_workspace(self, tmp_path: Path) -> None:
        ledger = _make_ledger({})
        _write_daily_note(tmp_path, "2026-04-12", [
            _make_entry_block("e1", "hello"),
        ])
        checker = MemoryParityChecker(ledger, tmp_path)
        report = await checker.check()
        assert report.only_in_workspace == ["e1"]
        assert report.is_consistent is False

    @pytest.mark.asyncio
    async def test_only_in_ledger(self, tmp_path: Path) -> None:
        ledger = _make_ledger({
            "e1": {"content": "hello", "scope_key": "main", "source": "user",
                   "source_session_id": None,
                   "principal_id": None, "visibility": "private_to_principal"},
        })
        checker = MemoryParityChecker(ledger, tmp_path)
        report = await checker.check()
        assert report.only_in_ledger == ["e1"]
        assert report.is_consistent is False

    @pytest.mark.asyncio
    async def test_empty_both(self, tmp_path: Path) -> None:
        ledger = _make_ledger({})
        checker = MemoryParityChecker(ledger, tmp_path)
        report = await checker.check()
        assert report.is_consistent is True
        assert report.matched == 0

    @pytest.mark.asyncio
    async def test_content_mismatch(self, tmp_path: Path) -> None:
        ledger = _make_ledger({
            "e1": {"content": "original", "scope_key": "main", "source": "user",
                   "source_session_id": None,
                   "principal_id": None, "visibility": "private_to_principal"},
        })
        _write_daily_note(tmp_path, "2026-04-12", [
            _make_entry_block("e1", "modified"),
        ])
        checker = MemoryParityChecker(ledger, tmp_path)
        report = await checker.check()
        assert report.content_mismatch == ["e1"]
        assert report.is_consistent is False

    @pytest.mark.asyncio
    async def test_metadata_mismatch(self, tmp_path: Path) -> None:
        ledger = _make_ledger({
            "e1": {"content": "hello", "scope_key": "other", "source": "user",
                   "source_session_id": None,
                   "principal_id": None, "visibility": "private_to_principal"},
        })
        _write_daily_note(tmp_path, "2026-04-12", [
            _make_entry_block("e1", "hello", scope="main"),
        ])
        checker = MemoryParityChecker(ledger, tmp_path)
        report = await checker.check()
        assert report.metadata_mismatch == ["e1"]
        assert report.is_consistent is False

    @pytest.mark.asyncio
    async def test_skips_entries_without_entry_id(self, tmp_path: Path) -> None:
        ledger = _make_ledger({})
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        filepath = memory_dir / "2026-04-12.md"
        filepath.write_text("---\n[10:00] old note without entry_id\n", encoding="utf-8")
        checker = MemoryParityChecker(ledger, tmp_path)
        report = await checker.check()
        assert report.is_consistent is True
        assert report.workspace_count == 0

    @pytest.mark.asyncio
    async def test_content_and_metadata_mismatch_both_reported(self, tmp_path: Path) -> None:
        """Both content and metadata drift on same entry must both be reported."""
        ledger = _make_ledger({
            "e1": {"content": "original", "scope_key": "other", "source": "user",
                   "source_session_id": None,
                   "principal_id": None, "visibility": "private_to_principal"},
        })
        _write_daily_note(tmp_path, "2026-04-12", [
            _make_entry_block("e1", "modified", scope="main"),
        ])
        checker = MemoryParityChecker(ledger, tmp_path)
        report = await checker.check()
        assert "e1" in report.content_mismatch
        assert "e1" in report.metadata_mismatch

    @pytest.mark.asyncio
    async def test_scope_filter_excludes_other_scopes(self, tmp_path: Path) -> None:
        """Scoped check should not report entries from other scopes as only_in_workspace."""
        ledger = _make_ledger({
            "e1": {"content": "hello", "scope_key": "target", "source": "user",
                   "source_session_id": None,
                   "principal_id": None, "visibility": "private_to_principal"},
        })
        _write_daily_note(tmp_path, "2026-04-12", [
            _make_entry_block("e1", "hello", scope="target"),
            _make_entry_block("e2", "other scope entry", scope="other"),
        ])
        checker = MemoryParityChecker(ledger, tmp_path)
        report = await checker.check(scope_key="target")
        assert report.is_consistent is True
        assert report.workspace_count == 1  # e2 excluded by scope filter
