# memory_entries

> Schema: `neomagi`  
> 返回总索引：[PostgreSQL Data Model Index](./index.md)

## 用途

`memory_entries` 是 workspace memory 文件的检索投影表，用于全文搜索和 scope-aware retrieval。它不是最终真源；真源仍是 workspace 中的 memory 文件。

## 一行代表什么

一行代表一个可检索的 memory 片段，而不是一整个文件。  
例如一个 daily note 里的单个条目，或一个 curated memory 文件中的单个 section，都可能对应一行。

## 关键关系 / 不变量

- 本表没有强制 FK 到其他业务表；它是 retrieval plane，而不是业务真源。
- `search_vector` 是派生列，由触发器维护。
- `entry_id` 与 `source_session_id` 是 provenance 字段，用来追踪投影条目的稳定身份与来源会话。

## 列

| 列 | 类型 / 约束 | 含义 |
| --- | --- | --- |
| `id` | `INTEGER` PK, autoincrement | 数据库内部主键。 |
| `entry_id` | `VARCHAR(36)` NULL | memory 条目的稳定对象 ID。 |
| `scope_key` | `VARCHAR(128)` NOT NULL, default `main` | 检索 scope。 |
| `source_type` | `VARCHAR(16)` NOT NULL | 来源类型，例如 `daily_note`、`curated`、`flush_candidate`。 |
| `source_path` | `VARCHAR(256)` NULL | 来源文件路径。 |
| `source_date` | `DATE` NULL | 来源日期，常用于 daily note。 |
| `source_session_id` | `VARCHAR(256)` NULL | 产生该条 memory 的来源会话 ID。 |
| `title` | `TEXT` NOT NULL | 检索标题。 |
| `content` | `TEXT` NOT NULL | 检索正文。 |
| `tags` | `TEXT[]` | 标签数组。 |
| `confidence` | `FLOAT` NULL | 置信度或质量分。 |
| `search_vector` | `TSVECTOR` NULL | 供全文搜索使用的派生索引字段。 |
| `created_at` | `TIMESTAMPTZ` NOT NULL | 行创建时间。 |
| `updated_at` | `TIMESTAMPTZ` NOT NULL | 行更新时间。 |

## 当前写入语义

- reindex 时通常按“删除旧投影 -> 重新插入新投影”的方式重建。
- `source_path` 和 `entry_id` 一起帮助追踪“这条检索记录来自哪个文件/哪一段内容”。
- 搜索应依赖 `search_vector` 与 GIN 索引，而不是直接扫 `content`。

## 额外说明

- `entry_id` / `source_session_id` 目前由 `ensure_schema()` 做幂等补列；它们已经进入运行时模型，但不是最初创建表时的列。
- 因为本表是检索投影，所以恢复与一致性修复优先采用 reindex，而不是把本表当作不可重建真源。

## 当前 schema 来源

- 初始表：[create_memory_entries](../../../alembic/versions/d5e6f7a8b9c0_create_memory_entries.py)
- 运行时模型：[src/memory/models.py](../../../src/memory/models.py)
- provenance 补列与触发器兜底：[src/session/database.py](../../../src/session/database.py)
