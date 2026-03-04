"""Preflight startup checks: unified framework replacing scattered lifespan validations.

Each check produces a CheckResult with OK/WARN/FAIL status plus diagnostic evidence.
Any FAIL blocks service startup; WARN items are logged but don't block.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from src.constants import DB_SCHEMA
from src.infra.health import CheckResult, CheckStatus, PreflightReport
from src.session.database import make_session_factory

if TYPE_CHECKING:
    from src.config.settings import Settings

logger = structlog.get_logger()

# Tables that must exist for the service to function
_REQUIRED_TABLES = {"sessions", "messages", "soul_versions", "memory_entries"}
_BUDGET_TABLES = {"budget_state", "budget_reservations"}
_SEARCH_TRIGGER_NAME = "trg_memory_entries_search_vector"


async def run_preflight(settings: Settings, db_engine: AsyncEngine) -> PreflightReport:
    """Execute all preflight checks and return a structured report.

    Checks C2-C11 per m5_architecture.md §6.1.
    """
    report = PreflightReport()

    # C2: active provider config closure
    report.checks.append(_check_active_provider(settings))

    # C3: workspace_dir / memory.workspace_path consistency
    report.checks.append(_check_workspace_path_consistency(settings))

    # C4: workspace required directories exist and writable
    report.checks.append(_check_workspace_dirs(settings))

    # C5: DB connectable
    report.checks.append(await _check_db_connection(db_engine))

    # C6-C9 require DB connectivity; skip if C5 failed
    if report.checks[-1].status == CheckStatus.FAIL:
        for name, impact in [
            ("schema_tables", "Cannot verify schema integrity"),
            ("search_trigger", "Cannot verify search trigger"),
            ("budget_tables", "Cannot verify budget tables"),
            ("soul_versions_readable", "Cannot verify soul versions table"),
        ]:
            report.checks.append(
                CheckResult(
                    name=name,
                    status=CheckStatus.FAIL,
                    evidence="Skipped: DB connection failed",
                    impact=impact,
                    next_action="Fix DB connection first",
                )
            )
    else:
        # C6: schema + required tables exist
        report.checks.append(await _check_schema_tables(db_engine))
        # C7: search trigger exists (WARN)
        report.checks.append(await _check_search_trigger(db_engine))
        # C8: budget tables exist (FAIL)
        report.checks.append(await _check_budget_tables(db_engine))
        # C9: soul_versions readable
        report.checks.append(await _check_soul_versions(db_engine))

    # C10: Telegram connector auth (only when enabled)
    report.checks.append(await _check_telegram(settings))

    # C11: SOUL.md reconcile (writes file at startup, WARN on drift)
    report.checks.append(await _check_soul_reconcile(settings, db_engine))

    return report


def _check_active_provider(settings: Settings) -> CheckResult:
    """C2: active provider must be fully configured."""
    active = settings.provider.active
    if active == "openai":
        if not settings.openai.api_key:
            return CheckResult(
                name="active_provider",
                status=CheckStatus.FAIL,
                evidence=f"Active provider '{active}' has no API key configured",
                impact="No LLM provider available; all requests will fail",
                next_action="Set OPENAI_API_KEY in .env",
            )
    elif active == "gemini":
        if not settings.gemini.api_key:
            return CheckResult(
                name="active_provider",
                status=CheckStatus.FAIL,
                evidence=f"Active provider '{active}' has no API key configured",
                impact="No LLM provider available; all requests will fail",
                next_action="Set GEMINI_API_KEY in .env",
            )
    return CheckResult(
        name="active_provider",
        status=CheckStatus.OK,
        evidence=f"Provider '{active}' configured",
        impact="",
        next_action="",
    )


def _check_workspace_path_consistency(settings: Settings) -> CheckResult:
    """C3: workspace_dir and memory.workspace_path must be consistent (ADR 0037)."""
    ws_dir = settings.workspace_dir.resolve()
    mem_path = settings.memory.workspace_path.resolve()
    if ws_dir != mem_path:
        return CheckResult(
            name="workspace_path",
            status=CheckStatus.FAIL,
            evidence=(
                f"workspace_dir={settings.workspace_dir}, "
                f"memory.workspace_path={settings.memory.workspace_path}"
            ),
            impact="Memory operations will target wrong directory",
            next_action="Align workspace_dir and MEMORY_WORKSPACE_PATH. See ADR 0037",
        )
    return CheckResult(
        name="workspace_path",
        status=CheckStatus.OK,
        evidence=f"Consistent: {ws_dir}",
        impact="",
        next_action="",
    )


def _check_workspace_dirs(settings: Settings) -> CheckResult:
    """C4: workspace and workspace/memory/ must exist and be writable."""
    ws = settings.workspace_dir.resolve()
    memory_dir = ws / "memory"
    issues: list[str] = []
    if not ws.is_dir():
        issues.append(f"workspace_dir not found: {ws}")
    elif not _is_writable(ws):
        issues.append(f"workspace_dir not writable: {ws}")
    if not memory_dir.is_dir():
        issues.append(f"memory dir not found: {memory_dir}")
    elif not _is_writable(memory_dir):
        issues.append(f"memory dir not writable: {memory_dir}")

    if issues:
        return CheckResult(
            name="workspace_dirs",
            status=CheckStatus.FAIL,
            evidence="; ".join(issues),
            impact="Cannot write memory files or SOUL.md projection",
            next_action="Create directories and ensure write permissions",
        )
    return CheckResult(
        name="workspace_dirs",
        status=CheckStatus.OK,
        evidence=f"Directories accessible: {ws}",
        impact="",
        next_action="",
    )


def _is_writable(path: object) -> bool:
    """Check if a Path is writable using os.access."""
    import os

    return os.access(path, os.W_OK)


async def _check_db_connection(engine: AsyncEngine) -> CheckResult:
    """C5: DB must be connectable."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return CheckResult(
            name="db_connection",
            status=CheckStatus.OK,
            evidence="PostgreSQL reachable",
            impact="",
            next_action="",
        )
    except Exception as exc:
        return CheckResult(
            name="db_connection",
            status=CheckStatus.FAIL,
            evidence=f"Connection failed: {type(exc).__name__}: {exc}",
            impact="All persistence operations will fail",
            next_action="Check DATABASE_* env vars and PostgreSQL availability",
        )


