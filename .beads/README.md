# Beads - AI-Native Issue Tracking

This repository uses **Beads** (`bd`) for issue tracking.

**Learn more:** [github.com/steveyegge/beads](https://github.com/steveyegge/beads)

## Architecture

```
.beads/
├── dolt/          # Local Dolt runtime database (NOT tracked by Git, see .gitignore)
├── backup/        # JSONL backup files (tracked by Git — canonical recovery artifacts)
│   ├── issues.jsonl
│   ├── dependencies.jsonl
│   ├── events.jsonl
│   ├── comments.jsonl
│   ├── labels.jsonl
│   ├── config.jsonl
│   └── backup_state.json
├── config.yaml    # bd configuration
└── hooks/         # bd git hooks (thin wrappers over `bd hooks run`)
```

- **Local runtime**: `bd` reads/writes `.beads/dolt/*`. Each write auto-commits to local Dolt history.
- **Recovery artifacts**: `.beads/backup/*.jsonl` are Git-tracked JSONL exports. This is the canonical off-machine backup path (ADR 0052).
- **Dolt remote sync is deprecated**: `bd dolt push` / `bd dolt pull` / `bd sync` are NOT used. See ADR 0052.

## Quick Start

```bash
# Create issues
bd create "Add user authentication"

# View all issues
bd list

# View issue details
bd show <issue-id>

# Update issue status
bd update <issue-id> --claim
bd update <issue-id> --status done
```

## Backup & Restore

### After modifying issue data

```bash
# Refresh JSONL backup (auto-creates a local backup commit)
just beads-backup          # or: bd backup --force

# Check backup status
just beads-backup-status   # or: bd backup status

# Push the backup commit to remote
git push

# Fallback: if bd did not auto-commit, do it manually:
# git add .beads/backup/ && git commit -m "bd: backup <date>" && git push
```

### Restoring from a fresh clone (no `.beads/dolt/`)

```bash
bd init
bd backup restore --dry-run   # preview what will be restored
bd backup restore             # actual restore
bd list                       # verify data integrity
```

## Why Beads?

- **AI-Native**: CLI-first, JSON output, designed for AI coding agents
- **Git-Friendly**: Issues live in your repo, backup via normal Git workflow
- **Dependency-Aware**: Track blockers and relationships between issues
- **Works Offline**: Local Dolt runtime, sync when you push

## More Info

- [github.com/steveyegge/beads/docs](https://github.com/steveyegge/beads/tree/main/docs)
- Run `bd quickstart` for interactive guide
