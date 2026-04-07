---
doc_id: 019d6457-9290-75e5-b2b1-6cf5a63c86c0
doc_id_format: uuidv7
doc_id_assigned_at: 2026-04-06T21:49:14+02:00
---
# PostgreSQL Data Model Index

> 作用：为应用自有 PostgreSQL 表提供稳定阅读入口。每张表单独一页，说明表用途、一行代表什么、列含义，以及与其他表/文档的关系。  
> 范围：当前只覆盖 `neomagi` schema 下由 NeoMAGI 运行时直接拥有的表；不覆盖 `alembic_version`、PostgreSQL 系统表、`.devcoord` SQLite 控制面或 `bd`/Dolt 数据。

## 1. 阅读建议

- 看对话持久化：[`sessions`](./sessions.md) -> [`messages`](./messages.md)
- 看 memory 检索面：[`memory_entries`](./memory_entries.md)
- 看 SOUL 治理：[`soul_versions`](./soul_versions.md)
- 看预算治理：[`budget_state`](./budget_state.md) / [`budget_reservations`](./budget_reservations.md)
- 看 skill current-state 与治理账本：[`skill_specs`](./skill_specs.md) / [`skill_evidence`](./skill_evidence.md) / [`skill_spec_versions`](./skill_spec_versions.md)
- 看 wrapper tool current-state 与治理账本：[`wrapper_tools`](./wrapper_tools.md) / [`wrapper_tool_versions`](./wrapper_tool_versions.md)

## 2. 按功能分组

### Session & Conversation

| 表 | 用途 | 相关表 |
| --- | --- | --- |
| [`sessions`](./sessions.md) | 会话级真源；保存会话模式、顺序控制、压缩状态 | [`messages`](./messages.md) |
| [`messages`](./messages.md) | 会话内按 `seq` 排序的消息流水 | [`sessions`](./sessions.md) |

### Retrieval Plane

| 表 | 用途 | 相关表 |
| --- | --- | --- |
| [`memory_entries`](./memory_entries.md) | workspace memory 文件的检索投影；不是最终真源 | 无硬 FK；可选记录 `source_session_id` |

### Governance Ledger

| 表 | 用途 | 相关表 |
| --- | --- | --- |
| [`soul_versions`](./soul_versions.md) | `SOUL.md` 治理账本与版本历史 | `SOUL.md` 投影文件 |
| [`skill_spec_versions`](./skill_spec_versions.md) | skill proposal/eval/apply/rollback 账本 | [`skill_specs`](./skill_specs.md), [`skill_evidence`](./skill_evidence.md) |
| [`wrapper_tool_versions`](./wrapper_tool_versions.md) | wrapper tool proposal/eval/apply/rollback 账本 | [`wrapper_tools`](./wrapper_tools.md) |

### Runtime Current-State

| 表 | 用途 | 相关表 |
| --- | --- | --- |
| [`skill_specs`](./skill_specs.md) | 当前 materialized skill 规格 | [`skill_evidence`](./skill_evidence.md), [`skill_spec_versions`](./skill_spec_versions.md) |
| [`skill_evidence`](./skill_evidence.md) | 当前 skill 的证据快照 | [`skill_specs`](./skill_specs.md), [`skill_spec_versions`](./skill_spec_versions.md) |
| [`wrapper_tools`](./wrapper_tools.md) | 当前 materialized wrapper tool 规格 | [`wrapper_tool_versions`](./wrapper_tool_versions.md) |

### Cost Governance

| 表 | 用途 | 相关表 |
| --- | --- | --- |
| [`budget_state`](./budget_state.md) | 全局累计预算状态 | [`budget_reservations`](./budget_reservations.md) |
| [`budget_reservations`](./budget_reservations.md) | 每次预算预占/结算流水 | [`budget_state`](./budget_state.md), [`sessions`](./sessions.md) |

## 3. 当前表清单（按表名）

| 表名 | 分类 | 一句话摘要 |
| --- | --- | --- |
| [`budget_reservations`](./budget_reservations.md) | Cost Governance | 每次通过预算闸门的预占与后续结算流水 |
| [`budget_state`](./budget_state.md) | Cost Governance | 全局预算累计器，当前设计上预期只有 `global` 一行 |
| [`memory_entries`](./memory_entries.md) | Retrieval Plane | workspace memory 的检索投影，一行代表一个可搜索片段 |
| [`messages`](./messages.md) | Session & Conversation | 会话内单条消息或工具调用消息 |
| [`sessions`](./sessions.md) | Session & Conversation | 会话级顶层状态与顺序控制 |
| [`skill_evidence`](./skill_evidence.md) | Runtime Current-State | 每个 skill 当前证据快照 |
| [`skill_specs`](./skill_specs.md) | Runtime Current-State | 每个 skill 当前 materialized 规格 |
| [`skill_spec_versions`](./skill_spec_versions.md) | Governance Ledger | skill 的治理账本，不等同于 current-state |
| [`soul_versions`](./soul_versions.md) | Governance Ledger | SOUL 内容的治理账本与版本历史 |
| [`wrapper_tool_versions`](./wrapper_tool_versions.md) | Governance Ledger | wrapper tool 的治理账本 |
| [`wrapper_tools`](./wrapper_tools.md) | Runtime Current-State | 当前 materialized wrapper tool 规格 |

## 4. 维护规则

- schema 改动时，优先同步更新对应逐表文档，再视需要更新本总索引。
- 若新增表，先决定其属于 current-state、governance ledger、retrieval plane 还是其他分类，再补入口。
- 若列语义发生变化，逐表文档中应同时更新：
  - `用途`
  - `一行代表什么`
  - `列`
  - `关键关系 / 不变量`
- 若代码实现与 migration 暂时不一致，应在逐表文档明确标注“当前 schema 来源”，避免把目标状态和已落库状态混写。
