---
doc_id: 019cd497-6ab8-724f-af6f-d573a1999f27
doc_id_format: uuidv7
doc_id_assigned_at: 2026-03-09T22:53:39+01:00
---
# Beads Git-JSONL Backup Migration — Restore Drill Report

- Date: 2026-03-09
- Plan: `dev_docs/plans/phase2/p2-beads_git-jsonl-backup-migration_2026-03-08.md` Slice D
- ADR: `decisions/0052-project-beads-backup-git-tracked-jsonl-exports.md`

## Environment

- Source repo: `/Users/zhiliangzhou/devel/Zhiliang/NeoMAGI` (main branch)
- Test dir: `/tmp/beads_restore_test_1772963131` (disposable, `git init`, no `.beads/dolt/`)
- bd version: as installed at drill time

## Note on `bd backup --force` auto-commit behavior

`bd backup --force` writes JSONL files to `.beads/backup/` and, when it detects a Git repo with a remote, automatically runs `git add` + `git commit` on the backup files. This is `bd`'s built-in behavior (output: "Backup committed and pushed to git"). The auto-push to Dolt remote fails (expected — that remote is deprecated), but the local Git commit succeeds. All `git show` references below point to these `bd`-created commits.

---

## Phase A: Restore from clean environment (118 issues)

Validates acceptance criterion: "在干净环境且初始不存在 `.beads/dolt/` 的前提下，`bd backup restore --dry-run` 能识别备份内容，且实际 restore 后的数据计数与 `.beads/backup/issues.jsonl` 一致"。

Baseline: 118 issues in source repo at drill start. Backup commit: `91890e8`.

### A1. Confirm source repo baseline

```
$ bd backup --force
Backup complete: 118 issues, 1092 events, 0 comments, 109 deps, 389 labels, 11 config

$ bd backup status
  Counts: 118 issues, 1092 events, ...
  Warning: dolt auto-push failed: ... fatal: remote 'origin' not found.

$ wc -l .beads/backup/issues.jsonl
     118

$ bd list --json --all | python3 -c "..."
Source repo issue count: 118
```

The `dolt auto-push` warning confirms the Dolt remote is unreachable — exactly the condition motivating this migration.

### A2. Disposable test directory setup

```
$ mkdir /tmp/beads_restore_test_1772963131 && cd $_
$ git init
$ mkdir -p .beads/backup
$ cp <source>/.beads/backup/*.jsonl .beads/backup/
$ cp <source>/.beads/backup/backup_state.json .beads/backup/
$ ls .beads/dolt/
  ls: ... No such file or directory     # confirmed: no pre-existing Dolt runtime
```

### A3. Init + dry-run restore

```
$ bd init
  ✓ bd initialized successfully!
  Backend: dolt
  Database: beads_restore_test_1772963131

$ bd backup restore --dry-run
! Dry run — no changes made
  Issues:       118
  Dependencies: 109
  Labels:       389
  Events:       1092
  Config:       11
```

### A4. Actual restore + verification

```
$ bd backup restore
✓ Restore complete
  Issues:       118
  Dependencies: 109
  Labels:       389
  Events:       1092
  Config:       11

$ bd list --json --all | python3 -c "..."
Total issues (all statuses): 118
```

Cross-check (all values at Phase A baseline):

| Source | Count |
|--------|-------|
| Source repo `bd list --json --all` | 118 |
| `.beads/backup/issues.jsonl` line count | 118 |
| Restored `bd list --json --all` | 118 |

All three match.

---

## Phase B: Mutation → backup diff (118 → 119 issues)

Validates acceptance criterion: "修改了 issue 数据后，`.beads/backup/*` 能稳定形成可提交变更"。

Performed in the source repo after Phase A.

### B1. Issue lifecycle: create → update → close

```
$ bd create "Drill: verify backup diff after mutation" -t task -p 4 --json
  → NeoMAGI-bui created (status: open)

$ bd update NeoMAGI-bui --claim --json
  → status: in_progress

$ bd close NeoMAGI-bui --reason "Drill verification complete" --json
  → status: closed
```

### B2. Backup refresh

```
$ bd backup --force
Backup complete: 119 issues, 1095 events, 0 comments, 109 deps, 389 labels, 11 config
```

`bd` auto-committed the backup diff as commit `776bd0e`:

```
$ git show --stat 776bd0e
  .beads/backup/backup_state.json | 8 ++++----
  .beads/backup/events.jsonl      | 3 +++
  .beads/backup/issues.jsonl      | 1 +
  3 files changed, 8 insertions(+), 4 deletions(-)
```

### B3. Diff analysis

| File | Delta | Explanation |
|------|-------|-------------|
| `issues.jsonl` | +1 line | 118 → 119 (new issue NeoMAGI-bui) |
| `events.jsonl` | +3 lines | 1092 → 1095 (create, claim, close events) |
| `backup_state.json` | metadata update | Dolt commit hash + timestamp refreshed |

The diff is deterministic: one issue lifecycle produces exactly one issue line and three event lines.

---

## Limitations

- `bd list` (without `--all`) defaults to open issues only; `--all` is required for total count verification.
- `bd init` derives the database name from the directory name; names with dots (e.g., `tmp.xxx`) cause Dolt to reject the name. Use alphanumeric-only directory names.
- `bd backup --force` auto-commits to Git and attempts a Dolt remote push. The push fails (expected post-migration), but the local Git commit succeeds. This auto-commit behavior means the backup diff is already committed by `bd` — the operator's responsibility is to `git push`.
- The `dolt auto-push` warning in `bd backup status` is cosmetic; it does not affect JSONL backup correctness.

## Conclusion

1. **Restore path verified** (Phase A): A clean environment with no `.beads/dolt/` recovers all 118 issues (baseline at drill time) from `.beads/backup/*.jsonl` via `bd init && bd backup restore`. Three-way count matches: source repo, JSONL line count, restored database.
2. **Mutation → backup diff verified** (Phase B): After a `bd create/update/close` cycle, `bd backup --force` produces a deterministic Git commit (`776bd0e`) with `issues.jsonl` +1 line and `events.jsonl` +3 lines. The backup is committable and pushable via normal Git workflow.
3. **Final state**: Source repo now has 119 issues (118 baseline + 1 drill issue). The backup files reflect this count.
