"""Tests for memory visibility policy checkpoint (P2-M3c, Slice C).

Covers all visibility × principal combinations for can_read() and can_write(),
including rule 0 (shared_space_id guard), defensive NULL visibility, and
requester/owner independence.
"""

from __future__ import annotations

import pytest

from src.memory.visibility import (
    MEMORY_VISIBILITY_POLICY_VERSION,
    MemoryPolicyEntry,
    PolicyContext,
    PolicyDecision,
    can_read,
    can_write,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(principal_id: str | None = None, scope: str = "main") -> PolicyContext:
    return PolicyContext(principal_id=principal_id, scope_key=scope)


def _entry(
    owner: str | None = None,
    visibility: str | None = "private_to_principal",
    shared_space_id: str | None = None,
) -> MemoryPolicyEntry:
    return MemoryPolicyEntry(
        entry_id="test-entry",
        owner_principal_id=owner,
        visibility=visibility,
        scope_key="main",
        shared_space_id=shared_space_id,
    )


# ---------------------------------------------------------------------------
# Policy version
# ---------------------------------------------------------------------------

class TestPolicyVersion:
    def test_version_is_v1(self) -> None:
        assert MEMORY_VISIBILITY_POLICY_VERSION == "v1"


# ---------------------------------------------------------------------------
# Rule 0: shared_space_id guard
# ---------------------------------------------------------------------------

class TestSharedSpaceIdGuard:
    """Rule 0: shared_space_id present → always deny, regardless of visibility."""

    @pytest.mark.parametrize("vis", [
        "private_to_principal", "shareable_summary", "shared_in_space", "unknown",
    ])
    def test_can_read_deny_any_visibility(self, vis: str) -> None:
        d = can_read(_ctx("user-1"), _entry(owner="user-1", visibility=vis, shared_space_id="sp-1"))
        assert not d.allowed
        assert d.reason == "membership_unavailable"

    @pytest.mark.parametrize("vis", [
        "private_to_principal", "shareable_summary", "shared_in_space", "unknown",
    ])
    def test_can_write_deny_any_visibility(self, vis: str) -> None:
        entry = _entry(owner="user-1", visibility=vis, shared_space_id="sp-1")
        d = can_write(_ctx("user-1"), entry)
        assert not d.allowed
        assert d.reason == "membership_unavailable"

    def test_can_read_anonymous_with_shared_space(self) -> None:
        d = can_read(_ctx(), _entry(owner=None, shared_space_id="sp-1"))
        assert not d.allowed
        assert d.reason == "membership_unavailable"

    def test_can_write_anonymous_with_shared_space(self) -> None:
        d = can_write(_ctx(), _entry(owner=None, shared_space_id="sp-1"))
        assert not d.allowed
        assert d.reason == "membership_unavailable"


# ---------------------------------------------------------------------------
# can_read: private_to_principal
# ---------------------------------------------------------------------------

class TestCanReadPrivate:
    def test_owner_reads_own(self) -> None:
        d = can_read(_ctx("user-1"), _entry(owner="user-1"))
        assert d.allowed
        assert d.reason == "owner_private_access"

    def test_authenticated_reads_legacy(self) -> None:
        d = can_read(_ctx("user-1"), _entry(owner=None))
        assert d.allowed
        assert d.reason == "owner_private_access"

    def test_anonymous_reads_legacy(self) -> None:
        d = can_read(_ctx(), _entry(owner=None))
        assert d.allowed
        assert d.reason == "anonymous_legacy_access"

    def test_cross_principal_deny(self) -> None:
        d = can_read(_ctx("user-1"), _entry(owner="user-2"))
        assert not d.allowed
        assert d.reason == "principal_mismatch"

    def test_anonymous_cannot_read_owned(self) -> None:
        d = can_read(_ctx(), _entry(owner="user-1"))
        assert not d.allowed
        assert d.reason == "principal_mismatch"


# ---------------------------------------------------------------------------
# can_read: shareable_summary
# ---------------------------------------------------------------------------

class TestCanReadSummary:
    def test_same_principal(self) -> None:
        d = can_read(_ctx("user-1"), _entry(owner="user-1", visibility="shareable_summary"))
        assert d.allowed
        assert d.reason == "same_principal"

    def test_cross_principal_deny(self) -> None:
        d = can_read(_ctx("user-1"), _entry(owner="user-2", visibility="shareable_summary"))
        assert not d.allowed
        assert d.reason == "principal_mismatch"

    def test_anonymous_deny(self) -> None:
        d = can_read(_ctx(), _entry(owner="user-1", visibility="shareable_summary"))
        assert not d.allowed
        assert d.reason == "principal_mismatch"

    def test_no_owner_summary_anonymous_deny(self) -> None:
        """No-principal shareable_summary is not legacy-visible to anonymous."""
        d = can_read(_ctx(), _entry(owner=None, visibility="shareable_summary"))
        assert not d.allowed
        assert d.reason == "principal_mismatch"

    def test_no_owner_summary_authenticated_deny(self) -> None:
        """No-principal shareable_summary is not visible to any authenticated user."""
        d = can_read(_ctx("user-1"), _entry(owner=None, visibility="shareable_summary"))
        assert not d.allowed
        assert d.reason == "principal_mismatch"


# ---------------------------------------------------------------------------
# can_read: shared_in_space (reserved, always deny)
# ---------------------------------------------------------------------------

class TestCanReadSharedInSpace:
    def test_authenticated_deny(self) -> None:
        d = can_read(_ctx("user-1"), _entry(owner="user-1", visibility="shared_in_space"))
        assert not d.allowed
        assert d.reason == "shared_space_policy_not_implemented"

    def test_anonymous_deny(self) -> None:
        d = can_read(_ctx(), _entry(owner=None, visibility="shared_in_space"))
        assert not d.allowed
        assert d.reason == "shared_space_policy_not_implemented"


# ---------------------------------------------------------------------------
# can_read: unknown visibility (fail-closed)
# ---------------------------------------------------------------------------

class TestCanReadUnknown:
    def test_unknown_visibility_deny(self) -> None:
        d = can_read(_ctx("user-1"), _entry(owner="user-1", visibility="some_new_value"))
        assert not d.allowed
        assert d.reason == "unknown_visibility_value"


# ---------------------------------------------------------------------------
# can_read: visibility=None (defensive, treated as private_to_principal)
# ---------------------------------------------------------------------------

class TestCanReadNullVisibility:
    def test_null_treated_as_private_owner(self) -> None:
        d = can_read(_ctx("user-1"), _entry(owner="user-1", visibility=None))
        assert d.allowed
        assert d.reason == "owner_private_access"

    def test_null_treated_as_private_anonymous_legacy(self) -> None:
        d = can_read(_ctx(), _entry(owner=None, visibility=None))
        assert d.allowed
        assert d.reason == "anonymous_legacy_access"

    def test_null_cross_principal_deny(self) -> None:
        d = can_read(_ctx("user-1"), _entry(owner="user-2", visibility=None))
        assert not d.allowed
        assert d.reason == "principal_mismatch"


# ---------------------------------------------------------------------------
# can_write: private_to_principal
# ---------------------------------------------------------------------------

class TestCanWritePrivate:
    def test_owner_writes_own(self) -> None:
        d = can_write(_ctx("user-1"), _entry(owner="user-1"))
        assert d.allowed
        assert d.reason == "owner_private_write"

    def test_anonymous_writes_no_owner(self) -> None:
        d = can_write(_ctx(), _entry(owner=None))
        assert d.allowed
        assert d.reason == "anonymous_legacy_write"

    def test_cross_principal_deny(self) -> None:
        d = can_write(_ctx("user-1"), _entry(owner="user-2"))
        assert not d.allowed
        assert d.reason == "principal_mismatch"

    def test_anonymous_cannot_write_owned(self) -> None:
        d = can_write(_ctx(), _entry(owner="user-1"))
        assert not d.allowed
        assert d.reason == "principal_mismatch"


# ---------------------------------------------------------------------------
# can_write: shareable_summary
# ---------------------------------------------------------------------------

class TestCanWriteSummary:
    def test_owner_write(self) -> None:
        d = can_write(_ctx("user-1"), _entry(owner="user-1", visibility="shareable_summary"))
        assert d.allowed
        assert d.reason == "owner_summary_write"

    def test_non_owner_deny(self) -> None:
        d = can_write(_ctx("user-1"), _entry(owner="user-2", visibility="shareable_summary"))
        assert not d.allowed
        assert d.reason == "principal_mismatch"

    def test_anonymous_deny(self) -> None:
        d = can_write(_ctx(), _entry(owner="user-1", visibility="shareable_summary"))
        assert not d.allowed
        assert d.reason == "principal_mismatch"


# ---------------------------------------------------------------------------
# can_write: shared_in_space (reserved, always deny)
# ---------------------------------------------------------------------------

class TestCanWriteSharedInSpace:
    def test_authenticated_deny(self) -> None:
        d = can_write(_ctx("user-1"), _entry(owner="user-1", visibility="shared_in_space"))
        assert not d.allowed
        assert d.reason == "shared_space_policy_not_implemented"

    def test_anonymous_deny(self) -> None:
        d = can_write(_ctx(), _entry(owner=None, visibility="shared_in_space"))
        assert not d.allowed
        assert d.reason == "shared_space_policy_not_implemented"


# ---------------------------------------------------------------------------
# can_write: unknown visibility (fail-closed)
# ---------------------------------------------------------------------------

class TestCanWriteUnknown:
    def test_unknown_visibility_deny(self) -> None:
        d = can_write(_ctx("user-1"), _entry(owner="user-1", visibility="something"))
        assert not d.allowed
        assert d.reason == "unknown_visibility_value"


# ---------------------------------------------------------------------------
# can_write: visibility=None (defensive)
# ---------------------------------------------------------------------------

class TestCanWriteNullVisibility:
    def test_null_treated_as_private_owner(self) -> None:
        d = can_write(_ctx("user-1"), _entry(owner="user-1", visibility=None))
        assert d.allowed
        assert d.reason == "owner_private_write"

    def test_null_treated_as_private_anonymous(self) -> None:
        d = can_write(_ctx(), _entry(owner=None, visibility=None))
        assert d.allowed
        assert d.reason == "anonymous_legacy_write"


# ---------------------------------------------------------------------------
# Requester/owner independence
# ---------------------------------------------------------------------------

class TestRequesterOwnerIndependence:
    """Verify that context.principal_id and entry.owner_principal_id are
    independently evaluated — no self-proving shortcut."""

    def test_read_different_ids(self) -> None:
        d = can_read(_ctx("alice"), _entry(owner="bob"))
        assert not d.allowed

    def test_write_different_ids(self) -> None:
        d = can_write(_ctx("alice"), _entry(owner="bob"))
        assert not d.allowed

    def test_read_summary_different_ids(self) -> None:
        d = can_read(_ctx("alice"), _entry(owner="bob", visibility="shareable_summary"))
        assert not d.allowed

    def test_write_summary_different_ids(self) -> None:
        d = can_write(_ctx("alice"), _entry(owner="bob", visibility="shareable_summary"))
        assert not d.allowed


# ---------------------------------------------------------------------------
# PolicyDecision dataclass
# ---------------------------------------------------------------------------

class TestPolicyDecision:
    def test_frozen(self) -> None:
        d = PolicyDecision(allowed=True, reason="test")
        with pytest.raises(AttributeError):
            d.allowed = False  # type: ignore[misc]
