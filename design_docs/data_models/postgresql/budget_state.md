# budget_state

> Schema: `neomagi`  
> 返回总索引：[PostgreSQL Data Model Index](./index.md)

## 用途

`budget_state` 保存全局预算累计状态，供 BudgetGate 在请求进入前做原子预算检查。

## 一行代表什么

当前设计中，一行代表一个预算累计器；现阶段预期只有 `id='global'` 这一行。

## 关键关系 / 不变量

- `budget_reservations` 记录每次预占/结算流水；`budget_state` 保存累计结果。
- migration 会自动 seed `global` 行。
- BudgetGate 通过原子更新 `cumulative_eur` 来做 stop/warn 阈值判断。

## 列

| 列 | 类型 / 约束 | 含义 |
| --- | --- | --- |
| `id` | `TEXT` PK, default `global` | 预算累计器 ID；当前固定使用 `global`。 |
| `cumulative_eur` | `NUMERIC(10,4)` NOT NULL, default `0` | 当前全局累计成本。 |
| `updated_at` | `TIMESTAMPTZ` NOT NULL | 最近更新时间。 |

## 当前写入语义

- try-reserve 成功时，先原子增加 `cumulative_eur`，再写 [`budget_reservations`](./budget_reservations.md)。
- settle 时会根据 `actual_eur - reserved_eur` 再修正 `cumulative_eur`。
-  denied 请求不会新增 reservation 行，但仍会读取这里的累计值生成拒绝消息。

## 当前 schema 来源

- 初始表：[add_budget_tables](../../../alembic/versions/f7a8b9c0d1e2_add_budget_tables.py)
- 运行时逻辑：[src/gateway/budget_gate.py](../../../src/gateway/budget_gate.py)
