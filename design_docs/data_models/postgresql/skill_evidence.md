---
doc_id: 019d6457-9290-79a5-87c4-749b17daa18c
doc_id_format: uuidv7
doc_id_assigned_at: 2026-04-06T21:49:14+02:00
---
# skill_evidence

> Schema: `neomagi`  
> 返回总索引：[PostgreSQL Data Model Index](./index.md)

## 用途

`skill_evidence` 保存每个 skill 当前证据快照，供 resolver、projector 和 learner 在运行时消费。

## 一行代表什么

一行代表一个 skill 当前的证据状态；它与 [`skill_specs`](./skill_specs.md) 是 1:1 关系。

## 关键关系 / 不变量

- `skill_id` 既是主键也是 FK，保证每个 skill 最多只有一行当前证据。
- 本表是 current-state，不保存完整历史；历史变化要回到 [`skill_spec_versions`](./skill_spec_versions.md) 的 proposal/eval 产物里看。
- 负面证据的来源有额外纪律约束，不能随意来自非确定性来源。

## 列

| 列 | 类型 / 约束 | 含义 |
| --- | --- | --- |
| `skill_id` | `TEXT` PK, FK -> `skill_specs.id` | 对应的 skill ID。 |
| `source` | `TEXT` NOT NULL | 当前证据来源，例如 `deterministic`、`test`、`eval`、`manual`。 |
| `success_count` | `INTEGER` NOT NULL, default `0` | 成功样本计数。 |
| `failure_count` | `INTEGER` NOT NULL, default `0` | 失败样本计数。 |
| `last_validated_at` | `TIMESTAMPTZ` NULL | 最近验证时间。 |
| `positive_patterns` | `JSONB` NOT NULL | 正向模式数组。 |
| `negative_patterns` | `JSONB` NOT NULL | 负向模式数组。 |
| `known_breakages` | `JSONB` NOT NULL | 已知失效场景数组。 |
| `created_at` | `TIMESTAMPTZ` NOT NULL | 首次写入时间。 |
| `updated_at` | `TIMESTAMPTZ` NOT NULL | 最近更新时间。 |

## 当前写入语义

- 常与 [`skill_specs`](./skill_specs.md) 一起被 upsert，形成“当前态 skill + 当前态 evidence”。
- `success_count` / `failure_count` 是当前快照，不是不可变账本。
- 对 `negative_patterns` 的写入应满足 deterministic provenance 约束。

## 当前 schema 来源

- 初始表：[create_skill_tables](../../../alembic/versions/a8b9c0d1e2f3_create_skill_tables.py)
- fresh DB 兜底 DDL：[src/session/database.py](../../../src/session/database.py)
- 运行时类型：[src/skills/types.py](../../../src/skills/types.py)
- 运行时 store：[src/skills/store.py](../../../src/skills/store.py)
