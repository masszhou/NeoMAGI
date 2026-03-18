"""Domain types for the growth case runtime layer (P2-M1c).

Defines: GrowthCaseStatus, GrowthCaseSpec, GrowthCaseRun.

Design notes:
- GrowthCaseSpec is a curated, hardcoded catalog entry -- not dynamically created.
- GrowthCaseRun is a single execution record persisted as workspace artifact,
  NOT in PostgreSQL (ADR 0057).
- Both use frozen=True for immutability (consistent with SkillSpec pattern).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class GrowthCaseStatus(StrEnum):
    """Lifecycle status for a growth case run."""

    planned = "planned"
    running = "running"
    passed = "passed"
    failed = "failed"
    vetoed = "vetoed"
    rolled_back = "rolled_back"


class GrowthCaseSpec(BaseModel):
    """Curated growth case specification. Hardcoded catalog."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    title: str
    source_kind: str  # GrowthObjectKind value
    target_kind: str | None = None  # GrowthObjectKind value, None if no promote
    contract_id: str
    contract_version: int
    entry_conditions: tuple[str, ...] = ()
    required_artifacts: tuple[str, ...] = ()
    success_rule: str = ""
    rollback_rule: str = ""


class GrowthCaseRun(BaseModel):
    """A single execution of a growth case. Persisted as workspace artifact."""

    model_config = ConfigDict(frozen=True)

    run_id: str  # artifact_id (uuid4 for now)
    case_id: str
    status: GrowthCaseStatus = GrowthCaseStatus.planned
    linked_bead_ids: tuple[str, ...] = ()
    proposal_refs: tuple[str, ...] = ()
    eval_refs: tuple[str, ...] = ()
    apply_refs: tuple[str, ...] = ()
    rollback_refs: tuple[str, ...] = ()
    artifact_refs: tuple[str, ...] = ()
    summary: str = ""
