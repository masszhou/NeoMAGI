---
doc_id: 019d7d3d-5a10-7a2b-a200-ace075b06a54
doc_id_format: uuidv7
doc_id_assigned_at: 2026-04-11T17:51:06+02:00
---
# P2-M5 Architecture（计划）

> 状态：planned  
> 对应里程碑：`P2-M5` 受治理自我演进工作流  
> 依据：`design_docs/phase2/roadmap_milestones_v1.md`、`design_docs/phase2/p2_m2_post_self_evolution_staged_plan.md`、ADR 0027、ADR 0060

## 1. 目标

- 将 NeoMAGI 的 self-evolution 从“人类手工编排多个 coding agent”推进到“系统受治理地协调一次工程演进闭环”。
- 通过固定 procedure、beads、git worktree、外部 coding agent runner、review loop 与 human gate，完成一个真实 sub-milestone。
- 保持可审计、可恢复、可停手；不自动 merge，不自动判定 UAT 通过，不绕过人类审批。

一句话：

**P2-M5 证明 NeoMAGI 能受治理地推进自己的工程演进，但仍不宣称具备无边界自治自改能力。**

## 2. 前置条件

P2-M5 不应抢跑以下能力：

- `P2-M2c`：`procedure_spec` 已进入 governance adapter，可被 propose / evaluate / apply / rollback。
- `P2-M2d`：memory source ledger prep 已完成，新写入至少能双写 DB ledger 与 workspace projection。
- `P2-M3`：principal / binding / visibility policy 已稳定，human gate 能关联明确 principal 与 approval audit。
- `P2-M4`：external collaboration / action surface 已稳定，外部 CLI、git/worktree、平台写动作能进入审批与审计路径。

若前置能力未完成，只允许做 fixture / scripted rehearsal，不得作为正式 P2-M5 验收。

## 3. 当前基线（输入）

- `P2-M1` 已提供 growth governance、skill object、wrapper tool 与 builder work memory。
- `P2-M2a/b` 已提供 Procedure Runtime、multi-agent handoff、review/publish 与 purposeful compact。
- `P2-M2c` 将补齐 procedure spec 自身的治理闭环。
- `P2-M2d` 将为 P2-M3 预备 append-only memory source ledger。
- `P2-M3` / `P2-M4` 将提供 identity、visibility、approval 与 external action surface。

P2-M5 不重新发明这些底层能力，只做受治理工作流组合。

## 4. 目标架构（高层）

### 4.1 Control Plane

- 使用一个固定、受治理的 procedure，例如 `self_evolve_submilestone_v1`。
- Procedure 负责：
  - 维护 checkpoint state。
  - 绑定 beads parent issue 与子任务。
  - 创建和记录 branch / worktree / review snapshot。
  - 触发外部 coding agent runner。
  - 收集 review findings。
  - 生成 closeout artifacts。
  - 在 human gate 处停手并等待明确批准。

### 4.2 External Agent Runner

首版至少区分两个 runner surface：

- planner / implementer：Claude Code CLI 或等价 coding agent。
- reviewer：Codex CLI 或等价 review agent。

runner 必须有明确的 typed I/O contract：

- input：scope、repo path、branch/worktree、allowed files、approved plan、round limit、timeout。
- output：summary、changed paths、findings、exit status、partial output refs、error classification。

runner 必须处理：

- timeout
- partial output
- non-zero exit
- rate limit
- auth failure
- context overflow
- interrupted run

### 4.3 Human Gates

P2-M5 至少保留三个硬 gate：

- `scope gate`：确认 sub-milestone 范围、非目标与风险。
- `plan gate`：计划审阅无 P1/P2 后，人类批准进入实现。
- `UAT gate`：用户按 test guide 完成真实交互验收后，才允许 milestone accepted。

每个 gate 必须记录：

- approving principal
- target issue / branch / commit
- approval timestamp
- approved scope or artifact ref
- residual risk decision

### 4.4 Artifact Plane

每次 P2-M5 run 至少产出：

- approved plan
- plan review report
- implementation review report
- implementation summary
- user test guide
- open issues
- progress ledger update

没有仓库内或 DB 内可追溯产物，不算成功。

## 5. 边界

### In

- 受治理 self-evolution workflow。
- beads task ledger。
- git branch / worktree isolation。
- external coding agent runner。
- plan review 与 implementation review loop。
- closeout artifact generation。
- human approval / audit / resume。

### Out

- 不自动 merge 到 `main`。
- 不自动关闭 parent issue。
- 不自动判定 UAT 通过。
- 不绕过 external action approval。
- 不让 worker 获得无限通用写权限。
- 不把一次成功 workflow 宣称为完整自治自改能力。

## 6. 建议拆分

### P2-M5a：Runner Contracts & Worktree Control

- 定义 external coding agent runner typed contract。
- 实现最小 worktree / branch / snapshot 控制。
- 只做 dry-run 或 fixture runner smoke，不执行真实仓库改动。

### P2-M5b：Self-Evolution ProcedureSpec

- 落 `self_evolve_submilestone_v1`。
- 固定 state、checkpoint、gate、round limit 与 artifact path contract。
- 验证中断 / resume / blocked-for-human-decision。

### P2-M5c：Review Loop & Artifact Writers

- 接入 planner / reviewer / implementer runner。
- 产出 plan、review report、summary、progress、user test guide、open issues。
- P1/P2 finding 未收敛时 fail-closed。

### P2-M5d：First Real Run

- 选择一个低风险、已批准 sub-milestone。
- 使用 fresh branch / worktree。
- 跑完整 scope gate -> plan gate -> implementation -> review -> UAT pending。
- 不自动 merge。

## 7. 验收

- 能推进：真实 sub-milestone 被推进到 UAT pending。
- 能收敛：review loop 在轮次上限内消除 P1/P2；不能消除时停手。
- 能留痕：beads、git、docs、progress、approval audit 均可追溯。
- 能恢复：中断后从最近 checkpoint 恢复，不要求人类重建上下文。
- 能停手：scope 未批准、plan 未批准、runner 失败、review 未收敛、UAT 未完成时，不继续推进。
