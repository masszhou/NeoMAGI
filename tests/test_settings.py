"""Tests for SessionSettings.dm_scope and TelegramSettings (Phase 0, ADR 0034)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.config.settings import SessionSettings, TelegramSettings


class TestSessionSettingsDmScope:
    def test_default_dm_scope_is_main(self) -> None:
        s = SessionSettings()
        assert s.dm_scope == "main"

    def test_explicit_main_accepted(self) -> None:
        s = SessionSettings(dm_scope="main")
        assert s.dm_scope == "main"

    def test_non_main_rejected(self) -> None:
        with pytest.raises(ValidationError, match="SESSION_DM_SCOPE must be 'main'"):
            SessionSettings(dm_scope="per-peer")

    def test_empty_string_rejected(self) -> None:
        with pytest.raises(ValidationError, match="SESSION_DM_SCOPE must be 'main'"):
            SessionSettings(dm_scope="")

    def test_default_mode_unchanged(self) -> None:
        s = SessionSettings()
        assert s.default_mode == "chat_safe"


class TestTelegramSettings:
    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
        monkeypatch.delenv("TELEGRAM_DM_SCOPE", raising=False)
        monkeypatch.delenv("TELEGRAM_MESSAGE_MAX_LENGTH", raising=False)
        s = TelegramSettings()
        assert s.bot_token == ""
        assert s.dm_scope == "per-channel-peer"
        assert s.allowed_user_ids == ""
        assert s.message_max_length == 4096

    def test_per_channel_peer_accepted(self) -> None:
        s = TelegramSettings(dm_scope="per-channel-peer")
        assert s.dm_scope == "per-channel-peer"

    def test_per_peer_accepted(self) -> None:
        s = TelegramSettings(dm_scope="per-peer")
        assert s.dm_scope == "per-peer"

    def test_main_accepted(self) -> None:
        s = TelegramSettings(dm_scope="main")
        assert s.dm_scope == "main"

    def test_invalid_dm_scope_rejected(self) -> None:
        with pytest.raises(ValidationError, match="TELEGRAM_DM_SCOPE must be one of"):
            TelegramSettings(dm_scope="invalid")

    def test_empty_dm_scope_rejected(self) -> None:
        with pytest.raises(ValidationError, match="TELEGRAM_DM_SCOPE must be one of"):
            TelegramSettings(dm_scope="")


class TestTelegramMessageMaxLength:
    """F4: message_max_length boundary validation."""

    def test_default_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
        monkeypatch.delenv("TELEGRAM_DM_SCOPE", raising=False)
        monkeypatch.delenv("TELEGRAM_MESSAGE_MAX_LENGTH", raising=False)
        s = TelegramSettings()
        assert s.message_max_length == 4096

    def test_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TelegramSettings(message_max_length=0)

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TelegramSettings(message_max_length=-1)

    def test_exceeds_telegram_limit_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TelegramSettings(message_max_length=5000)

    def test_valid_custom_value(self) -> None:
        s = TelegramSettings(message_max_length=2048)
        assert s.message_max_length == 2048
