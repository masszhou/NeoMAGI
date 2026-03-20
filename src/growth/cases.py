"""Growth case catalog: hardcoded, curated case specifications (P2-M1c).

The catalog is the single source of truth for what growth cases exist
and what they require. Cases are not dynamically created (ADR 0057).
"""

from __future__ import annotations

from src.growth.case_types import GrowthCaseSpec

GROWTH_CASE_CATALOG: dict[str, GrowthCaseSpec] = {
    "gc-1": GrowthCaseSpec(
        case_id="gc-1",
        title="Human-Taught Skill Reuse",
        source_kind="skill_spec",
        target_kind=None,  # no promote, just reuse
        contract_id="skill_spec_eval_v1",
        contract_version=1,
        entry_conditions=(
            "user_teaching_intent_detected",
            "structured_delta_extractable",
        ),
        required_artifacts=(
            "teaching_transcript",
            "skill_proposal",
            "reuse_evidence",
        ),
        success_rule="skill applied AND reused in similar task with positive outcome",
        rollback_rule="skill disabled if reuse fails twice consecutively",
    ),
    "gc-2": GrowthCaseSpec(
        case_id="gc-2",
        title="Skill-to-Wrapper-Tool Promotion",
        source_kind="skill_spec",
        target_kind="wrapper_tool",
        contract_id="wrapper_tool_eval_v1",
        contract_version=1,
        entry_conditions=(
            "active_skill_exists",
            "usage_count_gte_3",
            "success_rate_gte_0.8",
            "typed_io_boundary_clear",
        ),
        required_artifacts=(
            "skill_evidence_snapshot",
            "wrapper_tool_proposal",
            "eval_result",
            "apply_or_rollback_evidence",
        ),
        success_rule="wrapper_tool applied AND registered in ToolRegistry AND callable",
        rollback_rule="wrapper_tool removed from registry AND store on failure",
    ),
}


def get_case_spec(case_id: str) -> GrowthCaseSpec | None:
    """Return a case spec by ID, or None if not found."""
    return GROWTH_CASE_CATALOG.get(case_id)


def list_case_specs() -> list[GrowthCaseSpec]:
    """Return all case specs in catalog order."""
    return list(GROWTH_CASE_CATALOG.values())
