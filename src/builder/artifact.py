"""Artifact generation, rendering, and persistence for builder work memory.

Responsibilities:
- generate_artifact_id(): stable ID for artifact records
- render_artifact_markdown(): BuilderTaskRecord -> markdown text
- write_artifact(): persist markdown to workspace/artifacts/

All I/O is async (aiofiles). No PostgreSQL dependency (ADR 0055).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import aiofiles
import structlog

from src.builder.types import BuilderTaskRecord

logger = structlog.get_logger(__name__)


def generate_artifact_id() -> str:
    """Generate a stable artifact ID.

    TODO: Upgrade to UUIDv7 for time-ordered IDs when a suitable
    implementation is available. Using uuid4 as V1 fallback to avoid
    introducing a new dependency solely for this (ADR 0055 / ADR 0057).
    """
    return str(uuid.uuid4())


def _render_list_section(
    lines: list[str], heading: str, items: tuple[str, ...], *, prefix: str = "- ",
) -> None:
    """Append a markdown section with a bullet list if *items* is non-empty."""
    if not items:
        return
    lines += [f"## {heading}", ""]
    lines += [f"{prefix}{item}" for item in items]
    lines.append("")


def _render_text_section(lines: list[str], heading: str, text: str | None) -> None:
    """Append a markdown section with a single text body if *text* is truthy."""
    if not text:
        return
    lines += [f"## {heading}", "", text, ""]


def render_artifact_markdown(record: BuilderTaskRecord) -> str:
    """Render a BuilderTaskRecord as a markdown artifact document."""
    lines: list[str] = [f"# Builder Task: {record.task_brief}", ""]
    lines.append(f"- **artifact_id**: `{record.artifact_id}`")
    if record.bead_id:
        lines.append(f"- **bead_id**: `{record.bead_id}`")
    lines += [f"- **scope**: {record.scope}", ""]

    _render_list_section(lines, "Decision Snapshots", record.decision_snapshots)
    _render_list_section(lines, "TODO Items", record.todo_items, prefix="- [ ] ")
    _render_list_section(lines, "Blockers", record.blockers)
    _render_list_section(lines, "Artifact References", record.artifact_refs)
    _render_text_section(lines, "Validation Summary", record.validation_summary)
    _render_list_section(lines, "Promote Candidates", record.promote_candidates)
    _render_text_section(lines, "Next Recommended Action", record.next_recommended_action)

    return "\n".join(lines)


async def write_artifact(record: BuilderTaskRecord, base_dir: Path) -> Path:
    """Write a BuilderTaskRecord as a markdown file under *base_dir*.

    The file is placed at ``<base_dir>/builder_runs/<artifact_id>.md``.
    Parent directories are created if needed.

    Returns the path to the written file.
    """
    target_dir = base_dir / "builder_runs"
    target_dir.mkdir(parents=True, exist_ok=True)

    file_path = target_dir / f"{record.artifact_id}.md"
    content = render_artifact_markdown(record)

    async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
        await f.write(content)

    logger.info(
        "artifact_written",
        artifact_id=record.artifact_id,
        path=str(file_path),
    )
    return file_path
