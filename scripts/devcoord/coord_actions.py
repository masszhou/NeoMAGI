from __future__ import annotations

import json
from datetime import date
from typing import Any

from .model import DEFAULT_ROLES, CoordError
from .service import CoordService


def execute_action(service: CoordService, command: str, payload: dict[str, Any]) -> None:
    handler = _ACTION_HANDLERS.get(command)
    if handler is None:
        raise CoordError(f"unsupported action: {command}")
    handler(service, payload)


def _handle_init(service: CoordService, payload: dict[str, Any]) -> None:
    roles = payload.get("roles", DEFAULT_ROLES)
    if isinstance(roles, str):
        roles = _split_csv(roles)
    service.init_control_plane(
        _require_payload_str(payload, "milestone"),
        run_date=_payload_str(payload, "run_date", date.today().isoformat()),
        roles=tuple(str(role).strip() for role in roles),
    )


def _handle_open_gate(service: CoordService, payload: dict[str, Any]) -> None:
    service.open_gate(
        _require_payload_str(payload, "milestone"),
        phase=_require_payload_str(payload, "phase"),
        gate_id=_payload_alias(payload, "gate_id", "gate"),
        allowed_role=_require_payload_str(payload, "allowed_role"),
        target_commit=_require_payload_str(payload, "target_commit"),
        task=_require_payload_str(payload, "task"),
    )


def _handle_ack(service: CoordService, payload: dict[str, Any]) -> None:
    service.ack(
        _require_payload_str(payload, "milestone"),
        role=_require_payload_str(payload, "role"),
        command=_payload_alias(payload, "command", "cmd"),
        gate_id=_payload_alias(payload, "gate_id", "gate"),
        commit=_require_payload_str(payload, "commit"),
        phase=_payload_str(payload, "phase", None),
        task=_require_payload_str(payload, "task"),
    )


def _handle_heartbeat(service: CoordService, payload: dict[str, Any]) -> None:
    service.heartbeat(
        _require_payload_str(payload, "milestone"),
        role=_require_payload_str(payload, "role"),
        phase=_require_payload_str(payload, "phase"),
        status=_require_payload_str(payload, "status"),
        task=_require_payload_str(payload, "task"),
        eta_min=_optional_int(payload, "eta_min"),
        gate_id=_payload_str(payload, "gate_id", _payload_str(payload, "gate", None)),
        target_commit=_payload_str(payload, "target_commit", None),
        branch=_payload_str(payload, "branch", None),
    )


def _handle_phase_complete(service: CoordService, payload: dict[str, Any]) -> None:
    service.phase_complete(
        _require_payload_str(payload, "milestone"),
        role=_require_payload_str(payload, "role"),
        phase=_require_payload_str(payload, "phase"),
        gate_id=_payload_alias(payload, "gate_id", "gate"),
        commit=_require_payload_str(payload, "commit"),
        task=_require_payload_str(payload, "task"),
        branch=_payload_str(payload, "branch", None),
    )


def _handle_recovery_check(service: CoordService, payload: dict[str, Any]) -> None:
    service.recovery_check(
        _require_payload_str(payload, "milestone"),
        role=_require_payload_str(payload, "role"),
        last_seen_gate=_require_payload_str(payload, "last_seen_gate"),
        task=_require_payload_str(payload, "task"),
    )


def _handle_state_sync_ok(service: CoordService, payload: dict[str, Any]) -> None:
    service.state_sync_ok(
        _require_payload_str(payload, "milestone"),
        role=_require_payload_str(payload, "role"),
        gate_id=_payload_alias(payload, "gate_id", "gate"),
        target_commit=_require_payload_str(payload, "target_commit"),
        task=_require_payload_str(payload, "task"),
    )


def _handle_ping(service: CoordService, payload: dict[str, Any]) -> None:
    service.ping(
        _require_payload_str(payload, "milestone"),
        role=_require_payload_str(payload, "role"),
        phase=_require_payload_str(payload, "phase"),
        gate_id=_payload_alias(payload, "gate_id", "gate"),
        task=_require_payload_str(payload, "task"),
        target_commit=_payload_str(payload, "target_commit", None),
    )


def _handle_send_command(service: CoordService, payload: dict[str, Any]) -> None:
    service.ping(
        _require_payload_str(payload, "milestone"),
        role=_require_payload_str(payload, "role"),
        phase=_require_payload_str(payload, "phase"),
        gate_id=_payload_alias(payload, "gate_id", "gate"),
        task=_require_payload_str(payload, "task"),
        target_commit=_payload_str(payload, "target_commit", None),
        command_name=_require_payload_str(payload, "command_name"),
    )


