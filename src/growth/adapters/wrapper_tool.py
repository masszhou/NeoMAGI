"""Wrapper tool governed-object adapter: connects wrapper_tool to the growth kernel.

Implements :class:`GovernedObjectAdapter` protocol for
:attr:`GrowthObjectKind.wrapper_tool`.

Pins ``WRAPPER_TOOL_EVAL_CONTRACT_V1`` before every evaluation (ADR 0054 §1a).
All 5 eval checks are deterministic — no LLM calls, no network access.
``apply()`` and ``rollback()`` execute in single DB transactions (atomic).
ToolRegistry registration/unregistration is coupled to the transaction outcome.
"""

from __future__ import annotations

import importlib
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from src.growth.contracts import WRAPPER_TOOL_EVAL_CONTRACT_V1
from src.growth.types import (
    GrowthEvalResult,
    GrowthLifecycleStatus,
    GrowthObjectKind,
    GrowthProposal,
)
from src.wrappers.types import WrapperToolSpec

if TYPE_CHECKING:
    from src.tools.registry import ToolRegistry
    from src.wrappers.store import WrapperToolStore

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# implementation_ref V1 pattern: "<module>:<factory>"
# ---------------------------------------------------------------------------

_IMPL_REF_PATTERN = re.compile(r"^[\w.]+:[\w]+$")

# ---------------------------------------------------------------------------
# Eval check helpers
# ---------------------------------------------------------------------------


def _check_typed_io_validation(spec: WrapperToolSpec) -> dict:
    """Check 1: input_schema and output_schema are valid JSON Schema dicts."""
    errors: list[str] = []
    if not isinstance(spec.input_schema, dict):
        errors.append("input_schema is not a dict")
    elif "type" not in spec.input_schema:
        errors.append("input_schema missing 'type' key")
    if not isinstance(spec.output_schema, dict):
        errors.append("output_schema is not a dict")
    elif "type" not in spec.output_schema:
        errors.append("output_schema missing 'type' key")
    if not spec.id:
        errors.append("id is empty")
    if not spec.capability:
        errors.append("capability is empty")
    if not spec.summary:
        errors.append("summary is empty")
    if spec.version < 1:
        errors.append(f"version must be >= 1, got {spec.version}")
    passed = len(errors) == 0
    return {
        "name": "typed_io_validation",
        "passed": passed,
        "detail": "Typed I/O valid" if passed else "; ".join(errors),
    }


def _check_permission_boundary(spec: WrapperToolSpec) -> dict:
    """Check 2: deny_semantics must be non-empty and reasonable."""
    errors: list[str] = []
    if not spec.deny_semantics:
        errors.append("deny_semantics is empty — every wrapper must declare denied operations")
    else:
        for ds in spec.deny_semantics:
            if not ds.strip():
                errors.append("deny_semantics contains an empty entry")
    passed = len(errors) == 0
    return {
        "name": "permission_boundary",
        "passed": passed,
        "detail": "Permission boundary OK" if passed else "; ".join(errors),
    }


def _check_dry_run_smoke(spec: WrapperToolSpec) -> dict:
    """Check 3: implementation_ref format valid and module importable."""
    errors: list[str] = []
    ref = spec.implementation_ref
    if not _IMPL_REF_PATTERN.match(ref):
        errors.append(f"implementation_ref '{ref}' does not match '<module>:<factory>' pattern")
    else:
        module_path, _factory_name = ref.rsplit(":", 1)
        try:
            importlib.import_module(module_path)
        except ImportError as exc:
            errors.append(f"Cannot import module '{module_path}': {exc}")
    passed = len(errors) == 0
    return {
        "name": "dry_run_smoke",
        "passed": passed,
        "detail": "Dry-run smoke OK" if passed else "; ".join(errors),
    }


