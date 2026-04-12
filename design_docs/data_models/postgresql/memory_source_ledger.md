---
doc_id: 019d80e4-9f30-7484-be9e-9927ed51d93c
doc_id_format: uuidv7
doc_id_assigned_at: 2026-04-12T10:52:39+02:00
---
# memory_source_ledger

> Schema: `neomagi`
> 返回总索引：[PostgreSQL Data Model Index](./index.md)

## 用途

`memory_source_ledger` 是 NeoMAGI 的 append-only memory truth 表（ADR 0060, P2-M2d）。每次 memory 写入在此追加一条事件记录；workspace 中的 `memory/*.md` daily notes 和 `memory_entries` 表都是从本表衍生的 projection。

## 一行代表什么

一行代表一次 memory 事件。V1 只有 `append` 事件（新增 memory 条目）；后续版本将扩展 `correction`、`retraction`、`contested`、`hard_erase` 等事件类型，允许对同一 `entry_id` 追加多条事件记录。

## 关键关系 / 不变量

- `event_id`（UUIDv7）是每行的唯一标识，`entry_id`（UUIDv7）标识被操作的 memory 条目。
- Partial unique index `uq_memory_source_ledger_entry_append` 确保同一 `entry_id` 只有一条 `append` 事件（幂等防护），不阻塞未来 correction/retraction 事件。
- 本表不设外键到 `memory_entries`（两者是独立层：truth vs retrieval projection）。
- Backup 时纳入 `TRUTH_TABLES`（`scripts/backup.py`），`memory_entries` 则不纳入（可 reindex 重建）。

## 列

| 列 | 类型 / 约束 | 含义 |
| --- | --- | --- |
| `event_id` | `VARCHAR(36)` PK | 事件 identity，UUIDv7，每行独立。 |
| `entry_id` | `VARCHAR(36)` NOT NULL | 被操作的 memory 条目 identity，UUIDv7。 |
| `event_type` | `VARCHAR(16)` NOT NULL, default `append` | 事件类型。V1 只有 `append`。 |
| `scope_key` | `VARCHAR(128)` NOT NULL, default `main` | 检索可见性 scope（ADR 0034）。 |
| `source` | `VARCHAR(32)` NOT NULL | 写入来源：`user` 或 `compaction_flush`。 |
| `source_session_id` | `VARCHAR(256)` NULL | 来源 session provenance。 |
| `content` | `TEXT` NOT NULL | 原文正文。 |
| `metadata` | `JSONB` NOT NULL, default `{}` | 扩展元数据预留（V1 不使用）。 |
| `created_at` | `TIMESTAMPTZ` NOT NULL, default `now()` | 写入时间。 |

## 索引

| 索引名 | 列 | 类型 | 说明 |
| --- | --- | --- | --- |
| PK | `event_id` | btree | 主键 |
| `idx_memory_source_ledger_entry_id` | `entry_id` | btree | 按 entry 查询 |
| `idx_memory_source_ledger_scope` | `scope_key` | btree | scope 过滤 |
| `idx_memory_source_ledger_created_at` | `created_at` | btree | 时间范围扫描 |
| `uq_memory_source_ledger_entry_append` | `entry_id` WHERE `event_type = 'append'` | partial unique | 同一 entry 只允许一条 append |

## 当前写入语义

- `MemoryLedgerWriter.append()` 使用 `INSERT ... ON CONFLICT DO NOTHING` + `RETURNING event_id` 实现幂等。
- 写入顺序（P2-M2d truth-first）：先写本表，再写 workspace daily note projection。
- Ledger 写入失败 → 整体失败；projection 写入失败 → warning（truth 已持久化）。

## 当前 schema 来源

- Migration：[create_memory_source_ledger](../../../alembic/versions/e2f3a4b5c6d7_create_memory_source_ledger.py)
- Fresh-DB DDL：[src/session/database.py](../../../src/session/database.py) `_create_memory_source_ledger_table()`
- Writer API：[src/memory/ledger.py](../../../src/memory/ledger.py)