async def _check_schema_tables(engine: AsyncEngine) -> CheckResult:
    """C6: schema exists and required tables are present."""
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = :schema"
                ),
                {"schema": DB_SCHEMA},
            )
            existing = {row[0] for row in result.fetchall()}

        missing = _REQUIRED_TABLES - existing
        if missing:
            return CheckResult(
                name="schema_tables",
                status=CheckStatus.FAIL,
                evidence=f"Missing tables: {sorted(missing)}",
                impact="Core functionality unavailable",
                next_action="Run ensure_schema() or check migration state",
            )
        return CheckResult(
            name="schema_tables",
            status=CheckStatus.OK,
            evidence=f"All {len(_REQUIRED_TABLES)} required tables present",
            impact="",
            next_action="",
        )
    except Exception as exc:
        return CheckResult(
            name="schema_tables",
            status=CheckStatus.FAIL,
            evidence=f"Schema check failed: {type(exc).__name__}: {exc}",
            impact="Cannot verify database schema",
            next_action="Check database connectivity and permissions",
        )


async def _check_search_trigger(engine: AsyncEngine) -> CheckResult:
    """C7: memory_entries search vector trigger exists (WARN if missing)."""
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT 1 FROM information_schema.triggers "
                    "WHERE trigger_schema = :schema "
                    "AND trigger_name = :trigger_name"
                ),
                {"schema": DB_SCHEMA, "trigger_name": _SEARCH_TRIGGER_NAME},
            )
            if result.fetchone():
                return CheckResult(
                    name="search_trigger",
                    status=CheckStatus.OK,
                    evidence=f"Trigger '{_SEARCH_TRIGGER_NAME}' exists",
                    impact="",
                    next_action="",
                )
            return CheckResult(
                name="search_trigger",
                status=CheckStatus.WARN,
                evidence=f"Trigger '{_SEARCH_TRIGGER_NAME}' not found",
                impact="Memory search vector auto-population disabled",
                next_action="Run ensure_schema() to recreate trigger",
            )
    except Exception as exc:
        return CheckResult(
            name="search_trigger",
            status=CheckStatus.WARN,
            evidence=f"Trigger check failed: {type(exc).__name__}: {exc}",
            impact="Cannot verify search trigger",
            next_action="Check database connectivity",
        )


