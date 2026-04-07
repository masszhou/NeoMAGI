---
doc_id: 019d6457-9290-7ef8-95a9-1270d681b9eb
doc_id_format: uuidv7
doc_id_assigned_at: 2026-04-06T21:49:14+02:00
---
# sessions

> Schema: `neomagi`  
> 返回总索引：[PostgreSQL Data Model Index](./index.md)

## 用途

`sessions` 保存一段对话会话的顶层状态，是 [`messages`](./messages.md) 的父表，也是会话级顺序控制、租约锁和压缩状态的落点。

## 一行代表什么

一行代表一个 `session_id` 对应的整段会话，而不是单条消息。

## 关键关系 / 不变量

- [`messages`](./messages.md) 通过 `session_id -> sessions.id` 关联到父会话。
- `next_seq`、`lock_token`、`processing_since` 一起支撑多 worker 下的顺序写入与会话租约锁。
- `compacted_context` 等字段保存压缩后的上下文摘要，但不替代原始消息流水。

## 列

| 列 | 类型 / 约束 | 含义 |
| --- | --- | --- |
| `id` | `VARCHAR(128)` PK | 会话 ID。 |
| `created_at` | `TIMESTAMPTZ` NOT NULL | 会话创建时间。 |
| `updated_at` | `TIMESTAMPTZ` NOT NULL | 会话最近更新时间。 |
| `mode` | `VARCHAR(16)` NOT NULL, default `chat_safe` | 会话当前模式。 |
| `next_seq` | `INTEGER` NOT NULL, default `0` | 下一条消息应分配的顺序号。 |
| `lock_token` | `VARCHAR(36)` NULL | 当前持有会话处理租约的一方标识。 |
| `processing_since` | `TIMESTAMPTZ` NULL | 当前租约开始时间。 |
| `compacted_context` | `TEXT` NULL | 压缩后的上下文摘要文本。 |
| `compaction_metadata` | `JSONB` NULL | 压缩元数据，例如压缩范围、策略或统计信息。 |
| `last_compaction_seq` | `INTEGER` NULL | 最近一次压缩覆盖到的消息序号。 |
| `memory_flush_candidates` | `JSONB` NULL | 候选 memory flush 项列表。 |

## 当前写入语义

- 会话初始化时先写父行，再追加 [`messages`](./messages.md)。
- `updated_at` 主要反映会话级状态变化，而不是单靠读取行为变化。
- `memory_flush_candidates` 是会话态候选集，不是长期 memory 真源。

## 当前 schema 来源

- 初始表：[create_sessions_and_messages_tables](../../../alembic/versions/f2d8d48c9ef1_create_sessions_and_messages_tables.py)
- 顺序控制补列：[add_session_seq_lock_and_message_unique](../../../alembic/versions/a1b2c3d4e5f6_add_session_seq_lock_and_message_unique.py)
- mode 补列：[add_mode_column_to_sessions](../../../alembic/versions/b3c4d5e6f7a8_add_mode_column_to_sessions.py)
- compaction 补列：[add_compaction_fields_to_sessions](../../../alembic/versions/c4d5e6f7a8b9_add_compaction_fields_to_sessions.py)
- 运行时模型：[src/session/models.py](../../../src/session/models.py)
