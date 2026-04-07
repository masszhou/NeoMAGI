---
doc_id: 019d6457-9290-7b7e-bfb4-6baac7f15f80
doc_id_format: uuidv7
doc_id_assigned_at: 2026-04-06T21:49:14+02:00
---
# skill_spec_versions

> Schema: `neomagi`  
> 返回总索引：[PostgreSQL Data Model Index](./index.md)

## 用途

`skill_spec_versions` 是 skill 的治理账本，记录 proposal、eval、apply、rollback、veto 等治理事件。它和 [`skill_specs`](./skill_specs.md) / [`skill_evidence`](./skill_evidence.md) 的 current-state 语义严格分离。

## 一行代表什么

一行代表一次针对某个 skill 的治理版本记录，而不是“当前 skill 状态”。

## 关键关系 / 不变量

- `skill_id` 刻意不是指向 [`skill_specs`](./skill_specs.md) 的 FK，因为 proposal 可以先于 current-state materialization 存在。
- `governance_version` 是账本主键，按时间递增。
- `rolled_back_from` 自引用到账本里的另一条版本记录。

## 列

| 列 | 类型 / 约束 | 含义 |
| --- | --- | --- |
| `governance_version` | `BIGINT` PK, autoincrement | 账本版本号。 |
| `skill_id` | `TEXT` NOT NULL | 被治理的 skill ID。 |
| `status` | `TEXT` NOT NULL, default `proposed` | 生命周期状态，例如 `proposed`、`active`、`superseded`、`rolled_back`、`vetoed`。 |
| `proposal` | `JSONB` NOT NULL | proposal 载荷，通常包含 `intent`、`risk_notes`、`diff_summary`、`payload` 等。 |
| `eval_result` | `JSONB` NULL | 评估结果与 checks。 |
| `created_by` | `TEXT` NOT NULL, default `agent` | proposal 创建者。 |
| `created_at` | `TIMESTAMPTZ` NOT NULL | proposal 创建时间。 |
| `applied_at` | `TIMESTAMPTZ` NULL | 该版本被 apply 的时间。 |
| `rolled_back_from` | `BIGINT` NULL, self FK | rollback 记录回指的历史版本。 |

## 当前写入语义

- proposal 先写一行 `status='proposed'`。
- eval 结果回填到 `eval_result`。
- apply 成功后把状态置为 `active`，并在需要时 materialize 到 [`skill_specs`](./skill_specs.md) / [`skill_evidence`](./skill_evidence.md)。
- rollback 会新增一条新的 rollback ledger 记录，而不是只覆写旧行。

## 当前 schema 来源

- 初始表：[create_skill_tables](../../../alembic/versions/a8b9c0d1e2f3_create_skill_tables.py)
- fresh DB 兜底 DDL：[src/session/database.py](../../../src/session/database.py)
- 生命周期定义：[src/growth/types.py](../../../src/growth/types.py)
- 运行时 adapter：[src/growth/adapters/skill.py](../../../src/growth/adapters/skill.py)
- 运行时 store：[src/skills/store.py](../../../src/skills/store.py)
