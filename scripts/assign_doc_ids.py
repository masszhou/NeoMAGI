"""Assign UUIDv7 doc_id frontmatter to markdown files in design_docs/ and dev_docs/.

Both UUIDv7 timestamp and doc_id_assigned_at are derived from each file's
last git commit time. UUIDv7 is for machines, assigned_at is for humans.

Usage:
    uv run python scripts/assign_doc_ids.py                # dry-run (default)
    uv run python scripts/assign_doc_ids.py --apply        # write changes
    uv run python scripts/assign_doc_ids.py --apply --force  # overwrite existing

Important: if files were previously touched by a frontmatter-only commit, pass
--ref <commit-before-that> to get the correct content-change timestamp:
    uv run python scripts/assign_doc_ids.py --apply --force --ref HEAD~1
"""

from __future__ import annotations

import argparse
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path


TARGETS = ["design_docs", "dev_docs"]
REPO_ROOT = Path(__file__).resolve().parent.parent


def uuid7_from_timestamp(ts_seconds: float) -> uuid.UUID:
    """Generate UUIDv7 with a custom unix timestamp (seconds)."""
    ts_ms = int(ts_seconds * 1000)
    rand_bytes = os.urandom(10)
    rand_a = int.from_bytes(rand_bytes[:2], "big") & 0x0FFF
    rand_b = int.from_bytes(rand_bytes[2:], "big") & 0x3FFFFFFFFFFFFFFF
    high = (ts_ms << 16) | (0x7 << 12) | rand_a
    low = (0b10 << 62) | rand_b
    return uuid.UUID(int=(high << 64) | low)


def git_last_commit_iso(filepath: Path, ref: str | None = None) -> str | None:
    """Return the author date in ISO 8601 format of the last commit touching filepath."""
    cmd = ["git", "log", "-1", "--format=%aI"]
    if ref:
        cmd.append(ref)
    cmd.extend(["--", str(filepath)])
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=REPO_ROOT, check=True,
        )
        return result.stdout.strip() or None
    except subprocess.CalledProcessError:
        return None


def git_last_commit_unix(filepath: Path, ref: str | None = None) -> float | None:
    """Return the author timestamp (unix seconds) of the last commit touching filepath."""
    cmd = ["git", "log", "-1", "--format=%at"]
    if ref:
        cmd.append(ref)
    cmd.extend(["--", str(filepath)])
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=REPO_ROOT, check=True,
        )
        ts = result.stdout.strip()
        return float(ts) if ts else None
    except subprocess.CalledProcessError:
        return None


def has_doc_id_frontmatter(content: str) -> bool:
    """Check if the file already has a doc_id in YAML frontmatter."""
    if not content.startswith("---"):
        return False
    end = content.find("\n---", 3)
    if end == -1:
        return False
    return "doc_id:" in content[3:end]


def strip_doc_id_frontmatter(content: str) -> str:
    """Remove existing doc_id frontmatter, return the body."""
    if not content.startswith("---"):
        return content
    end = content.find("\n---", 3)
    if end == -1:
        return content
    if "doc_id:" not in content[3:end]:
        return content
    # Skip past closing "---\n"
    body_start = end + 4
    if body_start < len(content) and content[body_start] == "\n":
        body_start += 1  # skip blank line after frontmatter
    return content[body_start:]


def build_frontmatter(doc_id: uuid.UUID, assigned_at: str) -> str:
    return (
        f"---\n"
        f"doc_id: {doc_id}\n"
        f"doc_id_format: uuidv7\n"
        f"doc_id_assigned_at: {assigned_at}\n"
        f"---\n"
    )


def collect_md_files() -> list[Path]:
    files: list[Path] = []
    for target in TARGETS:
        target_dir = REPO_ROOT / target
        if not target_dir.is_dir():
            continue
        for md in sorted(target_dir.rglob("*.md")):
            if md.is_file():
                files.append(md)
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="Assign UUIDv7 doc_id to markdown files")
    parser.add_argument("--apply", action="store_true", help="Write changes (default is dry-run)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing doc_id frontmatter")
    parser.add_argument(
        "--ref", default=None,
        help="Git ref to query timestamps from (e.g. HEAD~1 to skip a prior frontmatter commit)",
    )
    args = parser.parse_args()

    files = collect_md_files()
    skipped = 0
    assigned = 0

    for filepath in files:
        content = filepath.read_text(encoding="utf-8")

        if has_doc_id_frontmatter(content):
            if not args.force:
                skipped += 1
                continue
            content = strip_doc_id_frontmatter(content)

        git_ts = git_last_commit_unix(filepath, ref=args.ref)
        git_iso = git_last_commit_iso(filepath, ref=args.ref)
        if git_ts is None:
            git_ts = filepath.stat().st_mtime
            git_iso = datetime.fromtimestamp(git_ts, tz=timezone.utc).isoformat(timespec="seconds")

        doc_id = uuid7_from_timestamp(git_ts)
        frontmatter = build_frontmatter(doc_id, git_iso)

        rel = filepath.relative_to(REPO_ROOT)
        ts_short = datetime.fromtimestamp(git_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        print(f"{'WRITE' if args.apply else 'DRY  '} {rel}  →  {doc_id}  ({ts_short} UTC)")

        if args.apply:
            filepath.write_text(frontmatter + content, encoding="utf-8")

        assigned += 1

    action = "assigned" if args.apply else "would assign"
    print(f"\nDone: {assigned} {action}, {skipped} skipped (already have doc_id)")


if __name__ == "__main__":
    main()
