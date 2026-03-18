"""Builder work memory lifecycle: create, update, link.

Orchestrates artifact persistence (workspace/artifacts/) and
best-effort bd issue indexing (ADR 0055 dual-layer model).

All I/O is async. bd CLI interactions are best-effort: if the CLI
is unavailable or a command fails, the function degrades gracefully
to artifact-only mode (ADR 0055 fallback).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import structlog

from src.builder.artifact import generate_artifact_id, write_artifact
from src.builder.types import BuilderTaskRecord

logger = structlog.get_logger(__name__)


async def _run_bd_command(*args: str) -> tuple[bool, str]:
    """Run a bd CLI command and return (success, stdout).

    Best-effort: returns (False, stderr) on any failure.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "bd",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        if proc.returncode == 0:
            return True, stdout.decode("utf-8", errors="replace")
        return False, stderr.decode("utf-8", errors="replace")
    except (FileNotFoundError, TimeoutError, OSError) as exc:
        logger.warning("bd_command_failed", args=args, error=str(exc))
        return False, str(exc)


async def _try_create_bead(task_brief: str, artifact_id: str) -> str | None:
    """Best-effort: create a bd issue and return its ID, or None on failure."""
    ok, output = await _run_bd_command("create", task_brief, "--json")
    if not ok:
        return None
    try:
        bead_id = json.loads(output).get("id")
        logger.info("bead_created", bead_id=bead_id, artifact_id=artifact_id)
        return bead_id
    except (json.JSONDecodeError, KeyError):
        logger.warning("bead_create_parse_failed", output=output[:200])
        return None


async def create_builder_task(
    task_brief: str,
    scope: str,
    base_dir: Path,
    *,
    decision_snapshots: tuple[str, ...] = (),
    todo_items: tuple[str, ...] = (),
    blockers: tuple[str, ...] = (),
    artifact_refs: tuple[str, ...] = (),
) -> BuilderTaskRecord:
    """Create a new builder task: artifact + optional bead index.

    1. Generates artifact_id
    2. Optionally creates a bd issue (best-effort)
    3. Writes canonical artifact to workspace/artifacts/
    4. Returns the immutable BuilderTaskRecord
    """
    artifact_id = generate_artifact_id()
    bead_id = await _try_create_bead(task_brief, artifact_id)

    record = BuilderTaskRecord(
        artifact_id=artifact_id,
        bead_id=bead_id,
        task_brief=task_brief,
        scope=scope,
        decision_snapshots=decision_snapshots,
        todo_items=todo_items,
        blockers=blockers,
        artifact_refs=artifact_refs,
    )

    await write_artifact(record, base_dir)

    if bead_id:
        artifact_path = base_dir / "builder_runs" / f"{artifact_id}.md"
        await _run_bd_command(
            "comments", "add", bead_id, f"artifact: {artifact_path}",
        )

    return record


_UPDATABLE_FIELDS: tuple[str, ...] = (
    "decision_snapshots", "todo_items", "blockers", "artifact_refs",
    "validation_summary", "promote_candidates", "next_recommended_action",
)


async def update_task_progress(
    record: BuilderTaskRecord,
    base_dir: Path,
    **kwargs: object,
) -> BuilderTaskRecord:
    """Update a builder task's progress: re-render artifact + optional bead comment.

    Accepts any subset of updatable fields as keyword arguments (see
    ``_UPDATABLE_FIELDS``).  Creates a new immutable record (frozen model),
    overwrites the artifact file via ``write_artifact``, and best-effort
    posts a progress comment to the linked bead.
    """
    updates = {k: v for k, v in kwargs.items() if k in _UPDATABLE_FIELDS and v is not None}
    updated = record.model_copy(update=updates)

    await write_artifact(updated, base_dir)
    logger.info("artifact_updated", artifact_id=updated.artifact_id, fields=list(updates.keys()))

    if updated.bead_id and updates:
        summary = ", ".join(updates.keys())
        await _run_bd_command(
            "comments", "add", updated.bead_id, f"progress update: {summary}",
        )

    return updated


async def link_artifact_to_bead(bead_id: str, artifact_path: Path) -> None:
    """Add an artifact reference as a comment on an existing bead.

    Best-effort: logs a warning and returns on failure.
    """
    ok, output = await _run_bd_command(
        "comments", "add", bead_id,
        f"artifact: {artifact_path}",
    )
    if ok:
        logger.info("artifact_linked", bead_id=bead_id, path=str(artifact_path))
    else:
        logger.warning(
            "artifact_link_failed",
            bead_id=bead_id,
            path=str(artifact_path),
            error=output[:200],
        )
