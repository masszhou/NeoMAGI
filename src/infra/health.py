"""Preflight health check data models.

Provides structured result types for startup and diagnostic checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CheckStatus(Enum):
    """Three-state check outcome."""

    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class CheckResult:
    """Single check outcome with diagnostic evidence."""

    name: str
    status: CheckStatus
    evidence: str
    impact: str
    next_action: str


@dataclass
class PreflightReport:
    """Aggregated preflight results."""

    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True if no FAIL checks exist."""
        return all(c.status != CheckStatus.FAIL for c in self.checks)

    def summary(self) -> str:
        """Format a human-readable summary of all checks."""
        lines: list[str] = []
        for c in self.checks:
            icon = {"ok": "OK", "warn": "WARN", "fail": "FAIL"}[c.status.value]
            lines.append(f"  [{icon}] {c.name}: {c.evidence}")
        status = "PASSED" if self.passed else "FAILED"
        header = f"Preflight {status} ({len(self.checks)} checks)"
        return "\n".join([header, *lines])
