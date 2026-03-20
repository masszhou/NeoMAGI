"""Tests for WrapperToolStore (P2-M1c).

Covers: store operations using mock DB session.
Uses AsyncMock — no real DB required.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.growth.types import (
    GrowthEvalResult,
    GrowthLifecycleStatus,
    GrowthObjectKind,
    GrowthProposal,
)
from src.wrappers.store import (
    WrapperToolProposalRecord,
    WrapperToolStore,
    _row_to_proposal_record,
    _row_to_spec,
)
from src.wrappers.types import WrapperToolSpec

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec(**overrides: object) -> WrapperToolSpec:
    defaults = {
        "id": "wt-001",
        "capability": "file_summarizer",
        "version": 1,
        "summary": "Summarizes a file",
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "implementation_ref": "src.wrappers.builtins:factory",
        "deny_semantics": ("no_write",),
    }
    defaults.update(overrides)
    return WrapperToolSpec(**defaults)  # type: ignore[arg-type]


def _make_proposal(**overrides: object) -> GrowthProposal:
    spec = _make_spec()
    defaults: dict = {
        "object_kind": GrowthObjectKind.wrapper_tool,
        "object_id": "wt-001",
        "intent": "Create wrapper tool",
        "risk_notes": "Low risk",
        "diff_summary": "New wrapper tool",
        "payload": {"wrapper_tool_spec": spec.model_dump()},
    }
    defaults.update(overrides)
    return GrowthProposal(**defaults)


def _make_mock_db_factory():
    """Create a mock async session factory."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock()
    factory.return_value = mock_session

    return factory, mock_session


def _make_row_mock(**kwargs):
    """Create a mock DB row."""
    row = MagicMock()
    for k, v in kwargs.items():
        setattr(row, k, v)
    return row


# ---------------------------------------------------------------------------
# Row mapper tests
# ---------------------------------------------------------------------------


class TestRowToSpec:
    def test_converts_row(self) -> None:
        row = _make_row_mock(
            id="wt-001",
            capability="test",
            version=1,
            summary="Test wrapper",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            bound_atomic_tools=["read_file"],
            implementation_ref="mod:factory",
            deny_semantics=["no_write"],
            scope_claim="local",
            disabled=False,
        )
        spec = _row_to_spec(row)
        assert isinstance(spec, WrapperToolSpec)
        assert spec.id == "wt-001"
        assert spec.bound_atomic_tools == ("read_file",)
        assert spec.deny_semantics == ("no_write",)

    def test_handles_none_arrays(self) -> None:
        row = _make_row_mock(
            id="wt-002",
            capability="test",
            version=1,
            summary="Test",
            input_schema={},
            output_schema={},
            bound_atomic_tools=None,
            implementation_ref="mod:f",
            deny_semantics=None,
            scope_claim="local",
            disabled=False,
        )
        spec = _row_to_spec(row)
        assert spec.bound_atomic_tools == ()
        assert spec.deny_semantics == ()


class TestRowToProposalRecord:
    def test_converts_row(self) -> None:
        row = _make_row_mock(
            governance_version=1,
            wrapper_tool_id="wt-001",
            status="proposed",
            proposal={"intent": "create"},
            eval_result=None,
            created_by="agent",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            applied_at=None,
            rolled_back_from=None,
        )
        record = _row_to_proposal_record(row)
        assert isinstance(record, WrapperToolProposalRecord)
        assert record.governance_version == 1
        assert record.wrapper_tool_id == "wt-001"


# ---------------------------------------------------------------------------
# Store method tests (mock DB)
# ---------------------------------------------------------------------------


class TestUpsertActive:
    @pytest.mark.asyncio
    async def test_standalone_session(self) -> None:
        factory, mock_session = _make_mock_db_factory()
        store = WrapperToolStore(factory)
        spec = _make_spec()
        await store.upsert_active(spec)
        mock_session.execute.assert_awaited_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_with_external_session(self) -> None:
        factory, _ = _make_mock_db_factory()
        store = WrapperToolStore(factory)
        spec = _make_spec()
        ext_session = AsyncMock()
        await store.upsert_active(spec, session=ext_session)
        ext_session.execute.assert_awaited_once()


class TestGetActive:
    @pytest.mark.asyncio
    async def test_list_all(self) -> None:
        factory, mock_session = _make_mock_db_factory()
        row = _make_row_mock(
            id="wt-001",
            capability="test",
            version=1,
            summary="Test",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            bound_atomic_tools=[],
            implementation_ref="mod:f",
            deny_semantics=["no_write"],
            scope_claim="local",
            disabled=False,
        )
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([row]))
        mock_session.execute = AsyncMock(return_value=mock_result)
        store = WrapperToolStore(factory)

        result = await store.get_active()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].id == "wt-001"

    @pytest.mark.asyncio
    async def test_get_by_id(self) -> None:
        factory, mock_session = _make_mock_db_factory()
        row = _make_row_mock(
            id="wt-001",
            capability="test",
            version=1,
            summary="Test",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            bound_atomic_tools=[],
            implementation_ref="mod:f",
            deny_semantics=["no_write"],
            scope_claim="local",
            disabled=False,
        )
        mock_result = MagicMock()
        mock_result.first.return_value = row
        mock_session.execute = AsyncMock(return_value=mock_result)
        store = WrapperToolStore(factory)

        result = await store.get_active(wrapper_tool_id="wt-001")
        assert isinstance(result, WrapperToolSpec)
        assert result.id == "wt-001"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self) -> None:
        factory, mock_session = _make_mock_db_factory()
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        store = WrapperToolStore(factory)

        result = await store.get_active(wrapper_tool_id="nonexistent")
        assert result is None


