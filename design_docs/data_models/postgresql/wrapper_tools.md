---
doc_id: 019d6457-9290-711f-9ce3-d24140133ecb
doc_id_format: uuidv7
doc_id_assigned_at: 2026-04-06T21:49:14+02:00
---
# wrapper_tools

> Schema: `neomagi`  
> 返回总索引：[PostgreSQL Data Model Index](./index.md)

## 用途

`wrapper_tools` 保存当前已 materialize 的 wrapper tool 规格，是 wrapper runtime 的 current-state 表。

## 一行代表什么

一行代表一个当前可加载到 ToolRegistry 中的 wrapper tool 定义。

## 关键关系 / 不变量

- [`wrapper_tool_versions`](./wrapper_tool_versions.md) 负责治理历史；本表只保存当前态。
- `disabled=true` 表示从 current-state 角度移除或软禁用。
- `implementation_ref` 使用 `<module>:<factory>` 形式指向 Python 实现入口。

## 列

| 列 | 类型 / 约束 | 含义 |
| --- | --- | --- |
| `id` | `TEXT` PK | wrapper tool ID。 |
| `capability` | `TEXT` NOT NULL | 所属能力类别。 |
| `version` | `INTEGER` NOT NULL, default `1` | 当前 materialized 版本号。 |
| `summary` | `TEXT` NOT NULL | 工具摘要。 |
| `input_schema` | `JSONB` NOT NULL | 输入 JSON Schema。 |
| `output_schema` | `JSONB` NOT NULL | 输出 JSON Schema。 |
| `bound_atomic_tools` | `JSONB` NOT NULL | 绑定的原子工具 ID 数组。 |
| `implementation_ref` | `TEXT` NOT NULL | Python 实现引用，格式为 `<module>:<factory>`。 |
| `deny_semantics` | `JSONB` NOT NULL | 显式拒绝/禁止的语义列表。 |
| `scope_claim` | `TEXT` NOT NULL, default `local` | 作用域声明，例如 `local`、`reusable`、`promotable`。 |
| `disabled` | `BOOLEAN` NOT NULL, default `false` | 是否被软禁用。 |
| `created_at` | `TIMESTAMPTZ` NOT NULL | 首次 materialize 时间。 |
| `updated_at` | `TIMESTAMPTZ` NOT NULL | 最近更新时间。 |

## 当前写入语义

- apply 成功后会 materialize 到本表，并尝试注册到 ToolRegistry。
- 相同 `id` 再 materialize 时通常走 upsert。
- 本表不保存治理状态；治理状态看 [`wrapper_tool_versions`](./wrapper_tool_versions.md)。

## 当前 schema 来源

- 初始表：[create_wrapper_tool_tables](../../../alembic/versions/b9c0d1e2f3a4_create_wrapper_tool_tables.py)
- 运行时类型：[src/wrappers/types.py](../../../src/wrappers/types.py)
- 运行时 store：[src/wrappers/store.py](../../../src/wrappers/store.py)
