# Glossary

> 目的：为 NeoMAGI 提供轻量级、可持续维护的 Domain Ontology。  
> 口径优先级：`decisions/` > `design_docs/` > `dev_docs/`。  
> 范围：只收录跨文档反复出现、且容易混淆的核心术语；不追求枚举所有代码符号。

## 使用原则

- 术语冲突时，先以已接受 ADR 为准。
- 同一概念尽量只保留一个主词；历史别名只作为 `Aliases` 保留。
- 本文件解释“概念是什么”，不替代具体实现文档、计划或测试用例。

### SOUL
- **Category**：Identity / Governance Object
- **Aliases**：`soul`
- **Definition**：NeoMAGI 的受治理“自我/原则/价值观”对象。它回答“agent 是谁、按什么原则代表用户”，而不是“具体任务怎么做”。
- **Relations**：
  - `projected-as` → [SOUL.md](#soulmd)
  - `aligned-with` → [Principal](#principal)
  - `is-a` → [Growth Object](#growth-object)
  - `evaluated-by` → [GrowthEvalContract](#growthevalcontract)

### SOUL.md
- **Category**：Workspace Projection
- **Aliases**：`workspace/SOUL.md`
- **Definition**：当前 active `SOUL` 的运行时投影文件，不是最终真源。项目语义上以 DB 中 active soul version 为准，`SOUL.md` 负责工作区可见性和 prompt 注入。
- **Relations**：
  - `projection-of` → [SOUL](#soul)

### Principal
- **Category**：Identity / Runtime
- **Aliases**：user-interest line
- **Definition**：NeoMAGI 在运行时所代表的“同一个用户利益”身份轴。多 agent 默认共享同一个 `SOUL / principal`，而不是各自拥有独立长期人格。
- **Relations**：
  - `co-defined-by` → [SOUL](#soul)

### Growth Object
- **Category**：Governance
- **Aliases**：governed growth object
- **Definition**：被允许进入显式成长生命周期的第一等对象。只有 growth object 才能进入 `propose -> evaluate -> apply -> rollback` 路径；普通实现产物或代码 diff 不自动成为 growth object。
- **Relations**：
  - `typed-by` → [Growth Object Kind](#growth-object-kind)
  - `mutated-by` → [Growth Proposal](#growth-proposal)
  - `evaluated-by` → [GrowthEvalContract](#growthevalcontract)

### Growth Object Kind
- **Category**：Governance
- **Aliases**：`GrowthObjectKind`, growth kind
- **Definition**：growth governance kernel 识别的对象类型枚举。当前核心 kind 包括 `soul`、`skill_spec`、`wrapper_tool`、`procedure_spec`、`memory_application_spec`。
- **Relations**：
  - `includes` → [SOUL](#soul)
  - `includes` → [SkillSpec](#skillspec)
  - `includes` → [Wrapper Tool](#wrapper-tool)
  - `includes` → [ProcedureSpec](#procedurespec)
  - `includes` → [Memory Application Spec](#memory-application-spec)

### Growth Proposal
- **Category**：Governance
- **Aliases**：`GrowthProposal`, proposal
- **Definition**：对某个 growth object 的可审计变更提案。它记录 intent、risk notes、diff summary、evidence refs 和对象相关 payload，但不应包含它自己的 judge / harness 变更。
- **Relations**：
  - `targets` → [Growth Object](#growth-object)
  - `evaluated-under` → [GrowthEvalContract](#growthevalcontract)
  - `may-attach` → [Raw Code Patch](#raw-code-patch)

### GrowthEvalContract
- **Category**：Governance / Evaluation
- **Aliases**：eval contract
- **Definition**：针对某类 growth object 的一等治理对象。它必须是 `object-scoped`、`versioned`、`immutable`，并定义什么可变、什么 judge 资产固定、以及 pass / veto / rollback 如何判定。
- **Relations**：
  - `applies-to` → [Growth Object](#growth-object)
  - `contains` → [Boundary Gates](#boundary-gates)
  - `contains` → [Effect Evidence](#effect-evidence)
  - `contains` → [Scope Claim](#scope-claim)
  - `contains` → [Efficiency Metrics](#efficiency-metrics)

### Boundary Gates
- **Category**：Evaluation
- **Aliases**：hard gates
- **Definition**：评估契约中的硬门槛，优先判断边界是否安全、架构是否清晰、回滚是否成立、依赖是否显式。未通过时，不进入后续效果或效率比较。
- **Relations**：
  - `layer-of` → [GrowthEvalContract](#growthevalcontract)
  - `precedes` → [Effect Evidence](#effect-evidence)

### Effect Evidence
- **Category**：Evaluation
- **Aliases**：before/after evidence, ablation evidence
- **Definition**：证明“这个改动确实带来改善”的证据层。默认应至少有固定 before / after cases；当改动声称是更普适的改进时，可增加轻量 ablation。
- **Relations**：
  - `layer-of` → [GrowthEvalContract](#growthevalcontract)
  - `precedes` → [Scope Claim](#scope-claim)

### Scope Claim
- **Category**：Evaluation
- **Aliases**：applicability claim
- **Definition**：对改进适用范围的明确声明，例如 `local`、`reusable`、`promotable`。claim 越强，所需证据和回归要求越高。
- **Relations**：
  - `layer-of` → [GrowthEvalContract](#growthevalcontract)
  - `precedes` → [Efficiency Metrics](#efficiency-metrics)

### Efficiency Metrics
- **Category**：Evaluation
- **Aliases**：efficiency signals
- **Definition**：在质量已达标后，用于比较效率收益的指标层，例如 `tokens_per_success`、`latency_per_success`、`cost_per_success`。它不单独决定是否 apply。
- **Relations**：
  - `layer-of` → [GrowthEvalContract](#growthevalcontract)

### Atomic Tool
- **Category**：Capability Layer
- **Aliases**：typed tool, atomic capability
- **Definition**：稳定、typed、可审计的底层能力单元。它回答“系统最底层能做什么”，而不回答“某类任务通常怎么更稳”。
- **Relations**：
  - `underlies` → [Wrapper Tool](#wrapper-tool)
  - `preferred-by` → [SkillSpec](#skillspec)
  - `used-by` → [Procedure Runtime](#procedure-runtime)

### Skill Object
- **Category**：Capability Layer
- **Aliases**：skill
- **Definition**：结构化的运行时经验对象，用来承载“这类任务基于已有经验通常该怎么更稳”的可复用 delta。它不是 tool，不是 procedure，也不是人格。
- **Relations**：
  - `specified-by` → [SkillSpec](#skillspec)
  - `supports` → [Capability](#capability)
  - `may-promote-to` → [Wrapper Tool](#wrapper-tool)
  - `may-suggest-entry-to` → [ProcedureSpec](#procedurespec)

### SkillSpec
- **Category**：Capability Layer / Governance Object
- **Aliases**：`skill_spec`
- **Definition**：一个 skill object 的静态规格。它定义 summary、activation、activation tags、preconditions、delta、tool preferences 和 escalation rules，是 `P2-M1b` 计划接入的第二类正式 growth object。
- **Relations**：
  - `specifies` → [Skill Object](#skill-object)
  - `paired-with` → [SkillEvidence](#skillevidence)
  - `supports` → [Capability](#capability)
  - `may-promote-to` → [Wrapper Tool](#wrapper-tool)
  - `is-a` → [Growth Object](#growth-object)
  - `evaluated-by` → [GrowthEvalContract](#growthevalcontract)

### SkillEvidence
- **Category**：Capability Layer / Runtime Evidence
- **Aliases**：skill runtime evidence
- **Definition**：附着在一个 `SkillSpec` 上的动态经验层，记录 success / failure、positive / negative patterns、known breakages 等运行时证据。它不是单独的 capability 层，而是 skill 的可学习部分。
- **Relations**：
  - `attached-to` → [SkillSpec](#skillspec)

### Capability
- **Category**：Product Surface
- **Aliases**：capability cluster
- **Definition**：对外稳定暴露的能力名或能力簇。它不是内部真实成长对象；内部实际支撑物通常是一个或多个 skill object。
- **Relations**：
  - `supported-by` → [Skill Object](#skill-object)

### Wrapper Tool
- **Category**：Capability Layer / Governance Object
- **Aliases**：`wrapper_tool`
- **Definition**：稳定的能力封装单元。它内部可以组合多个底层动作，但对上层仍表现为一个原子动作。适合“多命令但仍原子”的场景，复杂到需要 state / guard / recovery 时就不再适合停留在 wrapper tool。
- **Relations**：
  - `built-from` → [Atomic Tool](#atomic-tool)
  - `may-be-promoted-from` → [SkillSpec](#skillspec)
  - `may-promote-to` → [ProcedureSpec](#procedurespec)
  - `is-a` → [Growth Object](#growth-object)

### ProcedureSpec
- **Category**：Runtime Control / Governance Object
- **Aliases**：`procedure_spec`
- **Definition**：多步流程的静态协议定义。它描述状态、guard、transition 和允许动作，但它本身不是运行时实例。适用于多步、跨 turn、有顺序依赖、有副作用、需要 approval / recovery 的任务。
- **Relations**：
  - `executed-by` → [Procedure Runtime](#procedure-runtime)
  - `may-be-entered-from` → [Skill Object](#skill-object)
  - `may-be-promoted-from` → [Wrapper Tool](#wrapper-tool)
  - `is-a` → [Growth Object](#growth-object)

### Procedure Runtime
- **Category**：Runtime Control
- **Aliases**：procedure engine
- **Definition**：执行 `ProcedureSpec` 的 deterministic runtime control layer。它负责 guard、execute、context patch、transition、checkpoint、resume 和 side-effect boundary，而不是承担高层经验学习。
- **Relations**：
  - `consumes` → [ProcedureSpec](#procedurespec)
  - `manages` → [Active Procedure](#active-procedure)
  - `uses` → [Atomic Tool](#atomic-tool)

### Active Procedure
- **Category**：Runtime Control
- **Aliases**：procedure instance
- **Definition**：某个 `ProcedureSpec` 在运行时的会话内实例。它记录当前 state、上下文和推进状态，是 spec 的动态执行态而不是静态定义。
- **Relations**：
  - `instance-of` → [ProcedureSpec](#procedurespec)
  - `managed-by` → [Procedure Runtime](#procedure-runtime)

### Memory Application Spec
- **Category**：Memory / Governance Object
- **Aliases**：`memory_application_spec`
- **Definition**：建立在稳定 memory kernel 之上的声明式 memory application 规格。当前在 `P2-M1` 中仍是 tentative reserved kind，正式定义推迟到 `P2-M3`。
- **Relations**：
  - `is-a` → [Growth Object](#growth-object)

### Raw Code Patch
- **Category**：Implementation Artifact
- **Aliases**：repo diff, code diff
- **Definition**：实现某个 proposal 时产生的代码改动产物。在 `P2-M1` 中，它本身不是 growth object，只是 implementation artifact 或 supporting evidence。
- **Relations**：
  - `supports` → [Growth Proposal](#growth-proposal)
  - `is-not-a` → [Growth Object](#growth-object)
