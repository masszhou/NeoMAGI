---
doc_id: 019cbffe-c1f0-722b-ba32-01170d08f372
doc_id_format: uuidv7
doc_id_assigned_at: 2026-03-05T22:54:30+01:00
---
# 记忆架构 v2（原则版）

> 状态：current  
> 日期：2026-03-04  
> 用途：作为 memory 设计的长期原则文档，替代早期偏 `P1-M2` / `P1-M3` 规划口径的 `design_docs/phase1/memory_architecture.md`
> 修订：ADR 0060 已将机器写入 memory truth 从 workspace Markdown 调整为 DB append-only source ledger；workspace 文件保留为 projection / export surface。

## 1. 核心判断
- 机器写入 memory 的真源是 PostgreSQL 中的 append-only source ledger。
- workspace memory files 是人类可读、可导出、可重建的 projection / export surface。
- PostgreSQL 的 source ledger 只承担极薄事实账本，不等同于 retrieval 表、向量索引、graph projection 或完整 memory ontology。
- 平台只提供稳定原子操作；更高层的记忆组织方式允许 agent 按用户场景演化。
- 人类定义 `memory kernel`。
- agent 在 `memory kernel` 之上组合、声明、演化 `memory applications`。
- DB ledger 持有机器写入的原始材料、provenance、scope、visibility 与最小治理元数据。
- workspace 持有人类可读 projection、export 与部分 spec。
- retrieval 表、缓存、派生结构和查询加速层仍是可重建 projection。

核心句：

**Memory truth lives in an append-only user-owned PostgreSQL ledger. Workspace files are readable projections and exports. Retrieval and memory applications remain rebuildable projections above stable primitives.**

## 2. 为什么 memory 真源迁移到 DB source ledger
- PostgreSQL 已是产品运行时 hard dependency，不再是额外依赖。
- append-only ledger 更适合承载 provenance、scope、identity、visibility、redaction、contested memory 与审计。
- direct file edits 容易绕过授权、审计和一致性检查；显式 import / reconcile 才应把文件改动带回 ledger。
- Shared Companion / consent-scoped memory 需要更强的来源、授权与修正语义，Markdown 元数据协议会快速累积兼容债。
- workspace projection 继续保留可读性、导出性和可迁移性，但不再裁决机器写入事实。

## 3. 为什么 DB ledger 不是完整 memory ontology
- 数据库可以承载极薄事实账本，但不能把当前检索 schema 提升为长期记忆本体。
- `memory_entries`、embedding、ranking、thread、graph edge、summary cluster 都是 projection，可从 source ledger 重建。
- memory 在本项目中不是先验定义好的固定数据模型，而是会随用户任务逐步分化。
- 如果过早把完整数据库 ontology 当作真源，就会把“当前实现的检索模型”误固化成“长期记忆模型”。

## 4. 平台层与进化层的分工

### 4.1 Memory Kernel（平台固定层）
- DB source ledger
  - append-only memory events / versions
  - provenance / scope / visibility / source metadata
- workspace memory projections
  - `workspace/memory/YYYY-MM-DD.md`
  - `workspace/MEMORY.md`
- memory specs
  - agent 可声明的 memory application spec/manifest
  - 这些 spec 可继续作为 workspace / governance artifact 管理，不把 retrieval DB schema 当真源
- scope-aware 原子操作
  - append
  - search
  - recall
  - reindex
  - archive / curation
- 基础检索模板
  - lexical / BM25
  - hybrid search 作为通用初始模板
- 安全与运维约束
  - scope filtering
  - backup / restore
  - doctor / reindex

### 4.2 Memory Applications（agent 演化层）
- agent 可基于 daily notes、长期互动和用户目标，逐步形成领域化记忆组织方式。
- 这些记忆应用不是平台预写死的一套统一 schema。
- agent 优先演化 memory application 的声明与组合方式，而不是无约束地直接改造 memory kernel。
- 例如：
  - 金融分析用户：watchlist、thesis ledger、earnings memory、source credibility memory
  - 自媒体作者：style memory、topic backlog、argument bank、audience feedback memory
  - 软件项目用户：decision memory、bug pattern memory、review checklist memory
  - Shared Companion：relationship memory、shared-space summary、consent-scoped visibility ledger
- relationship memory 只能作为 memory application 演化，不能把 shared-space schema 直接硬编码进 memory kernel；它必须继续复用 scope filtering、DB ledger truth 与可重建 retrieval / workspace projection。

## 5. 长期原则
- 不预设唯一的“标准 memory schema”适用于所有用户。
- 先提供最少必要原子操作，再允许 agent 在其上构建更适配用户的 memory applications。
- agent 不应每次从零开始；应优先学习已有公开经验、案例和模式，再做本地适配。
- hybrid search 适合作为通用任务的默认模板，但不是长期唯一形态。
- Shared Companion 这类多 principal 场景必须先有身份、membership 与 consent policy，再设计检索增强；不能用更强检索能力绕过共享边界。

## 6. 关键边界
- 平台不应把某一版数据库结构误当作 memory 的永久本体。
- agent 可以演化记忆应用层，但不应随意破坏 memory kernel 的稳定契约。
- DB source ledger 保存机器写入 memory 的事实账本；workspace 中保存的是人类可读 projection、export 以及部分 memory specs；retrieval 表保存索引、缓存、派生结构与查询加速层。
- `SOUL` 不属于此文档范畴：`SOUL` 是受治理对象，真源在 DB，`SOUL.md` 是 projection。
- `scope_key` 回答“谁可以检索到这条记忆”；未来若引入 `shared_space_id`，也必须先映射到明确的 visibility / membership policy，再进入 retrieval。
- 私有记忆与 shared-space memory 必须是硬边界；不能因为两个 principal 属于同一关系空间，就默认互相召回私聊记忆。

## 7. 对当前实现的含义
- `memory_entries` 继续视为检索数据面，而非真源。
- daily notes 与 `MEMORY.md` 继续作为 projection / export；在 `P2-M2d` 之前，旧写入路径仍可能表现为文件优先，但新设计不得把它们作为长期机器写入真源。
- `P2-M2d` 只做 source ledger schema、append-only writer、`memory_append` 双写与 parity / reconcile 检查，不切换 read path。
- `P2-M3` identity / visibility policy 稳定后，再将 reindex 来源切到 DB ledger current view。
- `doctor/preflight` 应显式区分：
  - memory truth: DB append-only source ledger
  - memory projection/export: workspace
  - memory retrieval plane: PostgreSQL projections / indexes

## 8. 非目标
- 不追求由人类预先设计一套覆盖所有用户场景的统一记忆体系。
- 不允许 agent 无约束地直接演化底层存储内核。
- 不把当前某种检索实现等同于长期记忆本体。
