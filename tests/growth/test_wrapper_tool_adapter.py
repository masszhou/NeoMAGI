"""Tests for WrapperToolGovernedObjectAdapter (growth governance kernel, P2-M1c).

Covers: kind property, Protocol conformance, propose/evaluate/apply/rollback/veto/get_active,
eval checks (typed_io_validation, permission_boundary, dry_run_smoke,
before_after_cases, scope_claim_consistency), payload validation, error paths,
and single-transaction atomicity of apply/rollback.

Uses mock WrapperToolStore (AsyncMock) — no real DB required.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.growth.adapters.base import GovernedObjectAdapter
from src.growth.adapters.wrapper_tool import (
    WrapperToolGovernedObjectAdapter,
    _check_before_after_cases,
    _check_dry_run_smoke,
    _check_permission_boundary,
    _check_scope_claim_consistency,
    _check_typed_io_validation,
)
from src.growth.types import (
    GrowthEvalResult,
    GrowthLifecycleStatus,
    GrowthObjectKind,
    GrowthProposal,
)
from src.wrappers.store import WrapperToolProposalRecord
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
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {"summary": {"type": "string"}}},
        "implementation_ref": "json:loads",  # stdlib, always importable
        "deny_semantics": ("no_write", "no_delete"),
        "bound_atomic_tools": ("read_file",),
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
        "payload": {
            "wrapper_tool_spec": spec.model_dump(),
            "smoke_test_results": {"passed": True},
        },
    }
    defaults.update(overrides)
    return GrowthProposal(**defaults)


def _make_proposal_record(
    *,
    governance_version: int = 1,
    status: str = "proposed",
    eval_passed: bool | None = None,
    spec: WrapperToolSpec | None = None,
) -> WrapperToolProposalRecord:
    spec = spec or _make_spec()
    eval_result = None
    if eval_passed is not None:
        eval_result = {"passed": eval_passed}
    return WrapperToolProposalRecord(
        governance_version=governance_version,
        wrapper_tool_id=spec.id,
        status=status,
        proposal={
            "intent": "Create wrapper tool",
            "payload": {
                "wrapper_tool_spec": spec.model_dump(),
                "smoke_test_results": {"passed": True},
            },
        },
        eval_result=eval_result,
        created_by="agent",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        applied_at=None,
        rolled_back_from=None,
    )


@pytest.fixture()
def mock_store() -> AsyncMock:
    store = AsyncMock()
    store.create_proposal = AsyncMock(return_value=1)
    store.get_proposal = AsyncMock(return_value=_make_proposal_record())
    store.store_eval_result = AsyncMock()
    store.update_proposal_status = AsyncMock()
    store.upsert_active = AsyncMock()
    store.remove_active = AsyncMock()
    store.find_last_applied = AsyncMock(return_value=None)
    store.get_active = AsyncMock(return_value=[_make_spec()])

    mock_session = MagicMock(name="mock_db_session")

    @asynccontextmanager
    async def _fake_transaction():
        yield mock_session

    store.transaction = _fake_transaction
    store._mock_session = mock_session
    return store


@pytest.fixture()
def mock_registry() -> MagicMock:
    registry = MagicMock()
    registry.replace = MagicMock()
    registry.unregister = MagicMock()
    return registry


@pytest.fixture()
def adapter(mock_store: AsyncMock, mock_registry: MagicMock) -> WrapperToolGovernedObjectAdapter:
    return WrapperToolGovernedObjectAdapter(mock_store, mock_registry)


# ---------------------------------------------------------------------------
# Kind + Protocol
# ---------------------------------------------------------------------------


class TestKind:
    def test_kind_is_wrapper_tool(self, adapter: WrapperToolGovernedObjectAdapter) -> None:
        assert adapter.kind == GrowthObjectKind.wrapper_tool


class TestProtocolConformance:
    def test_isinstance_governed_object_adapter(
        self, adapter: WrapperToolGovernedObjectAdapter
    ) -> None:
        assert isinstance(adapter, GovernedObjectAdapter)


# ---------------------------------------------------------------------------
# Propose
# ---------------------------------------------------------------------------


class TestPropose:
    @pytest.mark.asyncio
    async def test_creates_proposal(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
    ) -> None:
        proposal = _make_proposal()
        gv = await adapter.propose(proposal)
        assert gv == 1
        mock_store.create_proposal.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_missing_wrapper_tool_spec_raises(
        self, adapter: WrapperToolGovernedObjectAdapter
    ) -> None:
        proposal = _make_proposal(payload={})
        with pytest.raises(ValueError, match="wrapper_tool_spec"):
            await adapter.propose(proposal)

    @pytest.mark.asyncio
    async def test_invalid_spec_dict_raises(
        self, adapter: WrapperToolGovernedObjectAdapter
    ) -> None:
        proposal = _make_proposal(payload={"wrapper_tool_spec": "not-a-dict"})
        with pytest.raises(ValueError, match="wrapper_tool_spec"):
            await adapter.propose(proposal)


# ---------------------------------------------------------------------------
# Evaluate
# ---------------------------------------------------------------------------


class TestEvaluate:
    @pytest.mark.asyncio
    async def test_passes_valid_proposal(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
    ) -> None:
        result = await adapter.evaluate(1)
        assert isinstance(result, GrowthEvalResult)
        assert result.passed is True
        assert result.contract_id == "wrapper_tool_eval_v1"
        assert result.contract_version == 1
        assert len(result.checks) == 5

    @pytest.mark.asyncio
    async def test_not_found(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
    ) -> None:
        mock_store.get_proposal = AsyncMock(return_value=None)
        result = await adapter.evaluate(999)
        assert result.passed is False
        assert "not found" in result.summary

    @pytest.mark.asyncio
    async def test_wrong_status(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
    ) -> None:
        mock_store.get_proposal = AsyncMock(return_value=_make_proposal_record(status="active"))
        result = await adapter.evaluate(1)
        assert result.passed is False
        assert "not 'proposed'" in result.summary

    @pytest.mark.asyncio
    async def test_stores_eval_result(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
    ) -> None:
        await adapter.evaluate(1)
        mock_store.store_eval_result.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_bad_payload_returns_failed(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
    ) -> None:
        bad_record = WrapperToolProposalRecord(
            governance_version=1,
            wrapper_tool_id="wt-001",
            status="proposed",
            proposal={"payload": {"wrapper_tool_spec": {"invalid": True}}},
            eval_result=None,
            created_by="agent",
            created_at=None,
            applied_at=None,
            rolled_back_from=None,
        )
        mock_store.get_proposal = AsyncMock(return_value=bad_record)
        result = await adapter.evaluate(1)
        assert result.passed is False
        assert "parse error" in result.summary.lower()


# ---------------------------------------------------------------------------
# Eval check functions (unit tests)
# ---------------------------------------------------------------------------


class TestCheckTypedIoValidation:
    def test_valid(self) -> None:
        spec = _make_spec()
        result = _check_typed_io_validation(spec)
        assert result["passed"] is True

    def test_input_schema_missing_type(self) -> None:
        spec = _make_spec(input_schema={"properties": {}})
        result = _check_typed_io_validation(spec)
        assert result["passed"] is False
        assert "type" in result["detail"]

    def test_output_schema_missing_type(self) -> None:
        spec = _make_spec(output_schema={})
        result = _check_typed_io_validation(spec)
        assert result["passed"] is False
        assert "type" in result["detail"]

    def test_empty_id(self) -> None:
        spec = _make_spec(id="")
        result = _check_typed_io_validation(spec)
        assert result["passed"] is False
        assert "id is empty" in result["detail"]

    def test_version_zero(self) -> None:
        spec = _make_spec(version=0)
        result = _check_typed_io_validation(spec)
        assert result["passed"] is False
        assert "version must be >= 1" in result["detail"]


class TestCheckPermissionBoundary:
    def test_valid(self) -> None:
        spec = _make_spec(deny_semantics=("no_write", "no_delete"))
        result = _check_permission_boundary(spec)
        assert result["passed"] is True

    def test_empty_deny_semantics(self) -> None:
        spec = _make_spec(deny_semantics=())
        result = _check_permission_boundary(spec)
        assert result["passed"] is False
        assert "empty" in result["detail"]

    def test_blank_entry(self) -> None:
        spec = _make_spec(deny_semantics=("no_write", "  "))
        result = _check_permission_boundary(spec)
        assert result["passed"] is False
        assert "empty entry" in result["detail"]


class TestCheckDryRunSmoke:
    def test_valid_stdlib_module(self) -> None:
        spec = _make_spec(implementation_ref="json:loads")
        result = _check_dry_run_smoke(spec)
        assert result["passed"] is True

    def test_invalid_format(self) -> None:
        spec = _make_spec(implementation_ref="no_colon_here")
        result = _check_dry_run_smoke(spec)
        assert result["passed"] is False
        assert "pattern" in result["detail"]

    def test_unimportable_module(self) -> None:
        spec = _make_spec(implementation_ref="nonexistent_module_xyz:factory")
        result = _check_dry_run_smoke(spec)
        assert result["passed"] is False
        assert "Cannot import" in result["detail"]

    def test_nested_module(self) -> None:
        spec = _make_spec(implementation_ref="os.path:join")
        result = _check_dry_run_smoke(spec)
        assert result["passed"] is True


class TestCheckBeforeAfterCases:
    def test_with_smoke_test_results(self) -> None:
        result = _check_before_after_cases({"smoke_test_results": {"passed": True}})
        assert result["passed"] is True

    def test_with_before_after(self) -> None:
        result = _check_before_after_cases({"before_after": [{"input": "x"}]})
        assert result["passed"] is True

    def test_with_evidence(self) -> None:
        result = _check_before_after_cases({"evidence": "manual test"})
        assert result["passed"] is True

    def test_missing_all_evidence(self) -> None:
        result = _check_before_after_cases({})
        assert result["passed"] is False
        assert "No before/after" in result["detail"]


class TestCheckScopeClaimConsistency:
    def test_local_always_passes(self) -> None:
        spec = _make_spec(scope_claim="local", bound_atomic_tools=())
        result = _check_scope_claim_consistency(spec)
        assert result["passed"] is True

    def test_reusable_needs_bound_tools(self) -> None:
        spec = _make_spec(scope_claim="reusable", bound_atomic_tools=())
        result = _check_scope_claim_consistency(spec)
        assert result["passed"] is False

    def test_reusable_with_bound_tools(self) -> None:
        spec = _make_spec(scope_claim="reusable", bound_atomic_tools=("read_file",))
        result = _check_scope_claim_consistency(spec)
        assert result["passed"] is True

    def test_invalid_scope_claim(self) -> None:
        spec = _make_spec(scope_claim="global")
        result = _check_scope_claim_consistency(spec)
        assert result["passed"] is False
        assert "not in" in result["detail"]


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


class TestApply:
    @pytest.mark.asyncio
    async def test_materializes_and_activates(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
        mock_registry: MagicMock,
    ) -> None:
        mock_store.get_proposal = AsyncMock(return_value=_make_proposal_record(eval_passed=True))
        with patch("src.growth.adapters.wrapper_tool._resolve_and_register"):
            await adapter.apply(1)
        mock_store.upsert_active.assert_awaited_once()
        mock_store.update_proposal_status.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_passes_session_to_store_methods(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
    ) -> None:
        mock_store.get_proposal = AsyncMock(return_value=_make_proposal_record(eval_passed=True))
        with patch("src.growth.adapters.wrapper_tool._resolve_and_register"):
            await adapter.apply(1)
        session = mock_store._mock_session
        upsert_call = mock_store.upsert_active.call_args
        assert upsert_call.kwargs.get("session") is session
        status_call = mock_store.update_proposal_status.call_args
        assert status_call.kwargs.get("session") is session

    @pytest.mark.asyncio
    async def test_not_found_raises(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
    ) -> None:
        mock_store.get_proposal = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="not found"):
            await adapter.apply(999)

    @pytest.mark.asyncio
    async def test_wrong_status_raises(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
    ) -> None:
        mock_store.get_proposal = AsyncMock(return_value=_make_proposal_record(status="active"))
        with pytest.raises(ValueError, match="status is"):
            await adapter.apply(1)

    @pytest.mark.asyncio
    async def test_eval_not_passed_raises(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
    ) -> None:
        mock_store.get_proposal = AsyncMock(return_value=_make_proposal_record(eval_passed=False))
        with pytest.raises(ValueError, match="eval not passed"):
            await adapter.apply(1)


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


class TestRollback:
    @pytest.mark.asyncio
    async def test_no_previous_disables_and_unregisters(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
        mock_registry: MagicMock,
    ) -> None:
        mock_store.find_last_applied = AsyncMock(return_value=None)
        gv = await adapter.rollback(wrapper_tool_id="wt-001")
        assert isinstance(gv, int)
        mock_store.remove_active.assert_awaited_once()
        mock_registry.unregister.assert_called_once_with("wt-001")
        session = mock_store._mock_session
        remove_call = mock_store.remove_active.call_args
        assert remove_call.kwargs.get("session") is session

    @pytest.mark.asyncio
    async def test_with_current_active_disables_and_unregisters(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
        mock_registry: MagicMock,
    ) -> None:
        """When an active version exists, rollback disables it and unregisters."""
        current = _make_proposal_record(governance_version=2, status="active")
        mock_store.find_last_applied = AsyncMock(return_value=current)
        gv = await adapter.rollback(wrapper_tool_id="wt-001")
        assert isinstance(gv, int)
        mock_store.remove_active.assert_awaited_once()
        mock_store.update_proposal_status.assert_any_await(
            2, GrowthLifecycleStatus.rolled_back, session=mock_store._mock_session
        )
        mock_registry.unregister.assert_called_once_with("wt-001")

    @pytest.mark.asyncio
    async def test_rollback_passes_session_to_all_writes(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
    ) -> None:
        current = _make_proposal_record(governance_version=2, status="active")
        mock_store.find_last_applied = AsyncMock(return_value=current)
        await adapter.rollback(wrapper_tool_id="wt-001")
        session = mock_store._mock_session
        remove_call = mock_store.remove_active.call_args
        assert remove_call.kwargs.get("session") is session
        for call in mock_store.update_proposal_status.call_args_list:
            assert call.kwargs.get("session") is session
        create_call = mock_store.create_proposal.call_args
        assert create_call.kwargs.get("session") is session

    @pytest.mark.asyncio
    async def test_missing_wrapper_tool_id_raises(
        self, adapter: WrapperToolGovernedObjectAdapter
    ) -> None:
        with pytest.raises(ValueError, match="wrapper_tool_id"):
            await adapter.rollback()

    @pytest.mark.asyncio
    async def test_unregister_skip_when_not_in_registry(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
        mock_registry: MagicMock,
    ) -> None:
        """Rollback with no previous version: unregister fails gracefully."""
        mock_store.find_last_applied = AsyncMock(return_value=None)
        mock_registry.unregister.side_effect = KeyError("not found")
        gv = await adapter.rollback(wrapper_tool_id="wt-ghost")
        assert isinstance(gv, int)


# ---------------------------------------------------------------------------
# Veto
# ---------------------------------------------------------------------------


class TestVeto:
    @pytest.mark.asyncio
    async def test_veto_proposed(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
    ) -> None:
        mock_store.get_proposal = AsyncMock(return_value=_make_proposal_record(status="proposed"))
        await adapter.veto(1)
        mock_store.update_proposal_status.assert_awaited_once()
        call_args = mock_store.update_proposal_status.call_args
        assert call_args[0][1] == GrowthLifecycleStatus.vetoed

    @pytest.mark.asyncio
    async def test_veto_active_triggers_rollback(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
    ) -> None:
        mock_store.get_proposal = AsyncMock(return_value=_make_proposal_record(status="active"))
        await adapter.veto(1)
        mock_store.find_last_applied.assert_awaited()

    @pytest.mark.asyncio
    async def test_veto_not_found_raises(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
    ) -> None:
        mock_store.get_proposal = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="not found"):
            await adapter.veto(999)

    @pytest.mark.asyncio
    async def test_veto_wrong_status_raises(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
    ) -> None:
        mock_store.get_proposal = AsyncMock(
            return_value=_make_proposal_record(status="rolled_back")
        )
        with pytest.raises(ValueError, match="Cannot veto"):
            await adapter.veto(1)


# ---------------------------------------------------------------------------
# GetActive
# ---------------------------------------------------------------------------


class TestGetActive:
    @pytest.mark.asyncio
    async def test_returns_list(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
    ) -> None:
        result = await adapter.get_active()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].id == "wt-001"
        mock_store.get_active.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_list(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
    ) -> None:
        mock_store.get_active = AsyncMock(return_value=[])
        result = await adapter.get_active()
        assert result == []


# ---------------------------------------------------------------------------
# Atomicity: apply/rollback partial-failure propagation
# ---------------------------------------------------------------------------


class TestApplyAtomicity:
    @pytest.mark.asyncio
    async def test_upsert_failure_propagates(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
    ) -> None:
        mock_store.get_proposal = AsyncMock(return_value=_make_proposal_record(eval_passed=True))
        mock_store.upsert_active = AsyncMock(side_effect=RuntimeError("DB write failed"))
        with pytest.raises(RuntimeError, match="DB write failed"):
            await adapter.apply(1)
        mock_store.update_proposal_status.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_registry_failure_triggers_compensation(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
    ) -> None:
        """[P2 regression] registry failure after DB commit must compensate DB."""
        mock_store.get_proposal = AsyncMock(return_value=_make_proposal_record(eval_passed=True))
        with patch(
            "src.growth.adapters.wrapper_tool._resolve_and_register",
            side_effect=RuntimeError("factory failed"),
        ):
            with pytest.raises(RuntimeError, match="factory failed"):
                await adapter.apply(1)
        # DB was committed then compensated: remove_active should be called
        assert mock_store.remove_active.await_count >= 1


class TestRollbackAtomicity:
    @pytest.mark.asyncio
    async def test_remove_failure_propagates(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
    ) -> None:
        mock_store.find_last_applied = AsyncMock(return_value=None)
        mock_store.remove_active = AsyncMock(side_effect=RuntimeError("DB write failed"))
        with pytest.raises(RuntimeError, match="DB write failed"):
            await adapter.rollback(wrapper_tool_id="wt-001")
        mock_store.create_proposal.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_proposal_failure_propagates(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
    ) -> None:
        mock_store.find_last_applied = AsyncMock(return_value=None)
        mock_store.create_proposal = AsyncMock(side_effect=RuntimeError("Insert failed"))
        with pytest.raises(RuntimeError, match="Insert failed"):
            await adapter.rollback(wrapper_tool_id="wt-001")
        mock_store.remove_active.assert_awaited_once()


# ---------------------------------------------------------------------------
# Post-review regressions: rollback, name binding, compensating semantics
# ---------------------------------------------------------------------------


class TestPostReviewRegressions:
    """Regression tests for findings [P1] rollback, [P1] name binding, [P2] atomicity."""

    @pytest.mark.asyncio
    async def test_rollback_removes_active_not_re_upserts(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
        mock_registry: MagicMock,
    ) -> None:
        """[P1] rollback must remove_active + unregister, not upsert the same version."""
        current = _make_proposal_record(governance_version=5, status="active")
        mock_store.find_last_applied = AsyncMock(return_value=current)
        await adapter.rollback(wrapper_tool_id="wt-001")
        # Must disable in store
        mock_store.remove_active.assert_awaited_once()
        # Must NOT re-upsert
        mock_store.upsert_active.assert_not_awaited()
        # Must unregister from registry
        mock_registry.unregister.assert_called_once_with("wt-001")
        # Must mark the active version as rolled_back in ledger
        rolled_back_calls = [
            c for c in mock_store.update_proposal_status.call_args_list
            if c[0][1] == GrowthLifecycleStatus.rolled_back and c[0][0] == 5
        ]
        assert len(rolled_back_calls) == 1

    @pytest.mark.asyncio
    async def test_name_mismatch_raises_on_apply(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
        mock_registry: MagicMock,
    ) -> None:
        """[P1] factory returning tool.name != spec.id must fail apply."""
        mock_store.get_proposal = AsyncMock(return_value=_make_proposal_record(eval_passed=True))

        mismatched_tool = MagicMock()
        mismatched_tool.name = "different-name"

        def bad_factory():
            return mismatched_tool

        with patch("src.growth.adapters.wrapper_tool.importlib") as mock_imp:
            mock_mod = MagicMock()
            mock_mod.loads = bad_factory  # matches "json:loads" ref
            mock_imp.import_module.return_value = mock_mod
            with pytest.raises(ValueError, match="must match"):
                await adapter.apply(1)
        # Registry should NOT have the mismatched tool
        mock_registry.replace.assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_db_first_then_registry(
        self,
        adapter: WrapperToolGovernedObjectAdapter,
        mock_store: AsyncMock,
    ) -> None:
        """[P2] DB writes must complete before registry mutation."""
        mock_store.get_proposal = AsyncMock(return_value=_make_proposal_record(eval_passed=True))
        call_order: list[str] = []
        orig_upsert = mock_store.upsert_active

        async def track_upsert(*a, **kw):
            call_order.append("db_upsert")
            return await orig_upsert(*a, **kw)

        mock_store.upsert_active = track_upsert

        def track_register(spec, registry):
            call_order.append("registry_replace")

        with patch(
            "src.growth.adapters.wrapper_tool._resolve_and_register",
            side_effect=track_register,
        ):
            await adapter.apply(1)
        assert call_order.index("db_upsert") < call_order.index("registry_replace")
