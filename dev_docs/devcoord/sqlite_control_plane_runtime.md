---
doc_id: 019cccd7-5108-75c9-b6be-1773a7519449
doc_id_format: uuidv7
doc_id_assigned_at: 2026-03-08T10:46:29+01:00
---
# SQLite Control Plane Runtime

> 状态：approved
> 日期：2026-03-07
> 适用范围：NeoMAGI devcoord 日常操作（非产品运行时）

## 1. 概述

devcoord 控制面使用 SQLite 作为唯一 SSOT（`.devcoord/control.db`）。beads backend 已在 Stage D 中正式退役。

架构设计详见 [`design_docs/devcoord_sqlite_control_plane.md`](/design_docs/devcoord_sqlite_control_plane.md)。

## 2. 日常操作

所有控制面写入统一通过：

```bash
uv run python scripts/devcoord/coord.py <group> <subcommand> [options]
```

### 2.1 命令面（Canonical Grouped CLI）

| Group | Subcommand | 用途 |
|-------|-----------|------|
| `init` | — | 初始化控制面 |
| `gate` | `open` / `review` / `close` | Gate 生命周期 |
| `command` | `ack` / `send` | 指令确认 / 发送 (send: PING, STOP, WAIT, RESUME) |
| `event` | `heartbeat` / `phase-complete` / `recovery-check` / `state-sync-ok` / `stale-detected` / `log-pending` / `unconfirmed-instruction` | 协议事件 |
| `projection` | `render` / `audit` | 投影生成与对账 |
| `milestone` | `close` | 关闭 milestone |
| `apply` | `<action>` | 结构化 JSON payload 入口 |

Legacy flat 命令（如 `open-gate`、`render`）仍可用作兼容别名。

### 2.2 已退役参数

以下参数在 Stage D 中正式退役，使用时会触发 fail-fast 错误：

- `--backend`
- `--beads-dir`
- `--bd-bin`
- `--dolt-bin`

## 3. Gate Lifecycle

```
gate open → command ack → event heartbeat* → event phase-complete
  → gate review → projection render → projection audit → gate close
```

## 4. Closeout Checklist

milestone 关闭的标准流程：

1. `gate review` — 提交审阅证据
2. `projection render` — 生成投影
3. `projection audit` — 对账（要求 `reconciled=true`）
4. `gate close` — 关闭 gate
5. `projection render` — 再次生成投影（反映 gate close 后状态）
6. `projection audit` — 再次对账
7. `milestone close` — 关闭 milestone

关键守卫：

- `gate close` 前必须存在匹配的 `GATE_REVIEW_COMPLETE` 事件
- `gate close` 前必须 `audit.reconciled=true`
- `milestone close` 前所有 gate 必须已关闭
- `milestone close` 不依赖 beads sync

## 5. Projection 文件

由 `projection render` 生成，不直接手写：

- `dev_docs/logs/<phase>/{milestone}_{YYYY-MM-DD}/heartbeat_events.jsonl`
- `dev_docs/logs/<phase>/{milestone}_{YYYY-MM-DD}/gate_state.md`
- `dev_docs/logs/<phase>/{milestone}_{YYYY-MM-DD}/watchdog_status.md`
- `dev_docs/progress/project_progress.md`

## 6. 与 beads / bd 的关系

- `bd` 仍用于 backlog / issue tracking
- devcoord control-plane 写入**不再**触发 beads backup
- beads issue 数据修改后使用 `just beads-backup` + 普通 `git add / commit / push`（ADR 0052）

## 7. Historical Cutover Checklist

Stage D 一次性 cutover 产出（完成后本节仅作历史记录）：

1. 确认无 active milestone 仍依赖 beads backend
2. 列出历史 `coord` beads 对象：`bd list --all --include-infra --json > /tmp/legacy-devcoord-beads.json`
3. 按 `coord` label 筛出历史 control-plane 对象
4. 对识别出的历史对象执行关闭：`bd close <id> --reason "Legacy devcoord beads control plane retired by Stage D"`
5. 验证 `bd list --status open` 不再包含 live devcoord 对象
6. 验证 SQLite closeout smoke：`projection render -> projection audit -> milestone close`

**不导入历史 beads control-plane 数据到 SQLite。历史证据文档不做改写。**
