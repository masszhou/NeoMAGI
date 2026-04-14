"""Retrieval regression tests (P2-M3c, Slice A).

Fixture-driven tests using real PostgreSQL search to verify retrieval quality.
Each case inserts indexed_entries, runs MemorySearcher.search(), and asserts
that expected_entry_ids are present in results.

Categories: cjk_tokenization, synonym, semantic_gap, partial_match.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.constants import DB_SCHEMA
from src.memory.models import MemoryEntry
from src.memory.query_processor import segment_for_index
from src.memory.searcher import MemorySearcher

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "retrieval_regression" / "cases.json"

# Known miss categories that are expected to fail before vector retrieval / query expansion
_XFAIL_CATEGORIES = {"synonym", "semantic_gap"}
# Individual case IDs that are known misses due to AND-mode partial mismatch
_XFAIL_CASE_IDS = {"cjk_long_query_01"}


def _load_cases() -> list[dict]:
    with FIXTURE_PATH.open() as f:
        data = json.load(f)
    return data["cases"]


def _case_ids() -> list[str]:
    return [c["id"] for c in _load_cases()]


_CASES = _load_cases()


@pytest.fixture(scope="module")
def memory_settings():
    """Minimal MemorySettings stub for MemorySearcher."""
    from unittest.mock import MagicMock
    settings = MagicMock()
    settings.max_search_results = 20
    return settings


@pytest_asyncio.fixture(scope="session")
async def _ensure_search_trigger(db_engine):
    """Ensure the search vector trigger exists (conftest only creates tables)."""
    from src.session.database import _create_search_trigger
    async with db_engine.begin() as conn:
        await _create_search_trigger(conn, DB_SCHEMA)


@pytest_asyncio.fixture
async def clean_memory_entries(
    db_session_factory: async_sessionmaker[AsyncSession],
    _ensure_search_trigger,
):
    """Ensure memory_entries is empty before each case."""
    async with db_session_factory() as db:
        await db.execute(text(f"DELETE FROM {DB_SCHEMA}.memory_entries"))
        await db.commit()
    yield


@pytest.mark.integration
@pytest.mark.retrieval_regression
@pytest.mark.parametrize("case", _CASES, ids=_case_ids())
async def test_retrieval_case(
    case: dict,
    db_session_factory: async_sessionmaker[AsyncSession],
    memory_settings,
    clean_memory_entries,
) -> None:
    """Run a single retrieval regression case against real PostgreSQL."""
    # Insert indexed entries with Jieba-segmented search_text
    async with db_session_factory() as db:
        for entry_data in case["indexed_entries"]:
            content = entry_data["content"]
            entry = MemoryEntry(
                entry_id=entry_data["entry_id"],
                scope_key=entry_data.get("scope_key", "main"),
                source_type="daily_note",
                source_path=None,
                source_date=None,
                title=entry_data.get("title", ""),
                content=content,
                search_text=segment_for_index(content),
                tags=[],
                confidence=None,
            )
            db.add(entry)
        await db.commit()

    # Build content→fixture_id lookup for matching
    # (MemorySearchResult.entry_id is the PK int, not the string entry_id)
    content_to_fixture_id = {
        e["content"]: e["entry_id"] for e in case["indexed_entries"]
    }

    # Execute search
    searcher = MemorySearcher(db_session_factory, memory_settings)
    results = await searcher.search(
        case["query"],
        scope_key=case["indexed_entries"][0].get("scope_key", "main"),
    )
    found_fixture_ids = {
        content_to_fixture_id[r.content]
        for r in results
        if r.content in content_to_fixture_id
    }

    expected = set(case["expected_entry_ids"])
    missing = expected - found_fixture_ids

    if case["category"] in _XFAIL_CATEGORIES or case["id"] in _XFAIL_CASE_IDS:
        if missing:
            pytest.xfail(
                f"Known {case['category']} miss: {missing} not found "
                f"(results: {found_fixture_ids})"
            )
    else:
        assert not missing, (
            f"Missing expected entries: {missing}. "
            f"Got: {found_fixture_ids}. "
            f"Category: {case['category']}. "
            f"Query: {case['query']}"
        )
