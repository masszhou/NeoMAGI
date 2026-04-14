"""Unified memory visibility policy checkpoint (P2-M3c, D4).

Pure functions — no I/O, no logging, no external dependencies.
Callers are responsible for logging policy decisions (see D7 audit trail).

Policy version is exported for SQL WHERE / PromptBuilder / test consistency.
"""

from __future__ import annotations

from dataclasses import dataclass

MEMORY_VISIBILITY_POLICY_VERSION = "v1"


@dataclass(frozen=True)
class PolicyContext:
    """Caller context for visibility policy evaluation."""

    principal_id: str | None
    scope_key: str


@dataclass(frozen=True)
class MemoryPolicyEntry:
    """Minimal view of a memory entry required for policy evaluation."""

    entry_id: str
    owner_principal_id: str | None
    visibility: str | None  # None treated as "private_to_principal" (defensive)
    scope_key: str
    shared_space_id: str | None = None  # reserved, currently always None


@dataclass(frozen=True)
class PolicyDecision:
    """Result of a visibility policy evaluation."""

    allowed: bool
    reason: str


def can_read(context: PolicyContext, entry: MemoryPolicyEntry) -> PolicyDecision:
    """Determine whether *context* principal may read *entry*.

    Rule evaluation order (first match wins):
      0. shared_space_id guard — always deny if present
      1. private_to_principal (incl. visibility=None defensive)
      2. shareable_summary — same-principal only (V1)
      3. shared_in_space — always deny (reserved)
      4. unknown visibility — fail-closed
    """
    # Rule 0: shared_space_id guard (highest priority)
    if entry.shared_space_id is not None:
        return PolicyDecision(allowed=False, reason="membership_unavailable")

    visibility = entry.visibility if entry.visibility is not None else "private_to_principal"

    if visibility == "private_to_principal":
        # Owner or anonymous/legacy (owner_principal_id is None)
        if context.principal_id is None:
            # Anonymous requester: only legacy (no-owner) entries
            if entry.owner_principal_id is None:
                return PolicyDecision(allowed=True, reason="anonymous_legacy_access")
            return PolicyDecision(allowed=False, reason="principal_mismatch")
        # Authenticated requester: own entries + legacy entries
        if entry.owner_principal_id is None or entry.owner_principal_id == context.principal_id:
            return PolicyDecision(allowed=True, reason="owner_private_access")
        return PolicyDecision(allowed=False, reason="principal_mismatch")

    if visibility == "shareable_summary":
        # V1: same-principal only; anonymous cannot read summaries
        if context.principal_id is None:
            return PolicyDecision(allowed=False, reason="principal_mismatch")
        if entry.owner_principal_id == context.principal_id:
            return PolicyDecision(allowed=True, reason="same_principal")
        return PolicyDecision(allowed=False, reason="principal_mismatch")

    if visibility == "shared_in_space":
        return PolicyDecision(allowed=False, reason="shared_space_policy_not_implemented")

    return PolicyDecision(allowed=False, reason="unknown_visibility_value")


def can_write(context: PolicyContext, proposed: MemoryPolicyEntry) -> PolicyDecision:
    """Determine whether *context* principal may write *proposed* entry.

    Rule evaluation order (first match wins):
      0. shared_space_id guard — always deny if present
      1. private_to_principal (incl. visibility=None defensive)
      2. shareable_summary — same-principal only (V1)
      3. shared_in_space — always deny (reserved)
      4. unknown visibility — fail-closed
    """
    # Rule 0: shared_space_id guard (highest priority)
    if proposed.shared_space_id is not None:
        return PolicyDecision(allowed=False, reason="membership_unavailable")

    visibility = (
        proposed.visibility if proposed.visibility is not None else "private_to_principal"
    )

    if visibility == "private_to_principal":
        if context.principal_id is None:
            # Anonymous writer: only allow writing no-owner entries
            if proposed.owner_principal_id is None:
                return PolicyDecision(allowed=True, reason="anonymous_legacy_write")
            return PolicyDecision(allowed=False, reason="principal_mismatch")
        # Authenticated writer: only allow writing own entries
        if proposed.owner_principal_id == context.principal_id:
            return PolicyDecision(allowed=True, reason="owner_private_write")
        return PolicyDecision(allowed=False, reason="principal_mismatch")

    if visibility == "shareable_summary":
        # V1: only owner can create their own summary; anonymous cannot
        if context.principal_id is None:
            return PolicyDecision(allowed=False, reason="principal_mismatch")
        if proposed.owner_principal_id == context.principal_id:
            return PolicyDecision(allowed=True, reason="owner_summary_write")
        return PolicyDecision(allowed=False, reason="principal_mismatch")

    if visibility == "shared_in_space":
        return PolicyDecision(allowed=False, reason="shared_space_policy_not_implemented")

    return PolicyDecision(allowed=False, reason="unknown_visibility_value")