def _check_before_after_cases(proposal_payload: dict) -> dict:
    """Check 4: proposal must contain before/after or smoke_test evidence."""
    has_evidence = (
        "before_after" in proposal_payload
        or "smoke_test_results" in proposal_payload
        or "evidence" in proposal_payload
    )
    if has_evidence:
        return {
            "name": "before_after_cases",
            "passed": True,
            "detail": "Before/after evidence present",
        }
    return {
        "name": "before_after_cases",
        "passed": False,
        "detail": "No before/after or smoke_test evidence in payload",
    }


def _check_scope_claim_consistency(spec: WrapperToolSpec) -> dict:
    """Check 5: scope_claim consistent with bound_atomic_tools and implementation_ref."""
    errors: list[str] = []
    valid_claims = {"local", "reusable", "promotable"}
    if spec.scope_claim not in valid_claims:
        errors.append(f"scope_claim '{spec.scope_claim}' not in {valid_claims}")
    if spec.scope_claim in ("reusable", "promotable"):
        if not spec.bound_atomic_tools:
            errors.append(f"scope_claim='{spec.scope_claim}' but bound_atomic_tools is empty")
    passed = len(errors) == 0
    return {
        "name": "scope_claim_consistency",
        "passed": passed,
        "detail": "Scope claim consistent" if passed else "; ".join(errors),
    }


# ---------------------------------------------------------------------------
# WrapperToolGovernedObjectAdapter
# ---------------------------------------------------------------------------


def _eval_early_return(record, version: int, contract) -> GrowthEvalResult | None:
    """Return early-exit eval result if record is missing or not proposed."""
    if record is None:
        return GrowthEvalResult(
            passed=False,
            summary=f"Governance version {version} not found",
            contract_id=contract.contract_id,
            contract_version=contract.version,
        )
    if record.status != GrowthLifecycleStatus.proposed:
        return GrowthEvalResult(
            passed=False,
            summary=f"Version {version} is '{record.status}', not 'proposed'",
            contract_id=contract.contract_id,
            contract_version=contract.version,
        )
    return None


def _parse_proposal_payload(record, contract) -> WrapperToolSpec | GrowthEvalResult:
    """Parse WrapperToolSpec from proposal payload; return EvalResult on failure."""
    payload = record.proposal.get("payload", {})
    try:
        spec = WrapperToolSpec(**payload.get("wrapper_tool_spec", {}))
    except Exception as exc:
        return GrowthEvalResult(
            passed=False,
            checks=[
                {
                    "name": "typed_io_validation",
                    "passed": False,
                    "detail": f"Payload parse error: {exc}",
                }
            ],
            summary=f"Payload parse error: {exc}",
            contract_id=contract.contract_id,
            contract_version=contract.version,
        )
    return spec


def _run_eval_checks(spec: WrapperToolSpec, payload: dict, contract) -> GrowthEvalResult:
    """Run 5 deterministic eval checks and return the composite result."""
    checks = [
        _check_typed_io_validation(spec),
        _check_permission_boundary(spec),
        _check_dry_run_smoke(spec),
        _check_before_after_cases(payload),
        _check_scope_claim_consistency(spec),
    ]
    passed = all(c["passed"] for c in checks)
    summary = (
        "All checks passed"
        if passed
        else "Failed: " + ", ".join(c["name"] for c in checks if not c["passed"])
    )
    return GrowthEvalResult(
        passed=passed,
        checks=checks,
        summary=summary,
        contract_id=contract.contract_id,
        contract_version=contract.version,
    )


def _resolve_and_register(spec: WrapperToolSpec, registry: ToolRegistry) -> None:
    """Resolve implementation_ref and register the tool in the ToolRegistry.

    Parses ``<module>:<factory>``, imports the module, calls the factory,
    and registers the resulting BaseTool instance.
    """
    module_path, factory_name = spec.implementation_ref.rsplit(":", 1)
    mod = importlib.import_module(module_path)
    factory = getattr(mod, factory_name)
    tool = factory()
    registry.replace(tool)
    logger.info(
        "wrapper_tool_registered",
        wrapper_tool_id=spec.id,
        tool_name=tool.name,
        implementation_ref=spec.implementation_ref,
    )