async def _check_budget_tables(engine: AsyncEngine) -> CheckResult:
    """C8: budget_state + budget_reservations tables must exist (FAIL).

    BudgetGate.try_reserve() is called on every request in dispatch_chat().
    Missing tables cause immediate crash on first request.
    """
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = :schema "
                    "AND table_name IN ('budget_state', 'budget_reservations')"
                ),
                {"schema": DB_SCHEMA},
            )
            existing = {row[0] for row in result.fetchall()}

        missing = _BUDGET_TABLES - existing
        if missing:
            return CheckResult(
                name="budget_tables",
                status=CheckStatus.FAIL,
                evidence=f"Missing budget tables: {sorted(missing)}",
                impact="First request will crash (BudgetGate.try_reserve fails)",
                next_action="Run ensure_schema() to create budget tables",
            )
        return CheckResult(
            name="budget_tables",
            status=CheckStatus.OK,
            evidence="Budget tables present",
            impact="",
            next_action="",
        )
    except Exception as exc:
        return CheckResult(
            name="budget_tables",
            status=CheckStatus.FAIL,
            evidence=f"Budget table check failed: {type(exc).__name__}: {exc}",
            impact="Cannot verify budget tables",
            next_action="Check database connectivity",
        )


async def _check_soul_versions(engine: AsyncEngine) -> CheckResult:
    """C9: soul_versions table must be readable."""
    try:
        async with engine.connect() as conn:
            await conn.execute(
                text(f"SELECT 1 FROM {DB_SCHEMA}.soul_versions LIMIT 1")
            )
        return CheckResult(
            name="soul_versions_readable",
            status=CheckStatus.OK,
            evidence="soul_versions table readable",
            impact="",
            next_action="",
        )
    except Exception as exc:
        return CheckResult(
            name="soul_versions_readable",
            status=CheckStatus.FAIL,
            evidence=f"soul_versions read failed: {type(exc).__name__}: {exc}",
            impact="Evolution engine cannot function",
            next_action="Run ensure_schema() or check table permissions",
        )


async def _check_telegram(settings: Settings) -> CheckResult:
    """C10: Telegram connector auth (only when bot_token is configured)."""
    if not settings.telegram.bot_token:
        return CheckResult(
            name="telegram_auth",
            status=CheckStatus.OK,
            evidence="Telegram disabled (no bot_token)",
            impact="",
            next_action="",
        )

    try:
        from aiogram import Bot

        bot = Bot(token=settings.telegram.bot_token)
        try:
            me = await bot.get_me()
            username = me.username or "(no username)"
            return CheckResult(
                name="telegram_auth",
                status=CheckStatus.OK,
                evidence=f"Bot authenticated: @{username}",
                impact="",
                next_action="",
            )
        finally:
            await bot.session.close()
    except Exception as exc:
        return CheckResult(
            name="telegram_auth",
            status=CheckStatus.FAIL,
            evidence=f"Telegram auth failed: {type(exc).__name__}: {exc}",
            impact="Telegram channel will not be available",
            next_action="Check TELEGRAM_BOT_TOKEN in .env",
        )


async def _check_soul_reconcile(settings: Settings, engine: AsyncEngine) -> CheckResult:
    """C11: SOUL.md projection reconcile.

    Executes reconcile at startup (writes file if drift detected).
    Drift is WARN, not FAIL — reconcile fixes it automatically.
    """
    try:
        from src.memory.evolution import EvolutionEngine

        db_factory = make_session_factory(engine)
        evolution = EvolutionEngine(db_factory, settings.workspace_dir, settings.memory)

        # Capture file content before reconcile to detect drift
        soul_path = settings.workspace_dir / "SOUL.md"
        before = soul_path.read_text(encoding="utf-8") if soul_path.is_file() else None

        await evolution.reconcile_soul_projection()

        after = soul_path.read_text(encoding="utf-8") if soul_path.is_file() else None

        if before != after:
            return CheckResult(
                name="soul_reconcile",
                status=CheckStatus.WARN,
                evidence="SOUL.md drift detected and reconciled from DB",
                impact="File was out of sync; now corrected",
                next_action="No action needed (auto-reconciled)",
            )
        return CheckResult(
            name="soul_reconcile",
            status=CheckStatus.OK,
            evidence="SOUL.md projection consistent with DB",
            impact="",
            next_action="",
        )
    except Exception as exc:
        return CheckResult(
            name="soul_reconcile",
            status=CheckStatus.WARN,
            evidence=f"Reconcile issue: {type(exc).__name__}: {exc}",
            impact="SOUL.md may be out of sync with DB",
            next_action="Run 'just reconcile' manually",
        )
