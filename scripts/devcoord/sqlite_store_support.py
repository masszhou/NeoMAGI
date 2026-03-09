from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from typing import Any

from .model import COORD_LABEL, KIND_KEY, CoordError
from .store import CoordRecord

_MESSAGE_PAYLOAD_EXCLUDED = frozenset(
    {
        KIND_KEY,
        "milestone",
        "gate_id",
        "phase",
        "command",
        "role",
        "target_commit",
        "requires_ack",
        "effective",
        "sent_at",
        "acked_at",
        "ack_role",
        "ack_commit",
    }
)
_EVENT_PAYLOAD_EXCLUDED = frozenset(
    {
        KIND_KEY,
        "milestone",
        "event_seq",
        "phase",
        "gate",
        "role",
        "event",
        "status",
        "task",
        "target_commit",
        "result",
        "report_path",
        "report_commit",
        "branch",
        "eta_min",
        "source_message_id",
        "ts",
    }
)


def split_record_id(record_id: str) -> tuple[str, str]:
    parts = record_id.split(":", 1)
    if len(parts) != 2:
        raise CoordError(f"invalid record_id format: {record_id}")
    return parts[0], parts[1]


def build_message_insert_values(meta: dict[str, Any]) -> tuple[Any, ...]:
    return (
        meta["milestone"],
        meta.get("gate_id", ""),
        meta.get("phase", ""),
        meta.get("command", ""),
        meta.get("role", ""),
        meta.get("target_commit", ""),
        1 if meta.get("requires_ack", True) else 0,
        1 if meta.get("effective", False) else 0,
        meta.get("sent_at", ""),
        _payload_json(meta, _MESSAGE_PAYLOAD_EXCLUDED),
    )


def build_event_insert_values(meta: dict[str, Any]) -> tuple[Any, ...]:
    return (
        meta["milestone"],
        meta.get("event_seq", 0),
        meta.get("phase", ""),
        meta.get("gate", ""),
        meta.get("role", ""),
        meta.get("event", ""),
        meta.get("status", ""),
        meta.get("task", ""),
        meta.get("target_commit", ""),
        meta.get("result", ""),
        meta.get("report_path", ""),
        meta.get("report_commit", ""),
        meta.get("branch", ""),
        meta.get("eta_min"),
        _parse_source_message_id(meta.get("source_message_id", "")),
        _payload_json(meta, _EVENT_PAYLOAD_EXCLUDED),
        meta.get("ts", ""),
    )


def message_update_assignments(
    metadata: dict[str, Any] | None,
    status: str | None,
) -> tuple[tuple[str, Any], ...]:
    assignments = list(_metadata_assignments(metadata or {}, _MESSAGE_UPDATE_FIELDS))
    if status == "closed":
        assignments.append(("record_closed", 1))
    return tuple(assignments)


def milestone_to_record(row: sqlite3.Row, schema_version: int) -> CoordRecord:
    milestone_id = row["milestone_id"]
    return CoordRecord(
        record_id=f"ms:{milestone_id}",
        title=f"Coord milestone {milestone_id}",
        description=f"NeoMAGI devcoord control plane for {milestone_id}.",
        record_type="epic",
        status="open" if row["status"] == "active" else "closed",
        labels=coord_labels("milestone", milestone_id),
        metadata={
            KIND_KEY: "milestone",
            "milestone": milestone_id,
            "run_date": row["run_date"],
            "schema_version": schema_version,
        },
        created_at=row["created_at"],
        closed_at=row["closed_at"],
    )


def phase_to_record(row: sqlite3.Row) -> CoordRecord:
    milestone_id = row["milestone_id"]
    phase_id = row["phase_id"]
    return CoordRecord(
        record_id=f"ph:{milestone_id}|{phase_id}",
        title=f"Coord phase {phase_id}",
        description=f"Coordination phase {phase_id} for {milestone_id}.",
        record_type="task",
        status="closed" if row["phase_state"] == "closed" else "open",
        labels=coord_labels("phase", milestone_id, phase=phase_id),
        metadata={
            KIND_KEY: "phase",
            "milestone": milestone_id,
            "phase": phase_id,
            "phase_state": row["phase_state"],
            "last_commit": row["last_commit"] or "",
        },
    )


def gate_to_record(row: sqlite3.Row) -> CoordRecord:
    milestone_id = row["milestone_id"]
    gate_id = row["gate_id"]
    return CoordRecord(
        record_id=f"gt:{milestone_id}|{gate_id}",
        title=f"Gate {gate_id}",
        description=f"Gate {gate_id} for phase {row['phase_id']}.",
        record_type="task",
        status="closed" if row["gate_state"] == "closed" else "open",
        labels=coord_labels("gate", milestone_id, phase=row["phase_id"], role=row["allowed_role"]),
        metadata={
            KIND_KEY: "gate",
            "milestone": milestone_id,
            "phase": row["phase_id"],
            "gate_id": gate_id,
            "allowed_role": row["allowed_role"],
            "target_commit": row["target_commit"] or "",
            "gate_state": row["gate_state"],
            "result": row["result"] or "",
            "report_path": row["report_path"] or "",
            "report_commit": row["report_commit"] or "",
            "opened_at": row["opened_at"] or "",
            "closed_at": row["closed_at"] or "",
        },
    )


