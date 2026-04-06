# messages

> Schema: `neomagi`  
> 返回总索引：[PostgreSQL Data Model Index](./index.md)

## 用途

`messages` 保存会话内按顺序展开的消息流水，包括普通用户/assistant 消息，以及带工具调用元数据的消息。

## 一行代表什么

一行代表会话中的一条消息事件，按同一 `session_id` 下的 `seq` 排序。

## 关键关系 / 不变量

- `session_id` FK 指向 [`sessions`](./sessions.md)。
- 同一会话内 `(session_id, seq)` 必须唯一，这是消息顺序的硬约束。
- `id` 是数据库自增主键；业务顺序以 `seq` 为准，不以 `id` 为准。

## 列

| 列 | 类型 / 约束 | 含义 |
| --- | --- | --- |
| `id` | `INTEGER` PK, autoincrement | 数据库内部主键。 |
| `session_id` | `VARCHAR(128)` FK -> `sessions.id` | 所属会话。 |
| `seq` | `INTEGER`, unique within `session_id` | 会话内顺序号。 |
| `role` | `VARCHAR(16)` NOT NULL | 消息角色，例如 `user`、`assistant`、`tool`。 |
| `content` | `TEXT` NOT NULL | 消息正文。 |
| `tool_calls` | `JSONB` NULL | assistant 发起的工具调用载荷快照。 |
| `tool_call_id` | `VARCHAR(64)` NULL | 与某次工具调用关联的调用 ID。 |
| `created_at` | `TIMESTAMPTZ` NOT NULL | 消息写入时间。 |

## 当前写入语义

- 一般按 `sessions.next_seq` 分配 `seq` 后写入。
- `tool_calls` 与 `tool_call_id` 允许把对话消息和工具调用链路串起来。
- 如果做上下文压缩，原始消息仍保留在本表中；压缩结果落在 [`sessions`](./sessions.md)。

## 当前 schema 来源

- 初始表：[create_sessions_and_messages_tables](../../../alembic/versions/f2d8d48c9ef1_create_sessions_and_messages_tables.py)
- 唯一约束补充：[add_session_seq_lock_and_message_unique](../../../alembic/versions/a1b2c3d4e5f6_add_session_seq_lock_and_message_unique.py)
- 运行时模型：[src/session/models.py](../../../src/session/models.py)
