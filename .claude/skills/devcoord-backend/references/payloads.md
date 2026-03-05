# Devcoord Backend Payload Reference

All commands via `uv run python scripts/devcoord/coord.py apply <action> --payload-stdin`.

## ack

```json
{"milestone": "m8", "phase": "p1", "gate_id": "m8-g0", "target_commit": "<sha>", "commit": "<HEAD>", "task": "implement health endpoint"}
```

Required: `milestone`, `phase`, `gate_id`, `target_commit`, `commit`, `task`.

## heartbeat

```json
{"milestone": "m8", "phase": "p1", "gate_id": "m8-g0", "branch": "feat/backend-m8-health", "task": "health endpoint — tests passing, writing integration test"}
```

Required: `milestone`, `phase`, `gate_id`, `branch`, `task`.

## phase-complete

```json
{"milestone": "m8", "phase": "p1", "gate_id": "m8-g0", "branch": "feat/backend-m8-health", "commit": "<HEAD>", "task": "health endpoint done, pushed"}
```

Required: `milestone`, `phase`, `gate_id`, `branch`, `commit`, `task`.

## recovery-check

```json
{"milestone": "m8", "phase": "p1", "gate_id": "m8-g0", "last_seen_gate": "m8-g0", "task": "resuming after restart"}
```

Required: `milestone`, `phase`, `gate_id`, `last_seen_gate`, `task`.
