# skill_specs

> Schema: `neomagi`  
> 返回总索引：[PostgreSQL Data Model Index](./index.md)

## 用途

`skill_specs` 保存当前已 materialize 的 skill 规格，是 skill runtime 的 current-state 表，而不是治理账本。

## 一行代表什么

一行代表一个当前可被 runtime 消费的 skill 定义。

## 关键关系 / 不变量

- [`skill_evidence`](./skill_evidence.md) 以 `skill_id` 1:1 关联到本表。
- [`skill_spec_versions`](./skill_spec_versions.md) 保存治理历史；本表只保存“当前态”。
- `disabled=true` 表示软禁用，不代表历史被删除。

## 列

| 列 | 类型 / 约束 | 含义 |
| --- | --- | --- |
| `id` | `TEXT` PK | skill ID。 |
| `capability` | `TEXT` NOT NULL | skill 所属能力类别。 |
| `version` | `INTEGER` NOT NULL, default `1` | 当前 materialized 版本号。 |
| `summary` | `TEXT` NOT NULL | skill 摘要。 |
| `activation` | `TEXT` NOT NULL | 触发/适用说明。 |
| `activation_tags` | `JSONB` NOT NULL | 触发标签数组。 |
| `preconditions` | `JSONB` NOT NULL | 前置条件数组。 |
| `delta` | `JSONB` NOT NULL | skill 对运行时行为的增量描述。 |
| `tool_preferences` | `JSONB` NOT NULL | 偏好的工具集合或顺序。 |
| `escalation_rules` | `JSONB` NOT NULL | 升级/转人工/转其他策略的规则。 |
| `exchange_policy` | `TEXT` NOT NULL, default `local_only` | skill 的共享/推广范围声明。 |
| `disabled` | `BOOLEAN` NOT NULL, default `false` | 是否被软禁用。 |
| `created_at` | `TIMESTAMPTZ` NOT NULL | 首次 materialize 时间。 |
| `updated_at` | `TIMESTAMPTZ` NOT NULL | 最近更新时间。 |

## 当前写入语义

- apply 成功后会把 proposal payload materialize 到本表。
- 相同 `id` 再次 apply 时通常走 upsert，而不是新建多行历史。
- 生命周期状态不放在本表，避免 current-state 与 governance ledger 混写。

## 当前 schema 来源

- 初始表：[create_skill_tables](../../../alembic/versions/a8b9c0d1e2f3_create_skill_tables.py)
- fresh DB 兜底 DDL：[src/session/database.py](../../../src/session/database.py)
- 运行时类型：[src/skills/types.py](../../../src/skills/types.py)
- 运行时 store：[src/skills/store.py](../../../src/skills/store.py)
