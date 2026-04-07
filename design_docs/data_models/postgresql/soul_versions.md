---
doc_id: 019d6457-9290-7afc-86c3-8061ba9c3f94
doc_id_format: uuidv7
doc_id_assigned_at: 2026-04-06T21:49:14+02:00
---
# soul_versions

> Schema: `neomagi`  
> 返回总索引：[PostgreSQL Data Model Index](./index.md)

## 用途

`soul_versions` 保存 `SOUL.md` 的治理账本与版本历史。当前设计里，数据库中的这张表才是 SOUL 的 SSOT，workspace 根目录的 `SOUL.md` 是其运行时投影。

## 一行代表什么

一行代表一次 SOUL 内容快照或治理事件：可能是 proposal、active 版本，也可能是 rollback/veto 后留下的审计记录。

## 关键关系 / 不变量

- `version` 是业务版本号，必须唯一。
- `status` 走治理生命周期，例如 `proposed`、`active`、`superseded`、`rolled_back`、`vetoed`。
- `proposal` 与 `eval_result` 保存 proposal/eval 产物，支撑审计和回溯。

## 列

| 列 | 类型 / 约束 | 含义 |
| --- | --- | --- |
| `id` | `INTEGER` PK, autoincrement | 数据库内部主键。 |
| `version` | `INTEGER` UNIQUE NOT NULL | SOUL 的业务版本号。 |
| `content` | `TEXT` NOT NULL | 该版本的完整 SOUL 文本。 |
| `status` | `VARCHAR(16)` NOT NULL | 当前治理状态。 |
| `proposal` | `JSONB` NULL | proposal 载荷与元数据。 |
| `eval_result` | `JSONB` NULL | eval 结果与检查明细。 |
| `created_by` | `VARCHAR(32)` NOT NULL | 创建来源，例如 `agent`、`bootstrap`、`system`。 |
| `created_at` | `TIMESTAMPTZ` NOT NULL | 创建时间。 |

## 当前写入语义

- 新 proposal 会先进入 `proposed`。
- apply 通过后会出现 `active` 版本；历史版本可能被标记为 `superseded` 或 `rolled_back`。
- 该表用于审计和回放，不等同于“当前 SOUL 只保留一行”的 current-state 表。

## 当前 schema 来源

- 初始表：[create_soul_versions](../../../alembic/versions/e6f7a8b9c0d1_create_soul_versions.py)
- 运行时模型：[src/memory/models.py](../../../src/memory/models.py)
- SSOT 决议：[0036-evolution-consistency-db-as-ssot-and-soulmd-as-projection](../../../decisions/0036-evolution-consistency-db-as-ssot-and-soulmd-as-projection.md)