class TestRemoveActive:
    @pytest.mark.asyncio
    async def test_standalone_session(self) -> None:
        factory, mock_session = _make_mock_db_factory()
        store = WrapperToolStore(factory)
        await store.remove_active("wt-001")
        mock_session.execute.assert_awaited_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_with_external_session(self) -> None:
        factory, _ = _make_mock_db_factory()
        store = WrapperToolStore(factory)
        ext_session = AsyncMock()
        await store.remove_active("wt-001", session=ext_session)
        ext_session.execute.assert_awaited_once()


class TestCreateProposal:
    @pytest.mark.asyncio
    async def test_returns_governance_version(self) -> None:
        factory, mock_session = _make_mock_db_factory()
        mock_result = MagicMock()
        mock_row = MagicMock()
        mock_row.governance_version = 42
        mock_result.first.return_value = mock_row
        mock_session.execute = AsyncMock(return_value=mock_result)
        store = WrapperToolStore(factory)

        proposal = _make_proposal()
        gv = await store.create_proposal(proposal)
        assert gv == 42

    @pytest.mark.asyncio
    async def test_with_external_session(self) -> None:
        factory, _ = _make_mock_db_factory()
        store = WrapperToolStore(factory)
        ext_session = AsyncMock()
        mock_row = MagicMock()
        mock_row.governance_version = 7
        mock_result = MagicMock()
        mock_result.first.return_value = mock_row
        ext_session.execute = AsyncMock(return_value=mock_result)

        proposal = _make_proposal()
        gv = await store.create_proposal(proposal, session=ext_session)
        assert gv == 7
        ext_session.execute.assert_awaited_once()


class TestGetProposal:
    @pytest.mark.asyncio
    async def test_found(self) -> None:
        factory, mock_session = _make_mock_db_factory()
        row = _make_row_mock(
            governance_version=1,
            wrapper_tool_id="wt-001",
            status="proposed",
            proposal={"intent": "create"},
            eval_result=None,
            created_by="agent",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            applied_at=None,
            rolled_back_from=None,
        )
        mock_result = MagicMock()
        mock_result.first.return_value = row
        mock_session.execute = AsyncMock(return_value=mock_result)
        store = WrapperToolStore(factory)

        record = await store.get_proposal(1)
        assert record is not None
        assert record.governance_version == 1

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        factory, mock_session = _make_mock_db_factory()
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        store = WrapperToolStore(factory)

        record = await store.get_proposal(999)
        assert record is None


class TestStoreEvalResult:
    @pytest.mark.asyncio
    async def test_persists(self) -> None:
        factory, mock_session = _make_mock_db_factory()
        store = WrapperToolStore(factory)
        result = GrowthEvalResult(
            passed=True,
            summary="All checks passed",
            contract_id="wrapper_tool_eval_v1",
            contract_version=1,
        )
        await store.store_eval_result(1, result)
        mock_session.execute.assert_awaited_once()
        mock_session.commit.assert_awaited_once()


class TestUpdateProposalStatus:
    @pytest.mark.asyncio
    async def test_standalone(self) -> None:
        factory, mock_session = _make_mock_db_factory()
        store = WrapperToolStore(factory)
        await store.update_proposal_status(1, GrowthLifecycleStatus.active)
        mock_session.execute.assert_awaited_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_with_session(self) -> None:
        factory, _ = _make_mock_db_factory()
        store = WrapperToolStore(factory)
        ext_session = AsyncMock()
        await store.update_proposal_status(1, GrowthLifecycleStatus.active, session=ext_session)
        ext_session.execute.assert_awaited_once()


class TestFindLastApplied:
    @pytest.mark.asyncio
    async def test_found(self) -> None:
        factory, mock_session = _make_mock_db_factory()
        row = _make_row_mock(
            governance_version=5,
            wrapper_tool_id="wt-001",
            status="active",
            proposal={"intent": "update"},
            eval_result={"passed": True},
            created_by="agent",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            applied_at=datetime(2026, 1, 2, tzinfo=UTC),
            rolled_back_from=None,
        )
        mock_result = MagicMock()
        mock_result.first.return_value = row
        mock_session.execute = AsyncMock(return_value=mock_result)
        store = WrapperToolStore(factory)

        record = await store.find_last_applied("wt-001")
        assert record is not None
        assert record.governance_version == 5

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        factory, mock_session = _make_mock_db_factory()
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        store = WrapperToolStore(factory)

        record = await store.find_last_applied("nonexistent")
        assert record is None