def role_to_record(row: sqlite3.Row) -> CoordRecord:
    milestone_id = row["milestone_id"]
    role = row["role"]
    return CoordRecord(
        record_id=f"rl:{milestone_id}|{role}",
        title=f"Agent {role}",
        description=f"Coordination state for {role}.",
        record_type="task",
        status="closed" if row["agent_state"] == "closed" else "open",
        labels=coord_labels("agent", milestone_id, role=role),
        metadata={
            KIND_KEY: "agent",
            "milestone": milestone_id,
            "role": role,
            "agent_state": row["agent_state"],
            "action": row["action"] or "",
            "current_task": row["current_task"] or "",
            "last_activity": row["last_activity"] or "",
            "stale_risk": row["stale_risk"] or "none",
        },
    )


def message_to_record(row: sqlite3.Row) -> CoordRecord:
    payload = _decode_payload(row["payload_json"])
    metadata = {
        KIND_KEY: "message",
        "milestone": row["milestone_id"],
        "gate_id": row["gate_id"] or "",
        "phase": row["phase_id"] or "",
        "command": row["command_name"],
        "role": row["target_role"],
        "target_commit": row["target_commit"] or "",
        "requires_ack": bool(row["requires_ack"]),
        "effective": bool(row["effective"]),
        "sent_at": row["sent_at"],
        "acked_at": row["acked_at"] or "",
        "ack_role": row["ack_role"] or "",
        "ack_commit": row["ack_commit"] or "",
    }
    metadata.update(payload)
    return CoordRecord(
        record_id=f"mg:{row['message_id']}",
        title=f"{row['command_name']} -> {row['target_role']}",
        description=payload.get("task", ""),
        record_type="task",
        status="closed" if row["record_closed"] else "open",
        labels=coord_labels(
            "message",
            row["milestone_id"],
            phase=row["phase_id"],
            role=row["target_role"],
        ),
        metadata=metadata,
        assignee=row["target_role"],
    )


def event_to_record(row: sqlite3.Row) -> CoordRecord:
    payload = _decode_payload(row["payload_json"])
    metadata: dict[str, Any] = {
        KIND_KEY: "event",
        "milestone": row["milestone_id"],
        "event_seq": row["event_seq"],
        "phase": row["phase_id"] or "",
        "gate": row["gate_id"] or "",
        "role": row["role"] or "",
        "event": row["event_type"],
        "status": row["status"] or "",
        "task": row["task"],
        "target_commit": row["target_commit"] or "",
        "result": row["result"] or "",
        "report_path": row["report_path"] or "",
        "report_commit": row["report_commit"] or "",
        "branch": row["branch"] or "",
        "eta_min": row["eta_min"],
        "source_message_id": f"mg:{row['source_message_id']}" if row["source_message_id"] else "",
        "ts": row["created_at"],
    }
    metadata.update(payload)
    return CoordRecord(
        record_id=f"ev:{row['event_id']}",
        title=f"{row['event_type']} {row['role'] or ''} phase {row['phase_id'] or 'na'}",
        description=row["task"],
        record_type="task",
        status="closed" if row["record_closed"] else "open",
        labels=coord_labels("event", row["milestone_id"], phase=row["phase_id"], role=row["role"]),
        metadata=metadata,
    )


def coord_labels(
    kind: str,
    milestone: str,
    *,
    phase: str | None = None,
    role: str | None = None,
) -> tuple[str, ...]:
    labels = [COORD_LABEL, f"coord-kind-{kind}", f"coord-milestone-{milestone}"]
    if phase:
        labels.append(f"coord-phase-{phase}")
    if role:
        labels.append(f"coord-role-{role}")
    return tuple(sorted(labels))


def _payload_json(meta: dict[str, Any], excluded: set[str] | frozenset[str]) -> str:
    payload = {key: value for key, value in meta.items() if key not in excluded}
    return json.dumps(payload, ensure_ascii=False)


def _parse_source_message_id(source_message_id: Any) -> int | None:
    if not source_message_id:
        return None
    try:
        return int(str(source_message_id).split(":")[-1])
    except (ValueError, IndexError):
        return None


def _metadata_assignments(
    metadata: dict[str, Any],
    fields: tuple[tuple[str, Callable[[Any], Any]], ...],
) -> tuple[tuple[str, Any], ...]:
    return tuple(
        (column, transform(metadata[column]))
        for column, transform in fields
        if column in metadata
    )


def _decode_payload(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _identity(value: Any) -> Any:
    return value


_MESSAGE_UPDATE_FIELDS: tuple[tuple[str, Callable[[Any], Any]], ...] = (
    ("effective", lambda value: 1 if value else 0),
    ("acked_at", _identity),
    ("ack_role", _identity),
    ("ack_commit", _identity),
)
