"""Tests for the M5 preflight unified framework.

Covers:
- CheckResult/PreflightReport data models
- Each check item (C2-C11) unit tests: OK/WARN/FAIL three-state
- run_preflight combination tests
- ValidationError wrapping in lifespan
- Lifespan integration: preflight failure blocks startup
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infra.health import CheckResult, CheckStatus, PreflightReport
from src.infra.preflight import (
    _check_active_provider,
    _check_budget_tables,
    _check_db_connection,
    _check_schema_tables,
    _check_search_trigger,
    _check_soul_reconcile,
    _check_soul_versions,
    _check_telegram,
    _check_workspace_dirs,
    _check_workspace_path_consistency,
    run_preflight,
)


def _mock_engine_with_conn(conn: AsyncMock) -> AsyncMock:
    """Create a mock engine whose connect() returns an async context manager."""
    engine = AsyncMock()

    @asynccontextmanager
    async def _connect():
        yield conn

    engine.connect = _connect
    return engine

# ---------------------------------------------------------------------------
# Data model tests
# ---------------------------------------------------------------------------


class TestPreflightReport:
    def test_passed_when_no_checks(self):
        report = PreflightReport()
        assert report.passed is True

    def test_passed_when_all_ok(self):
        report = PreflightReport(
            checks=[
                CheckResult("a", CheckStatus.OK, "", "", ""),
                CheckResult("b", CheckStatus.OK, "", "", ""),
            ]
        )
        assert report.passed is True

    def test_passed_when_warn_present(self):
        report = PreflightReport(
            checks=[
                CheckResult("a", CheckStatus.OK, "", "", ""),
                CheckResult("b", CheckStatus.WARN, "drift", "minor", "fix"),
            ]
        )
        assert report.passed is True

    def test_not_passed_when_fail_present(self):
        report = PreflightReport(
            checks=[
                CheckResult("a", CheckStatus.OK, "", "", ""),
                CheckResult("b", CheckStatus.FAIL, "broken", "critical", "fix"),
            ]
        )
        assert report.passed is False

    def test_summary_contains_status(self):
        report = PreflightReport(
            checks=[CheckResult("db", CheckStatus.OK, "connected", "", "")]
        )
        summary = report.summary()
        assert "PASSED" in summary
        assert "db" in summary

    def test_summary_failed(self):
        report = PreflightReport(
            checks=[CheckResult("db", CheckStatus.FAIL, "timeout", "down", "restart")]
        )
        summary = report.summary()
        assert "FAILED" in summary


# ---------------------------------------------------------------------------
# C2: Active provider config
# ---------------------------------------------------------------------------


class TestCheckActiveProvider:
    def test_openai_ok(self):
        settings = MagicMock()
        settings.provider.active = "openai"
        settings.openai.api_key = "sk-test"
        result = _check_active_provider(settings)
        assert result.status == CheckStatus.OK
        assert result.name == "active_provider"

    def test_openai_missing_key(self):
        settings = MagicMock()
        settings.provider.active = "openai"
        settings.openai.api_key = ""
        result = _check_active_provider(settings)
        assert result.status == CheckStatus.FAIL
        assert "OPENAI_API_KEY" in result.next_action

    def test_gemini_ok(self):
        settings = MagicMock()
        settings.provider.active = "gemini"
        settings.gemini.api_key = "test-key"
        result = _check_active_provider(settings)
        assert result.status == CheckStatus.OK

    def test_gemini_missing_key(self):
        settings = MagicMock()
        settings.provider.active = "gemini"
        settings.gemini.api_key = ""
        result = _check_active_provider(settings)
        assert result.status == CheckStatus.FAIL
        assert "GEMINI_API_KEY" in result.next_action


# ---------------------------------------------------------------------------
# C3: Workspace path consistency
# ---------------------------------------------------------------------------


class TestCheckWorkspacePath:
    def test_consistent_paths(self, tmp_path):
        settings = MagicMock()
        settings.workspace_dir = tmp_path
        settings.memory.workspace_path = tmp_path
        result = _check_workspace_path_consistency(settings)
        assert result.status == CheckStatus.OK

    def test_inconsistent_paths(self, tmp_path):
        settings = MagicMock()
        settings.workspace_dir = tmp_path
        settings.memory.workspace_path = tmp_path / "different"
        result = _check_workspace_path_consistency(settings)
        assert result.status == CheckStatus.FAIL
        assert "ADR 0037" in result.next_action


# ---------------------------------------------------------------------------
# C4: Workspace directories
# ---------------------------------------------------------------------------


class TestCheckWorkspaceDirs:
    def test_dirs_exist_and_writable(self, tmp_path):
        (tmp_path / "memory").mkdir()
        settings = MagicMock()
        settings.workspace_dir = tmp_path
        result = _check_workspace_dirs(settings)
        assert result.status == CheckStatus.OK

    def test_workspace_dir_missing(self, tmp_path):
        settings = MagicMock()
        settings.workspace_dir = tmp_path / "nonexistent"
        result = _check_workspace_dirs(settings)
        assert result.status == CheckStatus.FAIL
        assert "not found" in result.evidence

    def test_memory_dir_missing(self, tmp_path):
        settings = MagicMock()
        settings.workspace_dir = tmp_path  # exists
        # memory/ subdir doesn't exist
        result = _check_workspace_dirs(settings)
        assert result.status == CheckStatus.FAIL
        assert "memory dir not found" in result.evidence


# ---------------------------------------------------------------------------
# C5: DB connection
# ---------------------------------------------------------------------------


class TestCheckDBConnection:
    @pytest.mark.asyncio
    async def test_db_ok(self):
        conn = AsyncMock()
        conn.execute = AsyncMock()
        engine = _mock_engine_with_conn(conn)
        result = await _check_db_connection(engine)
        assert result.status == CheckStatus.OK

    @pytest.mark.asyncio
    async def test_db_unreachable(self):
        engine = AsyncMock()

        @asynccontextmanager
        async def _fail_connect():
            raise ConnectionRefusedError("refused")
            yield  # pragma: no cover — needed for asynccontextmanager

        engine.connect = _fail_connect
        result = await _check_db_connection(engine)
        assert result.status == CheckStatus.FAIL
        assert "ConnectionRefusedError" in result.evidence


# ---------------------------------------------------------------------------
# C6: Schema tables
# ---------------------------------------------------------------------------


class TestCheckSchemaTables:
    @pytest.mark.asyncio
    async def test_all_tables_present(self):
        conn = AsyncMock()
        rows = [("sessions",), ("messages",), ("soul_versions",), ("memory_entries",)]
        result_mock = MagicMock()
        result_mock.fetchall.return_value = rows
        conn.execute = AsyncMock(return_value=result_mock)
        engine = _mock_engine_with_conn(conn)

        result = await _check_schema_tables(engine)
        assert result.status == CheckStatus.OK

    @pytest.mark.asyncio
    async def test_missing_tables(self):
        conn = AsyncMock()
        rows = [("sessions",), ("messages",)]
        result_mock = MagicMock()
        result_mock.fetchall.return_value = rows
        conn.execute = AsyncMock(return_value=result_mock)
        engine = _mock_engine_with_conn(conn)

        result = await _check_schema_tables(engine)
        assert result.status == CheckStatus.FAIL
        assert "Missing tables" in result.evidence


# ---------------------------------------------------------------------------
# C7: Search trigger (WARN)
# ---------------------------------------------------------------------------


class TestCheckSearchTrigger:
    @pytest.mark.asyncio
    async def test_trigger_exists(self):
        conn = AsyncMock()
        result_mock = MagicMock()
        result_mock.fetchone.return_value = (1,)
        conn.execute = AsyncMock(return_value=result_mock)
        engine = _mock_engine_with_conn(conn)

        result = await _check_search_trigger(engine)
        assert result.status == CheckStatus.OK

    @pytest.mark.asyncio
    async def test_trigger_missing(self):
        conn = AsyncMock()
        result_mock = MagicMock()
        result_mock.fetchone.return_value = None
        conn.execute = AsyncMock(return_value=result_mock)
        engine = _mock_engine_with_conn(conn)

        result = await _check_search_trigger(engine)
        assert result.status == CheckStatus.WARN
        assert "not found" in result.evidence


# ---------------------------------------------------------------------------
# C8: Budget tables (FAIL)
# ---------------------------------------------------------------------------


class TestCheckBudgetTables:
    @pytest.mark.asyncio
    async def test_both_tables_present(self):
        conn = AsyncMock()
        rows = [("budget_state",), ("budget_reservations",)]
        result_mock = MagicMock()
        result_mock.fetchall.return_value = rows
        conn.execute = AsyncMock(return_value=result_mock)
        engine = _mock_engine_with_conn(conn)

        result = await _check_budget_tables(engine)
        assert result.status == CheckStatus.OK

    @pytest.mark.asyncio
    async def test_budget_tables_missing(self):
        conn = AsyncMock()
        rows = [("budget_state",)]  # missing budget_reservations
        result_mock = MagicMock()
        result_mock.fetchall.return_value = rows
        conn.execute = AsyncMock(return_value=result_mock)
        engine = _mock_engine_with_conn(conn)

        result = await _check_budget_tables(engine)
        assert result.status == CheckStatus.FAIL
        assert "budget_reservations" in result.evidence

    @pytest.mark.asyncio
    async def test_both_missing(self):
        conn = AsyncMock()
        result_mock = MagicMock()
        result_mock.fetchall.return_value = []
        conn.execute = AsyncMock(return_value=result_mock)
        engine = _mock_engine_with_conn(conn)

        result = await _check_budget_tables(engine)
        assert result.status == CheckStatus.FAIL


# ---------------------------------------------------------------------------
# C9: soul_versions readable
# ---------------------------------------------------------------------------


class TestCheckSoulVersions:
    @pytest.mark.asyncio
    async def test_table_readable(self):
        conn = AsyncMock()
        conn.execute = AsyncMock()
        engine = _mock_engine_with_conn(conn)

        result = await _check_soul_versions(engine)
        assert result.status == CheckStatus.OK

    @pytest.mark.asyncio
    async def test_table_unreadable(self):
        conn = AsyncMock()
        conn.execute = AsyncMock(side_effect=Exception("relation does not exist"))
        engine = _mock_engine_with_conn(conn)

        result = await _check_soul_versions(engine)
        assert result.status == CheckStatus.FAIL


# ---------------------------------------------------------------------------
# C10: Telegram auth
# ---------------------------------------------------------------------------


class TestCheckTelegram:
    @pytest.mark.asyncio
    async def test_telegram_disabled(self):
        settings = MagicMock()
        settings.telegram.bot_token = ""
        result = await _check_telegram(settings)
        assert result.status == CheckStatus.OK
        assert "disabled" in result.evidence

    @pytest.mark.asyncio
    async def test_telegram_auth_ok(self):
        settings = MagicMock()
        settings.telegram.bot_token = "fake:token"

        me = MagicMock()
        me.username = "testbot"
        mock_bot = MagicMock()
        mock_bot.get_me = AsyncMock(return_value=me)
        mock_bot.session.close = AsyncMock()

        with patch("aiogram.Bot", return_value=mock_bot) as mock_cls:
            result = await _check_telegram(settings)
            mock_cls.assert_called_once_with(token="fake:token")

        assert result.status == CheckStatus.OK
        assert "testbot" in result.evidence

    @pytest.mark.asyncio
    async def test_telegram_auth_fail(self):
        settings = MagicMock()
        settings.telegram.bot_token = "bad:token"

        mock_bot = MagicMock()
        mock_bot.get_me = AsyncMock(side_effect=Exception("Unauthorized"))
        mock_bot.session.close = AsyncMock()

        with patch("aiogram.Bot", return_value=mock_bot):
            result = await _check_telegram(settings)

        assert result.status == CheckStatus.FAIL
        assert "Unauthorized" in result.evidence


# ---------------------------------------------------------------------------
# C11: SOUL.md reconcile
# ---------------------------------------------------------------------------


class TestCheckSoulReconcile:
    @pytest.mark.asyncio
    async def test_reconcile_no_drift(self, tmp_path):
        """No drift: SOUL.md content matches before and after reconcile."""
        soul_path = tmp_path / "SOUL.md"
        soul_path.write_text("soul content", encoding="utf-8")

        settings = MagicMock()
        settings.workspace_dir = tmp_path
        engine = AsyncMock()

        mock_evolution = AsyncMock()
        mock_evolution.reconcile_soul_projection = AsyncMock()  # no-op

        with (
            patch("src.memory.evolution.EvolutionEngine", return_value=mock_evolution),
            patch("src.infra.preflight.make_session_factory"),
        ):
            result = await _check_soul_reconcile(settings, engine)

        assert result.status == CheckStatus.OK

    @pytest.mark.asyncio
    async def test_reconcile_with_drift(self, tmp_path):
        """Drift detected: SOUL.md content changes after reconcile → WARN."""
        soul_path = tmp_path / "SOUL.md"
        soul_path.write_text("old content", encoding="utf-8")

        settings = MagicMock()
        settings.workspace_dir = tmp_path
        engine = AsyncMock()

        async def _reconcile_and_write():
            soul_path.write_text("new content from DB", encoding="utf-8")

        mock_evolution = AsyncMock()
        mock_evolution.reconcile_soul_projection = AsyncMock(side_effect=_reconcile_and_write)

        with (
            patch("src.memory.evolution.EvolutionEngine", return_value=mock_evolution),
            patch("src.infra.preflight.make_session_factory"),
        ):
            result = await _check_soul_reconcile(settings, engine)

        assert result.status == CheckStatus.WARN
        assert "drift" in result.evidence

    @pytest.mark.asyncio
    async def test_reconcile_exception(self, tmp_path):
        """Reconcile failure → WARN (not FAIL)."""
        settings = MagicMock()
        settings.workspace_dir = tmp_path
        engine = AsyncMock()

        mock_evolution = AsyncMock()
        mock_evolution.reconcile_soul_projection = AsyncMock(
            side_effect=Exception("DB error")
        )

        with (
            patch("src.memory.evolution.EvolutionEngine", return_value=mock_evolution),
            patch("src.infra.preflight.make_session_factory"),
        ):
            result = await _check_soul_reconcile(settings, engine)

        assert result.status == CheckStatus.WARN
        assert "DB error" in result.evidence


# ---------------------------------------------------------------------------
# run_preflight combination tests
# ---------------------------------------------------------------------------


class TestRunPreflight:
    @pytest.mark.asyncio
    async def test_all_ok(self, tmp_path):
        """All checks pass → report.passed is True."""
        (tmp_path / "memory").mkdir()

        settings = MagicMock()
        settings.provider.active = "openai"
        settings.openai.api_key = "sk-test"
        settings.workspace_dir = tmp_path
        settings.memory.workspace_path = tmp_path
        settings.telegram.bot_token = ""

        conn = AsyncMock()

        # Return all required tables + budget tables
        all_tables = [
            ("sessions",), ("messages",), ("soul_versions",),
            ("memory_entries",), ("budget_state",), ("budget_reservations",),
        ]
        table_result = MagicMock()
        table_result.fetchall.return_value = all_tables
        # Trigger exists
        trigger_result = MagicMock()
        trigger_result.fetchone.return_value = (1,)

        call_count = 0

        async def _mock_execute(stmt, params=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MagicMock()  # C5: SELECT 1
            if call_count == 2:
                return table_result  # C6: schema tables
            if call_count == 3:
                return trigger_result  # C7: trigger check
            if call_count == 4:
                return table_result  # C8: budget tables
            return MagicMock()  # C9: soul_versions

        conn.execute = AsyncMock(side_effect=_mock_execute)
        engine = _mock_engine_with_conn(conn)

        mock_evolution = AsyncMock()
        mock_evolution.reconcile_soul_projection = AsyncMock()
        (tmp_path / "SOUL.md").write_text("soul", encoding="utf-8")

        with (
            patch("src.memory.evolution.EvolutionEngine", return_value=mock_evolution),
            patch("src.infra.preflight.make_session_factory"),
        ):
            report = await run_preflight(settings, engine)

        assert report.passed is True
        assert len(report.checks) == 10  # C2-C11

    @pytest.mark.asyncio
    async def test_fail_blocks(self, tmp_path):
        """A FAIL check → report.passed is False."""
        settings = MagicMock()
        settings.provider.active = "openai"
        settings.openai.api_key = ""  # C2 will FAIL
        settings.workspace_dir = tmp_path
        settings.memory.workspace_path = tmp_path
        settings.telegram.bot_token = ""
        (tmp_path / "memory").mkdir()
        (tmp_path / "SOUL.md").write_text("", encoding="utf-8")

        conn = AsyncMock()
        all_tables = [
            ("sessions",), ("messages",), ("soul_versions",),
            ("memory_entries",), ("budget_state",), ("budget_reservations",),
        ]
        table_result = MagicMock()
        table_result.fetchall.return_value = all_tables
        trigger_result = MagicMock()
        trigger_result.fetchone.return_value = (1,)
        conn.execute = AsyncMock(return_value=table_result)
        engine = _mock_engine_with_conn(conn)

        mock_evolution = AsyncMock()
        mock_evolution.reconcile_soul_projection = AsyncMock()

        with (
            patch("src.memory.evolution.EvolutionEngine", return_value=mock_evolution),
            patch("src.infra.preflight.make_session_factory"),
        ):
            report = await run_preflight(settings, engine)

        assert report.passed is False
        failed = [c for c in report.checks if c.status == CheckStatus.FAIL]
        assert any(c.name == "active_provider" for c in failed)

    @pytest.mark.asyncio
    async def test_db_fail_skips_dependent_checks(self):
        """DB connection failure → C6-C9 all FAIL with skip evidence."""
        settings = MagicMock()
        settings.provider.active = "openai"
        settings.openai.api_key = "sk-test"
        settings.workspace_dir = Path("/tmp/test-ws")
        settings.memory.workspace_path = Path("/tmp/test-ws")
        settings.telegram.bot_token = ""

        engine = AsyncMock()

        @asynccontextmanager
        async def _fail_connect():
            raise ConnectionRefusedError("refused")
            yield  # pragma: no cover

        engine.connect = _fail_connect

        with (
            patch("src.infra.preflight._check_workspace_dirs") as mock_ws,
            patch("src.infra.preflight._check_soul_reconcile") as mock_reconcile,
            patch("src.infra.preflight._check_telegram") as mock_tg,
        ):
            mock_ws.return_value = CheckResult(
                "workspace_dirs", CheckStatus.OK, "ok", "", ""
            )
            mock_reconcile.return_value = CheckResult(
                "soul_reconcile", CheckStatus.OK, "ok", "", ""
            )
            mock_tg.return_value = CheckResult(
                "telegram_auth", CheckStatus.OK, "disabled", "", ""
            )
            report = await run_preflight(settings, engine)

        assert report.passed is False
        # DB fail + 4 skipped dependent checks = 5 FAIL checks
        failed = [c for c in report.checks if c.status == CheckStatus.FAIL]
        assert len(failed) == 5
        skipped = [c for c in failed if "Skipped" in c.evidence]
        assert len(skipped) == 4

    @pytest.mark.asyncio
    async def test_warn_does_not_block(self, tmp_path):
        """WARN checks do not block: report.passed is True."""
        (tmp_path / "memory").mkdir()

        settings = MagicMock()
        settings.provider.active = "openai"
        settings.openai.api_key = "sk-test"
        settings.workspace_dir = tmp_path
        settings.memory.workspace_path = tmp_path
        settings.telegram.bot_token = ""

        conn = AsyncMock()

        all_tables = [
            ("sessions",), ("messages",), ("soul_versions",),
            ("memory_entries",), ("budget_state",), ("budget_reservations",),
        ]
        table_result = MagicMock()
        table_result.fetchall.return_value = all_tables
        # Trigger missing → WARN
        trigger_result = MagicMock()
        trigger_result.fetchone.return_value = None

        call_count = 0

        async def _mock_execute(stmt, params=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MagicMock()
            if call_count == 2:
                return table_result
            if call_count == 3:
                return trigger_result
            if call_count == 4:
                return table_result
            return MagicMock()

        conn.execute = AsyncMock(side_effect=_mock_execute)
        engine = _mock_engine_with_conn(conn)

        (tmp_path / "SOUL.md").write_text("soul", encoding="utf-8")
        mock_evolution = AsyncMock()
        mock_evolution.reconcile_soul_projection = AsyncMock()

        with (
            patch("src.memory.evolution.EvolutionEngine", return_value=mock_evolution),
            patch("src.infra.preflight.make_session_factory"),
        ):
            report = await run_preflight(settings, engine)

        assert report.passed is True
        warns = [c for c in report.checks if c.status == CheckStatus.WARN]
        assert len(warns) >= 1  # At least C7 trigger missing


# ---------------------------------------------------------------------------
# ValidationError wrapping in lifespan
# ---------------------------------------------------------------------------


class TestValidationErrorWrapping:
    @pytest.mark.asyncio
    async def test_validation_error_logged_and_reraised(self):
        """Missing required config → ValidationError with structured log."""
        from pydantic import ValidationError as PydanticValidationError

        from src.gateway.app import lifespan

        app = MagicMock()

        with (
            patch("src.gateway.app.setup_logging"),
            patch("src.gateway.app.get_settings") as mock_settings,
        ):
            mock_settings.side_effect = PydanticValidationError.from_exception_data(
                "Settings",
                [
                    {
                        "type": "missing",
                        "loc": ("openai", "api_key"),
                        "msg": "Field required",
                        "input": {},
                    }
                ],
            )

            with pytest.raises(PydanticValidationError):
                async with lifespan(app):
                    pass


# ---------------------------------------------------------------------------
# Lifespan integration: preflight failure blocks startup
# ---------------------------------------------------------------------------


class TestLifespanPreflightIntegration:
    @pytest.mark.asyncio
    async def test_preflight_fail_blocks_startup(self, tmp_path):
        """Preflight FAIL → lifespan raises RuntimeError."""
        from src.gateway.app import lifespan

        app = MagicMock()
        app.state = MagicMock()

        fake_engine = AsyncMock()
        fake_engine.dispose = AsyncMock()

        failing_report = PreflightReport(
            checks=[
                CheckResult(
                    "db_connection",
                    CheckStatus.FAIL,
                    "Connection refused",
                    "All persistence fails",
                    "Check DB",
                ),
            ]
        )

        with (
            patch("src.gateway.app.setup_logging"),
            patch("src.gateway.app.get_settings") as mock_settings,
            patch("src.gateway.app.create_db_engine", return_value=fake_engine),
            patch("src.gateway.app.ensure_schema", return_value=None),
            patch("src.gateway.app.make_session_factory"),
            patch("src.gateway.app.run_preflight", return_value=failing_report),
        ):
            from src.config.settings import (
                CompactionSettings,
                GeminiSettings,
                MemorySettings,
                ProviderSettings,
                TelegramSettings,
            )

            settings = MagicMock()
            settings.workspace_dir = tmp_path
            settings.memory = MemorySettings(workspace_path=tmp_path)
            settings.provider = ProviderSettings()
            settings.gemini = GeminiSettings()
            settings.compaction = CompactionSettings()
            settings.telegram = TelegramSettings(bot_token="")
            settings.openai.api_key = "test"
            settings.openai.base_url = None
            settings.openai.model = "gpt-4o-mini"
            settings.database.schema_ = "neomagi"
            settings.gateway.host = "0.0.0.0"
            settings.gateway.port = 19789
            settings.session.default_mode = "chat_safe"
            mock_settings.return_value = settings

            with pytest.raises(RuntimeError, match="Preflight failed"):
                async with lifespan(app):
                    pass

    @pytest.mark.asyncio
    async def test_preflight_report_stored_in_app_state(self, tmp_path):
        """Passing preflight → report stored in app.state.preflight_report."""
        from src.gateway.app import lifespan

        app = MagicMock()
        app.state = MagicMock()

        fake_engine = AsyncMock()
        fake_engine.dispose = AsyncMock()

        passing_report = PreflightReport(
            checks=[
                CheckResult("test", CheckStatus.OK, "ok", "", ""),
            ]
        )

        with (
            patch("src.gateway.app.setup_logging"),
            patch("src.gateway.app.get_settings") as mock_settings,
            patch("src.gateway.app.create_db_engine", return_value=fake_engine),
            patch("src.gateway.app.ensure_schema", return_value=None),
            patch("src.gateway.app.make_session_factory"),
            patch("src.gateway.app.run_preflight", return_value=passing_report),
            patch("src.gateway.app.EvolutionEngine") as mock_ev_cls,
        ):
            mock_ev = AsyncMock()
            mock_ev.reconcile_soul_projection = AsyncMock()
            mock_ev_cls.return_value = mock_ev

            from src.config.settings import (
                CompactionSettings,
                GeminiSettings,
                MemorySettings,
                ProviderSettings,
                TelegramSettings,
            )

            settings = MagicMock()
            settings.workspace_dir = tmp_path
            settings.memory = MemorySettings(workspace_path=tmp_path)
            settings.provider = ProviderSettings()
            settings.gemini = GeminiSettings()
            settings.compaction = CompactionSettings()
            settings.telegram = TelegramSettings(bot_token="")
            settings.openai.api_key = "test"
            settings.openai.base_url = None
            settings.openai.model = "gpt-4o-mini"
            settings.database.schema_ = "neomagi"
            settings.gateway.host = "0.0.0.0"
            settings.gateway.port = 19789
            settings.session = MagicMock()
            settings.session.default_mode = "chat_safe"
            mock_settings.return_value = settings

            async with lifespan(app):
                assert app.state.preflight_report == passing_report
