# budget_reservations

> Schema: `neomagi`  
> 返回总索引：[PostgreSQL Data Model Index](./index.md)

## 用途

`budget_reservations` 记录每次通过预算闸门后的预占与结算流水，用于成本追踪、审计和幂等 settle。

## 一行代表什么

一行代表一次成功的预算预占记录；之后它可能从 `reserved` 变为 `settled`。

## 关键关系 / 不变量

- 和 [`budget_state`](./budget_state.md) 语义配套：前者是累计器，后者是流水。
- `status='reserved'` 的行会被部分索引覆盖，便于快速定位待结算预占。
- `session_id` 与 `eval_run_id` 是软关联字段，用来回溯这笔预算来自哪次会话或评测，而不是 FK。

## 列

| 列 | 类型 / 约束 | 含义 |
| --- | --- | --- |
| `reservation_id` | `UUID` PK, default `gen_random_uuid()` | 预算预占 ID。 |
| `provider` | `TEXT` NOT NULL | 模型提供商。 |
| `model` | `TEXT` NOT NULL | 模型名。 |
| `session_id` | `TEXT` NOT NULL, default `''` | 来源会话 ID；可为空字符串。 |
| `eval_run_id` | `TEXT` NOT NULL, default `''` | 来源 eval run ID；可为空字符串。 |
| `reserved_eur` | `NUMERIC(10,4)` NOT NULL | 预估时先保留的金额。 |
| `actual_eur` | `NUMERIC(10,4)` NULL | 实际成本；结算后写入。 |
| `status` | `TEXT` NOT NULL, default `reserved` | 当前状态，当前运行时主要使用 `reserved` / `settled`。 |
| `created_at` | `TIMESTAMPTZ` NOT NULL | 预占创建时间。 |
| `settled_at` | `TIMESTAMPTZ` NULL | 实际结算时间。 |

## 当前写入语义

- try-reserve 成功后插入一行 `status='reserved'`。
- settle 以 CAS 方式把 `reserved` 翻转为 `settled`；重复 settle 是幂等 no-op。
- denied 请求不会插入行，因此本表只记录“实际预占过预算”的调用。

## 当前 schema 来源

- 初始表：[add_budget_tables](../../../alembic/versions/f7a8b9c0d1e2_add_budget_tables.py)
- 运行时逻辑：[src/gateway/budget_gate.py](../../../src/gateway/budget_gate.py)
