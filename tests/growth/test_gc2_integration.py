"""GC-2 integration test: Skill-to-Wrapper-Tool Promotion (P2-M1c em2.4.2).

Simulates the full GC-2 flow with all external dependencies mocked:
1. Pre-set active skill with evidence (usage_count=5, success_rate=0.9)
2. Check promote conditions (usage_count >= 3, success_rate >= 0.8)
3. GrowthGovernanceEngine.propose() for wrapper_tool
4. evaluate() passes 5 checks
5. apply() succeeds: store + ToolRegistry both visible
6. CaseRunner records complete run

Failure cases:
7. Eval failure (typed_io_validation fails) -> vetoed
8. Apply then rollback -> ToolRegistry wrapper removed

No DB, no LLM calls, no API quota consumed.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.growth.adapters.skill import SkillGovernedObjectAdapter
from src.growth.adapters.wrapper_tool import WrapperToolGovernedObjectAdapter
from src.growth.case_runner import CaseRunner
from src.growth.case_types import GrowthCaseStatus
from src.growth.engine import GrowthGovernanceEngine
from src.growth.policies import PolicyRegistry
from src.growth.types import (
    GrowthObjectKind,
    GrowthProposal,
)
from src.skills.types import SkillEvidence, SkillSpec
from src.wrappers.store import WrapperToolProposalRecord
from src.wrappers.types import WrapperToolSpec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill_spec() -> SkillSpec:
    return SkillSpec(
        id="sk-promote-001",
        capability="file summarization",
        version=1,
        summary="Summarize files using read_file",
        activation="When user asks to summarize a file",
        activation_tags=("summarize", "file"),
        delta=("Read file then produce summary",),
        exchange_policy="reusable",
    )


def _make_skill_evidence() -> SkillEvidence:
    return SkillEvidence(
        source="deterministic",
        success_count=5,
        failure_count=0,
        last_validated_at=datetime(2026, 3, 1, tzinfo=UTC),
        positive_patterns=("clean summary", "no hallucination"),
    )


def _make_wrapper_tool_spec() -> WrapperToolSpec:
    return WrapperToolSpec(
        id="wt-summarize-001",
        capability="file_summarizer",
        version=1,
        summary="Summarizes a file content",
        input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"summary": {"type": "string"}}},
        implementation_ref="json:loads",  # stdlib, always importable
        deny_semantics=("no_write", "no_delete"),
        bound_atomic_tools=("read_file",),
        scope_claim="reusable",
    )


def _make_wrapper_proposal_record(
    spec: WrapperToolSpec,
    *,
    gv: int = 1,
    status: str = "proposed",
    eval_passed: bool | None = None,
) -> WrapperToolProposalRecord:
    eval_result = None
    if eval_passed is not None:
        eval_result = {"passed": eval_passed}
    return WrapperToolProposalRecord(
        governance_version=gv,
        wrapper_tool_id=spec.id,
        status=status,
        proposal={
            "intent": "Promote skill to wrapper tool",
            "payload": {
                "wrapper_tool_spec": spec.model_dump(),
                "smoke_test_results": {"passed": True},
            },
        },
        eval_result=eval_result,
        created_by="agent",
        created_at=datetime(2026, 3, 1, tzinfo=UTC),
        applied_at=None,
        rolled_back_from=None,
    )


def _build_wrapper_store(
    wt_spec: WrapperToolSpec, *, eval_passed: bool = True,
) -> AsyncMock:
    """Build a mock WrapperToolStore for GC-2 flow."""
    store = AsyncMock()
    store.create_proposal = AsyncMock(return_value=1)
    store.store_eval_result = AsyncMock()
    store.update_proposal_status = AsyncMock()
    store.upsert_active = AsyncMock()
    store.remove_active = AsyncMock()
    store.find_last_applied = AsyncMock(return_value=None)
    store.get_active = AsyncMock(return_value=[wt_spec])

    proposed = _make_wrapper_proposal_record(wt_spec, gv=1, status="proposed")
    passed = _make_wrapper_proposal_record(
        wt_spec, gv=1, status="proposed", eval_passed=eval_passed,
    )
    store.get_proposal = AsyncMock(side_effect=[proposed, passed])

    mock_session = MagicMock(name="mock_db_session")

    @asynccontextmanager
    async def _fake_transaction():
        yield mock_session

    store.transaction = _fake_transaction
    return store


def _build_skill_store(skill_spec: SkillSpec, evidence: SkillEvidence) -> AsyncMock:
    """Build a mock SkillStore with active skill + evidence."""
    store = AsyncMock()
    store.list_active = AsyncMock(return_value=[skill_spec])
    store.get_evidence = AsyncMock(return_value={skill_spec.id: evidence})
    store.create_proposal = AsyncMock(return_value=99)
    store.get_proposal = AsyncMock(return_value=None)
    store.store_eval_result = AsyncMock()
    store.update_proposal_status = AsyncMock()
    store.upsert_active = AsyncMock()
    store.disable = AsyncMock()
    store.find_last_applied = AsyncMock(return_value=None)

    mock_session = MagicMock(name="mock_db_session")

    @asynccontextmanager
    async def _fake_transaction():
        yield mock_session

    store.transaction = _fake_transaction
    return store


def _check_promote_conditions(evidence: SkillEvidence) -> bool:
    """Check GC-2 entry conditions: usage_count >= 3, success_rate >= 0.8."""
    total = evidence.success_count + evidence.failure_count
    if total == 0:
        return False
    usage_ok = evidence.success_count >= 3
    success_rate = evidence.success_count / total
    rate_ok = success_rate >= 0.8
    return usage_ok and rate_ok


@pytest.fixture()
def gc2_components(tmp_path: Path):
    """Build the full component set for GC-2 integration."""
    skill_spec = _make_skill_spec()
    skill_evidence = _make_skill_evidence()
    wt_spec = _make_wrapper_tool_spec()

    skill_store = _build_skill_store(skill_spec, skill_evidence)
    wrapper_store = _build_wrapper_store(wt_spec)
    mock_registry = MagicMock()
    mock_registry.replace = MagicMock()
    mock_registry.unregister = MagicMock()

    skill_adapter = SkillGovernedObjectAdapter(skill_store)
    wrapper_adapter = WrapperToolGovernedObjectAdapter(wrapper_store, mock_registry)
    policy_registry = PolicyRegistry()

    engine = GrowthGovernanceEngine(
        adapters={
            GrowthObjectKind.skill_spec: skill_adapter,
            GrowthObjectKind.wrapper_tool: wrapper_adapter,
        },
        policy_registry=policy_registry,
    )
    runner = CaseRunner(artifact_base=tmp_path / "growth_cases")

    return {
        "skill_spec": skill_spec,
        "skill_evidence": skill_evidence,
        "wt_spec": wt_spec,
        "skill_store": skill_store,
        "wrapper_store": wrapper_store,
        "mock_registry": mock_registry,
        "engine": engine,
        "runner": runner,
        "artifact_base": tmp_path / "growth_cases",
    }


# ---------------------------------------------------------------------------
# Success flow
# ---------------------------------------------------------------------------


class TestGC2FullFlow:
    """Full GC-2: skill with evidence -> promote -> wrapper_tool applied."""

    @patch("src.growth.adapters.wrapper_tool.importlib")
    async def test_promote_skill_to_wrapper_tool(
        self, mock_importlib: MagicMock, gc2_components: dict,
    ) -> None:
        skill_evidence: SkillEvidence = gc2_components["skill_evidence"]
        wt_spec: WrapperToolSpec = gc2_components["wt_spec"]
        engine: GrowthGovernanceEngine = gc2_components["engine"]
        runner: CaseRunner = gc2_components["runner"]
        mock_registry: MagicMock = gc2_components["mock_registry"]
        artifact_base: Path = gc2_components["artifact_base"]

        # Stub importlib for dry_run_smoke check
        mock_mod = MagicMock()
        mock_mod.loads = MagicMock()
        mock_importlib.import_module.return_value = mock_mod

        # --- Step 1: Check promote conditions ---
        assert _check_promote_conditions(skill_evidence)

        # --- Step 2: Start case run ---
        run = await runner.start_run("gc-2")
        assert run.status == GrowthCaseStatus.running

        # --- Step 3: Propose wrapper_tool ---
        proposal = GrowthProposal(
            object_kind=GrowthObjectKind.wrapper_tool,
            object_id=wt_spec.id,
            intent="Promote skill to wrapper tool",
            risk_notes="Low risk - proven skill",
            diff_summary="Promote file_summarizer to wrapper tool",
            payload={
                "wrapper_tool_spec": wt_spec.model_dump(),
                "smoke_test_results": {"passed": True},
            },
        )
        gv = await engine.propose(GrowthObjectKind.wrapper_tool, proposal)
        assert gv == 1
        run = await runner.record_proposal(run, governance_version=gv)

        # --- Step 4: Evaluate ---
        eval_result = await engine.evaluate(GrowthObjectKind.wrapper_tool, gv)
        assert eval_result.passed is True
        run = await runner.record_eval(run, eval_result)

        # --- Step 5: Apply ---
        await engine.apply(GrowthObjectKind.wrapper_tool, gv)
        run = await runner.record_apply(run, success=True)

        # Verify ToolRegistry.replace was called
        mock_registry.replace.assert_called_once()

        # Verify wrapper store upsert_active was called
        wrapper_store: AsyncMock = gc2_components["wrapper_store"]
        wrapper_store.upsert_active.assert_called_once()

        # --- Step 6: Finalize ---
        run = await runner.finalize(
            run, summary="Skill promoted to wrapper tool successfully",
        )
        assert run.status == GrowthCaseStatus.passed

        # Verify artifact
        artifact_path = artifact_base / "gc-2" / f"{run.run_id}.md"
        assert artifact_path.exists()
        content = artifact_path.read_text(encoding="utf-8")
        assert "gv:1" in content
        assert "passed=True" in content


# ---------------------------------------------------------------------------
# Failure: eval fails (typed_io_validation)
# ---------------------------------------------------------------------------


class TestGC2EvalFailure:
    """GC-2 with eval failure -> vetoed."""

    async def test_eval_failure_vetoes_run(self, tmp_path: Path) -> None:
        wt_spec = WrapperToolSpec(
            id="wt-bad-io",
            capability="bad_tool",
            version=1,
            summary="Tool with invalid schemas",
            input_schema={"missing": "type"},  # missing "type" key
            output_schema={"type": "object"},
            implementation_ref="json:loads",
            deny_semantics=("no_write",),
        )

        wrapper_store = AsyncMock()
        wrapper_store.create_proposal = AsyncMock(return_value=1)
        wrapper_store.store_eval_result = AsyncMock()

        proposed = _make_wrapper_proposal_record(wt_spec, gv=1, status="proposed")
        proposed = WrapperToolProposalRecord(
            governance_version=1,
            wrapper_tool_id=wt_spec.id,
            status="proposed",
            proposal={
                "intent": "Promote",
                "payload": {
                    "wrapper_tool_spec": wt_spec.model_dump(),
                    "smoke_test_results": {"passed": True},
                },
            },
            eval_result=None,
            created_by="agent",
            created_at=datetime(2026, 3, 1, tzinfo=UTC),
            applied_at=None,
            rolled_back_from=None,
        )
        wrapper_store.get_proposal = AsyncMock(return_value=proposed)

        mock_session = MagicMock()

        @asynccontextmanager
        async def _fake_tx():
            yield mock_session

        wrapper_store.transaction = _fake_tx

        mock_registry = MagicMock()
        wrapper_adapter = WrapperToolGovernedObjectAdapter(wrapper_store, mock_registry)
        policy_registry = PolicyRegistry()
        engine = GrowthGovernanceEngine(
            adapters={GrowthObjectKind.wrapper_tool: wrapper_adapter},
            policy_registry=policy_registry,
        )
        runner = CaseRunner(artifact_base=tmp_path / "growth_cases")

        # Start run
        run = await runner.start_run("gc-2")

        # Propose
        proposal = GrowthProposal(
            object_kind=GrowthObjectKind.wrapper_tool,
            object_id=wt_spec.id,
            intent="Promote",
            risk_notes="Testing",
            diff_summary="Bad spec",
            payload={"wrapper_tool_spec": wt_spec.model_dump()},
        )
        gv = await engine.propose(GrowthObjectKind.wrapper_tool, proposal)
        run = await runner.record_proposal(run, gv)

        # Evaluate -- should fail on typed_io_validation
        eval_result = await engine.evaluate(GrowthObjectKind.wrapper_tool, gv)
        assert eval_result.passed is False
        run = await runner.record_eval(run, eval_result)

        # Verify the failure is typed_io
        failed_names = [c["name"] for c in eval_result.checks if not c["passed"]]
        assert "typed_io_validation" in failed_names

        # Finalize as vetoed
        vetoed_run = run.model_copy(
            update={"status": GrowthCaseStatus.vetoed},
        )
        final = await runner.finalize(
            vetoed_run,
            summary="Eval failed: typed_io_validation check did not pass",
            passed=False,
        )
        # vetoed is not in (failed, rolled_back), so finalize with passed=False
        # does not override it (it's not running either), let's check
        assert final.status == GrowthCaseStatus.vetoed
        assert "typed_io_validation" in final.summary


# ---------------------------------------------------------------------------
# Failure: apply then rollback
# ---------------------------------------------------------------------------


class TestGC2Rollback:
    """GC-2 with successful apply then rollback -> ToolRegistry wrapper removed."""

    @patch("src.growth.adapters.wrapper_tool.importlib")
    async def test_apply_then_rollback(
        self, mock_importlib: MagicMock, gc2_components: dict,
    ) -> None:
        wt_spec: WrapperToolSpec = gc2_components["wt_spec"]
        engine: GrowthGovernanceEngine = gc2_components["engine"]
        runner: CaseRunner = gc2_components["runner"]
        mock_registry: MagicMock = gc2_components["mock_registry"]
        wrapper_store: AsyncMock = gc2_components["wrapper_store"]

        # Stub importlib
        mock_mod = MagicMock()
        mock_mod.loads = MagicMock()
        mock_importlib.import_module.return_value = mock_mod

        # Start
        run = await runner.start_run("gc-2")

        # Propose
        proposal = GrowthProposal(
            object_kind=GrowthObjectKind.wrapper_tool,
            object_id=wt_spec.id,
            intent="Promote",
            risk_notes="Test",
            diff_summary="Promote",
            payload={
                "wrapper_tool_spec": wt_spec.model_dump(),
                "smoke_test_results": {"passed": True},
            },
        )
        gv = await engine.propose(GrowthObjectKind.wrapper_tool, proposal)
        run = await runner.record_proposal(run, gv)

        # Evaluate + Apply
        eval_result = await engine.evaluate(GrowthObjectKind.wrapper_tool, gv)
        assert eval_result.passed
        run = await runner.record_eval(run, eval_result)
        await engine.apply(GrowthObjectKind.wrapper_tool, gv)
        run = await runner.record_apply(run, success=True)

        # Now rollback
        # Reset side_effect for rollback proposal creation
        wrapper_store.create_proposal = AsyncMock(return_value=2)
        wrapper_store.find_last_applied = AsyncMock(return_value=None)

        rollback_gv = await engine.rollback(
            GrowthObjectKind.wrapper_tool, wrapper_tool_id=wt_spec.id,
        )
        run = await runner.record_rollback(run)

        # Verify ToolRegistry.unregister was called (no last_applied -> disable path)
        mock_registry.unregister.assert_called_with(wt_spec.id)

        # Verify wrapper store remove_active was called
        wrapper_store.remove_active.assert_called_once()

        # Finalize
        final = await runner.finalize(run, summary="Rolled back after apply")
        assert final.status == GrowthCaseStatus.rolled_back
        assert "rollback:executed" in final.rollback_refs


class TestPromoteConditionCheck:
    """_check_promote_conditions should validate GC-2 thresholds."""

    def test_meets_conditions(self) -> None:
        evidence = SkillEvidence(source="test", success_count=5, failure_count=0)
        assert _check_promote_conditions(evidence)

    def test_insufficient_usage(self) -> None:
        evidence = SkillEvidence(source="test", success_count=2, failure_count=0)
        assert not _check_promote_conditions(evidence)

    def test_low_success_rate(self) -> None:
        evidence = SkillEvidence(source="test", success_count=3, failure_count=3)
        assert not _check_promote_conditions(evidence)

    def test_boundary_usage_count(self) -> None:
        evidence = SkillEvidence(source="test", success_count=3, failure_count=0)
        assert _check_promote_conditions(evidence)

    def test_boundary_success_rate(self) -> None:
        # 4/5 = 0.8 exactly
        evidence = SkillEvidence(source="test", success_count=4, failure_count=1)
        assert _check_promote_conditions(evidence)

    def test_zero_total(self) -> None:
        evidence = SkillEvidence(source="test", success_count=0, failure_count=0)
        assert not _check_promote_conditions(evidence)
