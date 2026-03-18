"""Tests for GrowthCaseSpec and GrowthCaseRun domain types (P2-M1c em2.4.3)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.growth.case_types import GrowthCaseRun, GrowthCaseSpec, GrowthCaseStatus


class TestGrowthCaseStatus:
    """GrowthCaseStatus should have all expected lifecycle values."""

    def test_all_values(self) -> None:
        expected = {"planned", "running", "passed", "failed", "vetoed", "rolled_back"}
        assert {s.value for s in GrowthCaseStatus} == expected

    def test_string_identity(self) -> None:
        assert GrowthCaseStatus.planned == "planned"
        assert GrowthCaseStatus.rolled_back == "rolled_back"


class TestGrowthCaseSpec:
    """GrowthCaseSpec should be frozen and validate required fields."""

    def test_minimal_construction(self) -> None:
        spec = GrowthCaseSpec(
            case_id="gc-test",
            title="Test Case",
            source_kind="skill_spec",
            contract_id="test_v1",
            contract_version=1,
        )
        assert spec.case_id == "gc-test"
        assert spec.title == "Test Case"
        assert spec.source_kind == "skill_spec"
        assert spec.target_kind is None
        assert spec.entry_conditions == ()
        assert spec.required_artifacts == ()
        assert spec.success_rule == ""
        assert spec.rollback_rule == ""

    def test_full_construction(self) -> None:
        spec = GrowthCaseSpec(
            case_id="gc-full",
            title="Full Case",
            source_kind="skill_spec",
            target_kind="wrapper_tool",
            contract_id="wrapper_tool_eval_v1",
            contract_version=1,
            entry_conditions=("cond_a", "cond_b"),
            required_artifacts=("art_1", "art_2"),
            success_rule="all pass",
            rollback_rule="remove on fail",
        )
        assert spec.target_kind == "wrapper_tool"
        assert len(spec.entry_conditions) == 2
        assert len(spec.required_artifacts) == 2

    def test_frozen(self) -> None:
        spec = GrowthCaseSpec(
            case_id="gc-frozen",
            title="Frozen",
            source_kind="skill_spec",
            contract_id="v1",
            contract_version=1,
        )
        with pytest.raises(ValidationError):
            spec.case_id = "mutated"  # type: ignore[misc]

    def test_missing_required_field(self) -> None:
        with pytest.raises(ValidationError):
            GrowthCaseSpec(  # type: ignore[call-arg]
                case_id="gc-bad",
                title="No contract",
                source_kind="skill_spec",
                # contract_id missing
                contract_version=1,
            )


class TestGrowthCaseRun:
    """GrowthCaseRun should be frozen with default values."""

    def test_minimal_construction(self) -> None:
        run = GrowthCaseRun(run_id="run-1", case_id="gc-1")
        assert run.status == GrowthCaseStatus.planned
        assert run.linked_bead_ids == ()
        assert run.proposal_refs == ()
        assert run.eval_refs == ()
        assert run.apply_refs == ()
        assert run.rollback_refs == ()
        assert run.artifact_refs == ()
        assert run.summary == ""

    def test_frozen(self) -> None:
        run = GrowthCaseRun(run_id="run-f", case_id="gc-1")
        with pytest.raises(ValidationError):
            run.status = GrowthCaseStatus.passed  # type: ignore[misc]

    def test_model_copy_update(self) -> None:
        run = GrowthCaseRun(run_id="run-c", case_id="gc-1")
        updated = run.model_copy(
            update={
                "status": GrowthCaseStatus.running,
                "proposal_refs": ("gv:1",),
            },
        )
        assert updated.status == GrowthCaseStatus.running
        assert updated.proposal_refs == ("gv:1",)
        # Original unchanged
        assert run.status == GrowthCaseStatus.planned
        assert run.proposal_refs == ()