class WrapperToolGovernedObjectAdapter:
    """Adapter connecting wrapper_tool to the growth governance kernel.

    Implements :class:`GovernedObjectAdapter` protocol for
    :attr:`GrowthObjectKind.wrapper_tool`.
    """

    def __init__(self, store: WrapperToolStore, registry: ToolRegistry) -> None:
        self._store = store
        self._registry = registry
        self._contract = WRAPPER_TOOL_EVAL_CONTRACT_V1

    @property
    def kind(self) -> GrowthObjectKind:
        return GrowthObjectKind.wrapper_tool

    async def propose(self, proposal: GrowthProposal) -> int:
        """Create a governance proposal from payload.

        Requires ``proposal.payload["wrapper_tool_spec"]`` (dict).
        Returns the governance_version.
        """
        raw_spec = proposal.payload.get("wrapper_tool_spec")
        if not isinstance(raw_spec, dict):
            raise ValueError(
                "WrapperToolGovernedObjectAdapter.propose() requires "
                'proposal.payload["wrapper_tool_spec"] to be a dict'
            )
        # Validate that it parses as a domain object (fail fast)
        WrapperToolSpec(**raw_spec)

        gv = await self._store.create_proposal(proposal)
        logger.info(
            "wrapper_tool_adapter_proposed",
            governance_version=gv,
            wrapper_tool_id=proposal.object_id,
        )
        return gv

    async def evaluate(self, version: int) -> GrowthEvalResult:
        """Run 5 deterministic eval checks against a proposed wrapper tool.

        Pins ``WRAPPER_TOOL_EVAL_CONTRACT_V1`` (ADR 0054 §1a).
        """
        contract = self._contract
        record = await self._store.get_proposal(version)

        early = _eval_early_return(record, version, contract)
        if early is not None:
            return early

        assert record is not None  # guaranteed by _eval_early_return
        parsed = _parse_proposal_payload(record, contract)
        if isinstance(parsed, GrowthEvalResult):
            return parsed
        spec = parsed

        payload = record.proposal.get("payload", {})
        result = _run_eval_checks(spec, payload, contract)
        await self._store.store_eval_result(version, result)
        logger.info(
            "wrapper_tool_adapter_evaluated",
            governance_version=version,
            passed=result.passed,
        )
        return result

    async def apply(self, version: int) -> None:
        """Materialize a passed proposal to wrapper_tools + ToolRegistry (atomic).

        Five-step write in single transaction:
        1. Check eval_result.passed == True
        2. Parse WrapperToolSpec
        3. Upsert current-state (store)
        4. Register in ToolRegistry
        5. Mark ledger row as active

        Steps 3-5 execute within a single DB transaction so that a failure
        in any step rolls back DB writes.  ToolRegistry registration is
        performed before the ledger update; if ledger update fails, the
        transaction context manager's rollback triggers, and the caller
        is responsible for not leaking the registry state (in practice
        the whole operation is retried or aborted).
        """
        record = await self._store.get_proposal(version)
        if record is None:
            raise ValueError(f"Governance version {version} not found")
        if record.status != GrowthLifecycleStatus.proposed:
            raise ValueError(f"Cannot apply version {version}: status is '{record.status}'")
        if not record.eval_result or not record.eval_result.get("passed"):
            raise ValueError(f"Cannot apply version {version}: eval not passed")

        payload = record.proposal.get("payload", {})
        spec = WrapperToolSpec(**payload["wrapper_tool_spec"])

        # Atomic: upsert current-state + register tool + update ledger
        async with self._store.transaction() as session:
            await self._store.upsert_active(spec, session=session)
            _resolve_and_register(spec, self._registry)
            await self._store.update_proposal_status(
                version,
                GrowthLifecycleStatus.active,
                applied_at=datetime.now(UTC),
                session=session,
            )
        logger.info(
            "wrapper_tool_adapter_applied",
            governance_version=version,
            wrapper_tool_id=spec.id,
        )

    async def rollback(self, **kwargs: object) -> int:
        """Rollback to previous applied snapshot or disable.

        Returns the governance_version of the rollback entry.
        All writes execute within a single DB transaction (atomic).
        """
        wrapper_tool_id = kwargs.get("wrapper_tool_id")
        if not isinstance(wrapper_tool_id, str):
            raise ValueError("rollback() requires wrapper_tool_id as keyword argument")

        last_applied = await self._store.find_last_applied(wrapper_tool_id)

        async with self._store.transaction() as session:
            await self._restore_or_disable(last_applied, wrapper_tool_id, session)
            gv = await self._create_rollback_entry(last_applied, wrapper_tool_id, session)

        logger.info(
            "wrapper_tool_adapter_rolled_back",
            governance_version=gv,
            wrapper_tool_id=wrapper_tool_id,
        )
        return gv

    async def _restore_or_disable(self, last_applied, wrapper_tool_id: str, session) -> None:
        """Re-materialize previous snapshot or disable + unregister."""
        if last_applied is not None:
            payload = last_applied.proposal.get("payload", {})
            spec = WrapperToolSpec(**payload["wrapper_tool_spec"])
            await self._store.upsert_active(spec, session=session)
            _resolve_and_register(spec, self._registry)
            await self._store.update_proposal_status(
                last_applied.governance_version,
                GrowthLifecycleStatus.rolled_back,
                session=session,
            )
        else:
            await self._store.remove_active(wrapper_tool_id, session=session)
            self._unregister_tool(wrapper_tool_id)

    def _unregister_tool(self, wrapper_tool_id: str) -> None:
        """Best-effort unregister from ToolRegistry."""
        try:
            self._registry.unregister(wrapper_tool_id)
        except KeyError:
            logger.debug(
                "wrapper_tool_unregister_skip",
                wrapper_tool_id=wrapper_tool_id,
                reason="not in registry",
            )

    async def _create_rollback_entry(self, last_applied, wrapper_tool_id: str, session) -> int:
        """Create a rollback ledger entry and return its governance_version."""
        rollback_proposal = GrowthProposal(
            object_kind=GrowthObjectKind.wrapper_tool,
            object_id=wrapper_tool_id,
            intent="rollback",
            risk_notes="System rollback",
            diff_summary="Rollback to previous version or disable",
            proposed_by="system",
        )
        gv = await self._store.create_proposal(rollback_proposal, session=session)
        await self._store.update_proposal_status(
            gv,
            GrowthLifecycleStatus.rolled_back,
            rolled_back_from=(last_applied.governance_version if last_applied else None),
            session=session,
        )
        return gv

    async def veto(self, version: int) -> None:
        """Veto a proposed or active governance version.

        Unapplied proposal -> mark vetoed.
        Active -> rollback/disable path.
        """
        record = await self._store.get_proposal(version)
        if record is None:
            raise ValueError(f"Governance version {version} not found")

        if record.status == GrowthLifecycleStatus.proposed:
            await self._store.update_proposal_status(version, GrowthLifecycleStatus.vetoed)
            logger.info(
                "wrapper_tool_adapter_vetoed",
                governance_version=version,
                was_status="proposed",
            )
        elif record.status == GrowthLifecycleStatus.active:
            await self.rollback(wrapper_tool_id=record.wrapper_tool_id)
            logger.info(
                "wrapper_tool_adapter_vetoed",
                governance_version=version,
                was_status="active",
            )
        else:
            raise ValueError(f"Cannot veto version {version}: status is '{record.status}'")

    async def get_active(self) -> list[WrapperToolSpec]:
        """Return all active (non-disabled) wrapper tools. Collection semantics."""
        result = await self._store.get_active()
        assert isinstance(result, list)  # no wrapper_tool_id arg → list
        return result