def _handle_unconfirmed_instruction(service: CoordService, payload: dict[str, Any]) -> None:
    service.unconfirmed_instruction(
        _require_payload_str(payload, "milestone"),
        role=_require_payload_str(payload, "role"),
        command=_payload_alias(payload, "command", "cmd"),
        phase=_require_payload_str(payload, "phase"),
        gate_id=_payload_alias(payload, "gate_id", "gate"),
        task=_require_payload_str(payload, "task"),
        target_commit=_payload_str(payload, "target_commit", None),
        ping_count=_optional_int(payload, "ping_count"),
    )


def _handle_log_pending(service: CoordService, payload: dict[str, Any]) -> None:
    service.log_pending(
        _require_payload_str(payload, "milestone"),
        phase=_require_payload_str(payload, "phase"),
        task=_require_payload_str(payload, "task"),
        gate_id=_payload_str(payload, "gate_id", _payload_str(payload, "gate", None)),
        target_commit=_payload_str(payload, "target_commit", None),
    )


def _handle_stale_detected(service: CoordService, payload: dict[str, Any]) -> None:
    service.stale_detected(
        _require_payload_str(payload, "milestone"),
        role=_require_payload_str(payload, "role"),
        phase=_require_payload_str(payload, "phase"),
        task=_require_payload_str(payload, "task"),
        gate_id=_payload_str(payload, "gate_id", _payload_str(payload, "gate", None)),
        target_commit=_payload_str(payload, "target_commit", None),
        ping_count=_optional_int(payload, "ping_count"),
    )


def _handle_gate_review(service: CoordService, payload: dict[str, Any]) -> None:
    service.gate_review(
        _require_payload_str(payload, "milestone"),
        role=_require_payload_str(payload, "role"),
        phase=_require_payload_str(payload, "phase"),
        gate_id=_payload_alias(payload, "gate_id", "gate"),
        result=_require_payload_str(payload, "result"),
        report_commit=_require_payload_str(payload, "report_commit"),
        report_path=_require_payload_str(payload, "report_path"),
        task=_require_payload_str(payload, "task"),
    )


def _handle_gate_close(service: CoordService, payload: dict[str, Any]) -> None:
    service.gate_close(
        _require_payload_str(payload, "milestone"),
        phase=_require_payload_str(payload, "phase"),
        gate_id=_payload_alias(payload, "gate_id", "gate"),
        result=_require_payload_str(payload, "result"),
        report_commit=_require_payload_str(payload, "report_commit"),
        report_path=_require_payload_str(payload, "report_path"),
        task=_require_payload_str(payload, "task"),
    )


def _handle_milestone_close(service: CoordService, payload: dict[str, Any]) -> None:
    service.close_milestone(_require_payload_str(payload, "milestone"))


def _handle_audit(service: CoordService, payload: dict[str, Any]) -> None:
    print(json.dumps(service.audit(_require_payload_str(payload, "milestone")), ensure_ascii=False))


def _handle_render(service: CoordService, payload: dict[str, Any]) -> None:
    service.render(_require_payload_str(payload, "milestone"))


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _require_payload_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if value in (None, ""):
        raise CoordError(f"payload missing required field: {key}")
    return str(value)


def _payload_str(payload: dict[str, Any], key: str, default: str | None) -> str | None:
    value = payload.get(key, default)
    if value in (None, ""):
        return default
    return str(value)


def _payload_alias(payload: dict[str, Any], primary: str, alias: str) -> str:
    value = payload.get(primary)
    if value in (None, ""):
        value = payload.get(alias)
    if value in (None, ""):
        raise CoordError(f"payload missing required field: {primary}")
    return str(value)


def _optional_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    return int(value)


_ACTION_HANDLERS = {
    "init": _handle_init,
    "open-gate": _handle_open_gate,
    "ack": _handle_ack,
    "heartbeat": _handle_heartbeat,
    "phase-complete": _handle_phase_complete,
    "recovery-check": _handle_recovery_check,
    "state-sync-ok": _handle_state_sync_ok,
    "ping": _handle_ping,
    "send-command": _handle_send_command,
    "unconfirmed-instruction": _handle_unconfirmed_instruction,
    "log-pending": _handle_log_pending,
    "stale-detected": _handle_stale_detected,
    "gate-review": _handle_gate_review,
    "gate-close": _handle_gate_close,
    "milestone-close": _handle_milestone_close,
    "audit": _handle_audit,
    "render": _handle_render,
}
