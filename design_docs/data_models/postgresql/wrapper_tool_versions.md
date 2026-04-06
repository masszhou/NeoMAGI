# wrapper_tool_versions

> Schema: `neomagi`  
> 返回总索引：[PostgreSQL Data Model Index](./index.md)

## 用途

`wrapper_tool_versions` 是 wrapper tool 的治理账本，记录 proposal、eval、apply、rollback、veto 等治理过程。

## 一行代表什么

一行代表一次针对某个 wrapper tool 的治理版本记录，而不是当前 current-state 本身。

## 关键关系 / 不变量

- `wrapper_tool_id` 刻意不是指向 [`wrapper_tools`](./wrapper_tools.md) 的 FK，因为 proposal 可以先于 materialization 存在。
- `rolled_back_from` 自引用到账本里的另一条记录。
- 存在单活约束：同一 `wrapper_tool_id` 最多只能有一条 `status='active'` 的记录。

## 列

| 列 | 类型 / 约束 | 含义 |
| --- | --- | --- |
| `governance_version` | `BIGINT` PK, autoincrement | 账本版本号。 |
| `wrapper_tool_id` | `TEXT` NOT NULL | 被治理的 wrapper tool ID。 |
| `status` | `TEXT` NOT NULL, default `proposed` | 生命周期状态，例如 `proposed`、`active`、`superseded`、`rolled_back`、`vetoed`。 |
| `proposal` | `JSONB` NOT NULL | proposal 载荷，通常包含 `wrapper_tool_spec` 与证据。 |
| `eval_result` | `JSONB` NULL | 评估结果与 checks。 |
| `created_by` | `TEXT` NOT NULL, default `agent` | proposal 创建者。 |
| `created_at` | `TIMESTAMPTZ` NOT NULL | proposal 创建时间。 |
| `applied_at` | `TIMESTAMPTZ` NULL | 该版本被 apply 的时间。 |
| `rolled_back_from` | `BIGINT` NULL, self FK | rollback 记录回指的历史版本。 |

## 当前写入语义

- proposal 先写为 `status='proposed'`。
- eval 结果回填到 `eval_result`。
- apply 成功后状态转为 `active`，并 materialize 到 [`wrapper_tools`](./wrapper_tools.md)。
- P2-M1c 不支持同 ID 的 in-place upgrade；如果已有 active 版本，通常先 rollback/disable 再重新走一轮 proposal。

## 当前 schema 来源

- 初始表：[create_wrapper_tool_tables](../../../alembic/versions/b9c0d1e2f3a4_create_wrapper_tool_tables.py)
- 生命周期定义：[src/growth/types.py](../../../src/growth/types.py)
- 运行时 adapter：[src/growth/adapters/wrapper_tool.py](../../../src/growth/adapters/wrapper_tool.py)
- 运行时 store：[src/wrappers/store.py](../../../src/wrappers/store.py)
