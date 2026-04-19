---
doc_id: 019da594-dd6e-723b-937d-d4c0c1578d14
doc_id_format: uuidv7
doc_id_assigned_at: 2026-04-19T13:51:29+02:00
---
# 0063-memory-truth-postgres-with-workspace-projection

- Status: proposed
- Date: 2026-04-19
- Refines: ADR 0060
- Related: `design_docs/phase3/p3_daily_use_architecture_draft.md`

## 背景

ADR 0060 已将机器写入 memory truth 从 workspace Markdown 调整为 DB append-only source ledger，并把 workspace 文件定位为 projection / export surface。

P3 daily-use 计划进一步收缩实现口径：趁真实使用刚开始，不做长期双写迁移，不做文件与数据库双向同步，不把 Markdown 的手工编辑作为自动真源。目标是尽快形成单一 memory truth，避免在 daily-use 阶段背负双主一致性成本。

## 选了什么

- Postgres memory ledger 是机器写入 memory 的唯一真源。
- Workspace Markdown memory 文件是 human-readable projection / export，不是写入真源。
- `memory_append` 写入顺序为：
  1. 先写 DB；
  2. DB 成功后同步 append 到 Markdown projection；
  3. projection 失败不回滚 DB。
- Markdown projection 可以从 DB 重建。
- Projection 文件必须标注：`This file is auto-generated. Manual edits will be lost.`
- P3 初版不做历史迁移，除非后续真实使用证明需要。
- 手工文件编辑如需进入 memory truth，必须通过显式 import / reconcile 命令，不自动生效。

## 为什么

- 单一真源能降低 P3 daily-use 的实现和排障成本。
- DB 更适合承载 stable id、scope、principal、visibility、provenance、metadata 和审计。
- Workspace 文件的核心价值是可读、可导出、可重建，而不是承载并发写入和授权裁决。
- 文件与 DB 双主会引入复杂 reconcile 语义；P3 当前更需要稳定使用，而不是双向同步系统。
- Projection 失败不影响 DB truth，能避免用户可读面的问题破坏记忆写入闭环。

## 放弃了什么

- 方案 A：长期保持 DB 与 Markdown 双写双主。
  - 放弃原因：冲突语义不闭合，且会让用户直接文件编辑绕过授权和审计。
- 方案 B：DB 写入失败时仍写 Markdown。
  - 放弃原因：会重新制造文件真源，破坏单一 truth。
- 方案 C：立即迁移所有历史 Markdown memory。
  - 放弃原因：P3 当前重点是 daily-use 新写入闭环；历史迁移会扩大范围。
- 方案 D：Markdown projection 失败时回滚 DB。
  - 放弃原因：projection 是可重建展示面，不应阻断真源写入。

## 影响

- `memory_append` 与后续 memory writer 必须以 DB 写入成功作为 truth 判定。
- Workspace memory 文件必须被文案和文件头标记为 auto-generated projection。
- 需要提供手动 projection rebuild 和 checksum / reconcile 工具。
- `memory_entries`、embedding、search index、workspace Markdown 都应视为可重建 projection，不应裁决 memory truth。
- ADR 0060 中的 dual-write prep 口径在 P3 中收敛为 DB truth + best-effort projection，而不是长期迁移状态。
