# P2-M2 Architecture（计划）

> 状态：planned  
> 对应里程碑：`P2-M2` Procedure Runtime 与多 Agent 执行  
> 依据：`design_docs/phase2/roadmap_milestones_v1.md`、`design_docs/procedure_runtime.md`、ADR 0047、ADR 0048

## 1. 目标

- 将 `Procedure Runtime` 从草案推进为最小可用的 deterministic runtime control layer。
- 在单一用户利益、单一 `SOUL / principal` 约束下，引入 execution-oriented 多 agent runtime。
- 建立中途 steering / interrupt / resume 的产品语义。
- 固化 bounded handoff 与 purposeful compact，避免多 agent runtime 重新变成全文上下文复制。

## 2. 当前基线（输入）

- 现有 agent runtime 仍以单 agent loop 为主。
- M2 compaction 已存在，但主要服务长会话压缩，不是 task-state-oriented compact。
- `Procedure Runtime` 设计已定稿，但 runtime object、spec registry 与 active procedure lifecycle 尚未实现。
- devcoord 已验证“多执行单元协作”在开发治理层有价值，但这套能力尚未进入产品运行时。
- 当前没有正式的 runtime handoff packet、sub-agent role contract、publish / merge contract。

实现参考：
- `src/agent/agent.py`
- `src/agent/compaction.py`
- `design_docs/procedure_runtime.md`
- `decisions/0047-neomagi-multi-agent-single-soul-execution-units.md`

## 3. 复杂度评估与建议拆分

`P2-M2` 复杂度：**高**。  
原因：它同时覆盖 runtime state machine、多 agent contract、handoff、steering、compact。

建议拆成 2 个内部子阶段：

### P2-M2a：Procedure Runtime Core
- `ProcedureSpec`
- `ActiveProcedure`
- `ProcedureContextRegistry` / `ProcedureGuardRegistry`
- `ToolResult.context_patch`
- validator / executor / transition
- session-scoped single active procedure
- checkpoint-based steering / resume

### P2-M2b：Multi-Agent Runtime
- primary / worker / reviewer roles
- handoff packet
- bounded context exchange
- purposeful compact 与 publish / merge

## 4. 目标架构（高层）

### 4.1 Procedure Plane

- 引入正式 runtime object：
  - `ProcedureSpec`
  - `ActiveProcedure`
- V1 先固定为 session-scoped single active procedure；并发 procedure 留待后续单独设计。
- `AgentLoop` 只负责识别当前是否有 active procedure 并委托执行，不内联完整流程状态机。
- `ProcedureRuntime` / `ProcedureExecutor` 负责 `guard -> execute -> patch -> transition -> CAS` 主链路。
- 只约束：
  - checkpoint
  - guard
  - transition
  - side-effect boundary
- 不追求完整 choreography，不将其扩张成重型 workflow engine。

### 4.2 Agent Role Plane

- runtime 角色应保持简单：
  - `primary agent`
  - `worker agent`
  - `reviewer / critic agent`
- 所有角色共享同一用户利益与同一 `SOUL / principal`。
- 子 agent 默认不拥有独立长期记忆与独立长期身份。

### 4.3 Handoff / Exchange Plane

- agent 间默认只交换 bounded packet，而不是全文上下文：
  - task brief
  - constraints
  - current state
  - intermediate result
  - evidence
  - open questions
- publish / merge 应显式发生：
  - 没有 publish / merge 的结果，不进入用户级连续性。

### 4.4 Steering / Resume Plane

- 用户中途追加 steering 时，不直接依赖模型“自行理解新意图”。
- steering 应在 checkpoint 生效。
- 中断后恢复依赖：
  - `ActiveProcedure.state`
  - handoff packet
  - compacted task state
而不是只依赖 prompt 历史。

### 4.5 Purposeful Compact Plane

- compact 的目标从“摘要聊天”升级为“保留任务状态”：
  - 当前目标
  - TODO
  - blockers
  - last valid result
  - pending approvals
- 该层既服务长任务恢复，也服务 multi-agent handoff。

## 5. 边界

- In:
  - 最小 procedure runtime。
  - execution-oriented multi-agent runtime。
  - steering / interrupt / resume。
  - bounded handoff。
  - purposeful compact。
- Out:
  - 不建设通用 workflow engine。
  - 不引入 DAG / DSL / 并行调度系统。
  - 不实现多人格产品层。
  - 不让子 agent 获得独立长期记忆。
  - 不追求无边界 agent society。

## 6. 验收对齐（来自 roadmap）

- 用户可在多阶段任务中途追加 steering，并在 checkpoint 生效。
- 同一任务可由多个 agent 分工推进，handoff 只交换必要上下文。
- 流程中断后可从明确状态恢复，而不是完全依赖模型重新理解历史。
- 多 agent 运行时保持“单一用户利益 / 单一 SOUL”边界，不退化为多人格协作系统。
