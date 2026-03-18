# Agent Teams 配置 - NeoMAGI P2-M1c

请创建 Claude Code agent teams 来进行下面的任务。

## 0. 任务目标
交付并验收已批准的 `P2-M1c` 计划：
- `dev_docs/plans/phase2/p2-m1c_growth-cases-capability-promotion_2026-03-18.md`

任务目标是“growth case 最小闭环 + builder work memory 证据层 + `skill_spec -> wrapper_tool` capability promotion + replay / rollback 可审计证据”，不是“尽快做一个完整 procedure runtime / builder runtime / 自治成长平台”。

已确认的 steering 边界：
1. `P2-M1c` 采用 curated growth cases，而不是开放式“想学什么就临时跑什么”：
   - `GC-1 human_taught_skill_reuse` 必做
   - `GC-2 skill_to_wrapper_tool_promotion` 必做
   - `GC-3 external_readonly_experience_import` 只有在 import 协议先冻结时才允许纳入本 milestone
2. `bd / beads` 在 `P2-M1c` 里只承担 builder work memory / artifact index：
   - bead 只承载 task index、状态、摘要、artifact refs、progress / blocker / validation comments
   - 详细正文与 canonical record 必须进入 workspace artifact
   - 禁止回到 devcoord gate / ACK / heartbeat / closeout 控制面语义
3. `BuilderTaskRecord` 在 `P2-M1c` 中是逻辑对象，不要求完整映射到 `bd` metadata：
   - canonical record = workspace artifact
   - `bd` = task envelope + artifact pointer + summary index
4. `GrowthCaseSpec / GrowthCaseRun` 的持久化策略固定为极简：
   - `GrowthCaseSpec` = hardcoded catalog
   - `GrowthCaseRun` = workspace artifact（如 `dev_docs/cases/<case_id>/<run_id>.md`）
   - 不为 case run records 新增 PostgreSQL 表
5. `P2-M1c` 只 onboarding 一个新的 growth object kind：
   - `wrapper_tool` = onboarded
   - `procedure_spec` = reserved，明确推迟到 `P2-M2`
   - `memory_application_spec` = reserved，明确推迟到 `P2-M3`
6. `wrapper_tool` V1 边界固定为 single-turn typed capability：
   - 可以 code-backed / registry-backed
   - 可以绑定现有 atomic tools
   - 不允许长成 procedure runtime、generic workflow DSL 或跨 turn state machine
7. `WrapperToolSpec.implementation_ref` 的语义必须固定为 Python entrypoint：
   - `<module_path>:<factory_name>`
   - `factory_name` 返回 `BaseTool` 实例，或返回可立即注册的 `BaseTool` 子类
   - 不接受 code blob 或模糊 file path
8. `wrapper_tool` contract 升级必须遵守 ADR 0054 的 immutable contract 原则：
   - 不得直接改写 `WRAPPER_TOOL_EVAL_CONTRACT_SKELETON`
   - 必须新建 `WRAPPER_TOOL_EVAL_CONTRACT_V1`
   - runtime `_CONTRACTS` 映射切到 `V1`
9. `ToolRegistry` / wrapper runtime 必须支持 replace/remove 语义：
   - apply 时可注册 active wrapper
   - rollback / disable 时可移除 active wrapper
   - supersede 时可替换同名 wrapper
   - 不允许依赖静默覆盖掩盖 name collision
10. `wrapper_tool` 的 current-state、governance ledger 与 runtime registry 写入必须共成败：
   - 优先单事务
   - 若无法单事务，必须有显式 compensating semantics
   - 不允许 current-state / ledger / registry 漂移
11. `skill_spec -> wrapper_tool` promote 阈值直接沿用当前 `PolicyRegistry` 既有 schema：
   - `usage_count >= 3`
   - `success_rate >= 0.8`
   - `unit_test_pass`
   - `integration_smoke`
   - `risk_gate = low`
   不满足时只允许 `promote_candidate`，不允许 apply
12. `GC-2` 的依赖必须分层说明：
   - core apply path 依赖 `wrapper_tool` onboarding 完成
   - 完整闭环依赖 `builder work memory + wrapper_tool runtime` 都完成
13. 以下全部不在本轮范围：
   - `Procedure Runtime`
   - `procedure_spec` onboarding
   - `memory_application_spec` onboarding
   - raw code patch 升格为独立 growth object
   - 自动 promote / 自动 apply / 自动 disable
   - 开放式自治代码搜索 / 无限 self-improvement loop
   - 通用 workflow DSL / branching wrapper graph
   - 重新把 `beads` 当成 devcoord control-plane

## 1. 必读上下文（启动前）
PM 在拆解任务前必须阅读：
1. `README.md`
2. `CLAUDE.md`
3. `AGENTS.md`
4. `AGENTTEAMS.md`
5. `design_docs/index.md`
6. `design_docs/phase2/index.md`
7. `design_docs/phase2/p2_m1_architecture.md`
8. `design_docs/phase2/roadmap_milestones_v1.md`
9. `design_docs/skill_objects_runtime.md`
10. `design_docs/GLOSSARY.md`
11. `design_docs/system_prompt.md`
12. `design_docs/devcoord_sqlite_control_plane.md`
13. `dev_docs/devcoord/sqlite_control_plane_runtime.md`
14. `dev_docs/plans/phase2/p2-m1a_growth-governance-kernel_2026-03-06.md`
15. `dev_docs/plans/phase2/p2-m1b_skill-objects-runtime_2026-03-14.md`
16. `dev_docs/plans/phase2/p2-m1b-prep_growth-eval-contract_2026-03-15.md`
17. `dev_docs/plans/phase2/p2-m1c_growth-cases-capability-promotion_2026-03-18.md`
18. `dev_docs/progress/project_progress.md`
19. `decisions/INDEX.md`
20. 重点 ADR：
   - `decisions/0048-skill-objects-as-runtime-experience-layer.md`
   - `decisions/0049-growth-governance-kernel-adapter-first.md`
   - `decisions/0050-devcoord-decouple-from-beads-and-use-sqlite-control-plane-store.md`
   - `decisions/0052-project-beads-backup-git-tracked-jsonl-exports.md`
   - `decisions/0054-growth-eval-contracts-immutable-and-object-scoped.md`
21. 关键现状代码面：
   - `src/growth/engine.py`
   - `src/growth/policies.py`
   - `src/growth/contracts.py`
   - `src/growth/adapters/base.py`
   - `src/growth/adapters/skill.py`
   - `src/skills/types.py`
   - `src/skills/store.py`
   - `src/skills/learner.py`
   - `src/skills/resolver.py`
   - `src/skills/projector.py`
   - `src/tools/base.py`
   - `src/tools/registry.py`
   - `src/agent/prompt_builder.py`
   - `src/agent/message_flow.py`
   - `src/gateway/app.py`

PM 先输出：
- Phase 拆解
- Gate 设计
- 风险清单
- 角色分工
- beads issue 树
- `GC-1 / GC-2` 证据计划
- respawn 策略

待我确认后再 spawn teammates。

## 2. `bd` 与 devcoord SQLite control plane 使用规则（强制）
本项目现在明确分成两套系统，不能混淆：

### 2.0 为什么这样分层
这个分层不是单纯的工具偏好，而是为了避免 agent 把“待完成工作”与“协作协议状态”混成一类对象。

背景：
- 历史上 `beads` 曾同时承载 backlog issue 和 devcoord control-plane 对象，但这会让 `bd list` / `bd ready` 同时混入真实任务与 Gate / ACK / heartbeat / 恢复握手等协议状态，导致 backlog 视图不可读。
- devcoord 真正要解决的是协议状态机问题：
  - 哪个 Gate 当前 open
  - 哪条指令是否已 ACK 生效
  - 哪个角色需要等待恢复同步
  - projection / audit 是否对账完成
  这些都不属于 issue tracker 语义。
- 因此当前定义固定为三层：
  - `bd / beads` = backlog / issue graph / review follow-up / builder work memory index
  - `scripts/devcoord/coord.py` = 协作协议运行时
  - `.devcoord/control.db` = devcoord control-plane 唯一 SSOT
  - `dev_docs/logs/*` + `project_progress.md` = render 生成的 projection / 人类可读证据

对 agent 的直接影响：
- 当你在回答“现在还有什么工作可做 / 我该 claim 哪个任务 / 新发现的 follow-up 怎么挂依赖”时，应该使用 `bd ... --json`。
- 当你在回答“当前 Gate 是否放行 / 是否需要 ACK / 是否该 heartbeat / 是否该 render/audit / milestone 是否可关闭”时，应该使用 `uv run python scripts/devcoord/coord.py ...`。
- 当你在阅读 `dev_docs/logs/*`、`gate_state.md`、`watchdog_status.md` 时，必须把它们视为 projection，而不是控制面真源；若 projection 与控制动作冲突，以 `.devcoord/control.db` 经 `coord.py` 读出的状态为准。
- SQLite 在这里只服务 devcoord 内部协作控制面，不代表产品运行时存储技术发生变化；产品数据面仍然是 PostgreSQL 17。

### 2.1 Issue Tracking
1. 所有任务跟踪一律使用 `bd ... --json`
2. 禁止使用 markdown TODO / 临时任务清单替代
3. PM 启动时必须先检查：
   - `bd ready --json`
4. PM 必须为 `P2-M1c` 建立/整理 issue 树：
   - 一个 milestone 级 epic / 主任务
   - 每个 Phase 至少一个子任务
   - `GC-1`、`GC-2` 至少各有一条可追踪任务
   - 新发现工作必须用 `discovered-from:<parent-id>` 关联
5. Backend / Tester 开工前必须 claim 自己负责的 issue：
   - `bd update <id> --claim --json`
6. 阶段完成后及时 `bd close ... --reason "Completed"` 或更新状态

说明：
- `bd / beads` 负责 backlog / issue graph / epic / review follow-up / builder work memory index。
- `bd` 不再承载任何 live devcoord control-plane 状态。

### 2.2 Devcoord SQLite Control Plane
1. 协作控制写操作一律走：
   - `uv run python scripts/devcoord/coord.py ...`
2. 禁止直接手写：
   - `dev_docs/logs/phase2/*`
   - `gate_state.md`
   - `watchdog_status.md`
   - `heartbeat_events.jsonl`
   - `dev_docs/progress/project_progress.md`
3. devcoord control-plane 的唯一 SSOT 是 repo 根：
   - `.devcoord/control.db`
4. `dev_docs/logs/phase2/*` 和 `dev_docs/progress/project_progress.md` 只是 `projection render` 生成的 projection，不是手写真源
5. PM / teammate 不得用 `bd`、SQLite ad-hoc 查询、或直接文件编辑替代 `scripts/devcoord/coord.py` 完成 devcoord 写操作
6. canonical grouped CLI 以当前 runtime 为准：
   - `gate open|review|close`
   - `command ack|send`
   - `event heartbeat|phase-complete|recovery-check|state-sync-ok|stale-detected|log-pending|unconfirmed-instruction`
   - `projection render|audit`
   - `milestone close`
   - `apply <action>` 作为结构化 payload 入口
7. Gate 关闭前 PM 必须执行：
   - `projection render`
   - `projection audit`
   且要求 `audit.reconciled=true`
8. milestone closeout 不依赖 beads sync；按照 SQLite control-plane runbook 执行：
   - `gate review`
   - `projection render`
   - `projection audit`
   - `gate close`
   - `projection render`
   - `projection audit`
   - `milestone close`

### 2.3 常见误用（重点提醒）
1. 不要把 issue bead 当成 gate / heartbeat / ACK 控制面事件。
2. 不要用 `bd create/update` 记录 devcoord 状态。
3. 不要把 `.beads/` 误当成 devcoord 控制面真源；它只承载 issue tracking 和 builder work memory index。
4. 不要直接编辑 `dev_docs/logs/phase2/*` 试图“补日志”。
5. 不要用 SQLite CLI / DB Browser 手工改 `.devcoord/control.db`。
6. 不要忘记：
   - teammate devcoord 写操作前先校验 `git rev-parse HEAD == target_commit`
7. 不要使用：
   - `bd sync`
   - `bd dolt pull`
   - `bd dolt push`
8. 只有本轮实际修改了 beads / bd issue 数据时，才需要在收尾执行：
   - `just beads-backup`
   - `git add .beads/backup/ && git commit -m "bd: backup <date>"`
   - devcoord control-plane 写入不触发 beads backup

## 3. Skills 要求（Claude Code 强制）
如使用 Claude Code：
1. PM 必须显式使用：
   - `.claude/skills/devcoord-pm/SKILL.md`
   - slash 形式优先：`/devcoord-pm`
2. Backend 必须显式使用：
   - `.claude/skills/devcoord-backend/SKILL.md`
   - slash 形式优先：`/devcoord-backend`
3. Tester 必须显式使用：
   - `.claude/skills/devcoord-tester/SKILL.md`
   - slash 形式优先：`/devcoord-tester`
4. PM spawn prompt 中必须明确写出对应 skill 名称、skill 路径、slash 名称
5. 对 Claude Code 的 devcoord 关键流程，PM 至少一次用 CLI debug 或：
   - `scripts/devcoord/check_skill_activation.sh`
   验证 skill 实际命中
6. Teammate 在任何 devcoord 写操作前，必须先验证：
   - `git rev-parse HEAD == target_commit`
   若不一致，只允许回报阻塞，不允许写控制面

## 4. 全局工作原则
1. 实现以已批准 `P2-M1c` 计划和相关 ADR 为准；冲突时先升级为 open question。
2. 先交付 case-driven、promotion-first、work-memory-backed 的最小闭环，不做与 `P2-M1c` 无关重构。
3. `bd / beads` 只做 builder work memory index 与 artifact pointer，不做 control-plane，也不做 product memory truth。
4. builder work memory 采用双层表达：
   - canonical record = workspace artifact
   - bead = issue / state / comments / artifact refs / promote candidate index
5. `GrowthCaseSpec` 必须保持 curated catalog；禁止把临时 prompt 或 ad-hoc 测试当成正式 case。
6. `GrowthCaseRun` 不进 PostgreSQL；V1 只允许 workspace artifact + bead refs。
7. `wrapper_tool` V1 必须保持 single-turn typed capability 边界；超出直接提 backlog 给 `procedure_spec` / `P2-M2`。
8. `implementation_ref` 固定为 `<module>:<factory>`；不得用 code blob、动态生成代码、或模糊 file path。
9. `wrapper_tool` contract 升级必须遵守 immutable contract：
   - 新建 `WRAPPER_TOOL_EVAL_CONTRACT_V1`
   - runtime 切到 `V1`
   - skeleton 不再被 runtime 使用
10. `ToolRegistry` 不允许只有 add 语义；必须有 replace/remove 路径来支撑 apply / rollback / supersede。
11. `GC-1` 先验证“学成 skill 并在相似任务中复用”；`GC-2` 再验证 promote；不得跳过 reuse 直接宣称升格成功。
12. promotion threshold 只做保守 apply：
   - 阈值不满足 → candidate only
   - target kind 未 onboard → recommendation only
   - 只有阈值满足且 runtime 接线完成后才允许 apply
13. 所有结论必须附证据：文件路径、关键行、命令、测试结果、artifact 路径、proposal / eval / apply / rollback refs。
14. 不允许静默跳过不确定项；必须写明推荐方案、影响、回滚路径。

## 5. 成员与职责
### 5.1 PM
1. 负责拆解、分派、节奏控制、阶段验收，不写实现代码。
2. 为每个角色创建独立 worktree，并在 spawn prompt 中写明绝对路径。
3. 负责：
   - 建立 beads issue 树
   - 维护 devcoord control plane
   - 收集 Backend / Tester 证据
   - gate open / close
4. 每阶段收口必须收齐：
   - 变更清单
   - beads issue 状态
   - 验证证据
   - `GC-1 / GC-2` requirement-evidence matrix
   - Tester 结论
   - 残余风险
   - commit sha

### 5.2 Backend Developer
1. 负责 `P2-M1c` 实现与自测。
2. 每个 phase 结束时提交：
   - 代码 / 文档 / migration 变更
   - 关键设计说明
   - 测试证据
   - beads issue 更新
   - commit sha
3. 未收到 PM 的 `GATE_OPEN` 不得跨 phase 推进。

### 5.3 Tester and Reviewer
1. 使命是证明“计划边界是否兑现”，不是“测试是否跑完”。
2. 必须输出：
   - 结论：PASS / PASS_WITH_RISK / FAIL
   - Findings（按严重度，含路径和行号）
   - Requirement-Evidence Matrix
   - Residual Risks
   - Gate 建议
3. 任一 P0 / P1 未关闭，结论必须 FAIL。
4. 核心验收项缺证据，结论不得 PASS。

### 5.4 Frontend
Frontend 本轮默认不 spawn。`P2-M1c` 聚焦 growth / builder / wrapper runtime，不做前端 UI 新功能。

## 6. P2-M1c Phase / Gate 范围（强约束）
### Phase 0：ADR + Vocabulary Freeze
- 目标：
  - 冻结 `bd / beads` work memory 与 control-plane 的边界
  - 冻结 `GrowthCaseSpec / GrowthCaseRun` 的持久化策略
  - 冻结 `wrapper_tool` 的 V1 对象边界
  - 冻结 `implementation_ref = <module>:<factory>`
  - 新建 `WRAPPER_TOOL_EVAL_CONTRACT_V1` 并切换 runtime `_CONTRACTS`
  - 决定 `GC-3` 是否进入本 milestone
- Gate 核心：
  - `GrowthCaseSpec` 必须是 hardcoded curated catalog
  - `GrowthCaseRun` 必须是 workspace artifact，不新增 DB run store
  - `WRAPPER_TOOL_EVAL_CONTRACT_SKELETON` 不得继续作为 runtime contract
  - `GC-3` 若 import 协议未冻结，不得进 acceptance
  - `bd` feasibility spike 与 `artifact-first + bead-pointer-only` fallback 必须写清

### Phase 1：Builder Work Memory Substrate
- 目标：
  - 新增 builder work memory 类型与 artifact 模板
  - 落地 bead + artifact 双层结构
  - 固定 builder task / growth case 的索引语义
  - 完成 `bd` feasibility spike
- Gate 核心：
  - canonical record 必须在 workspace artifact
  - bead 只允许承担 task envelope / state / comments / refs
  - 不触碰 `.devcoord/control.db` 语义
  - 若 `bd` 能力不足，必须可退化到 `artifact-first + bead-pointer-only`

### Phase 2：Wrapper Tool Store + Adapter + Runtime Wiring
- 目标：
  - 新增 `wrapper_tool` types / store / governance adapter
  - 新增 Alembic migration：
    - `wrapper_tools`
    - `wrapper_tool_versions`
  - 修改 `src/growth/policies.py` 使 `wrapper_tool` onboarded
  - 修改 `src/tools/registry.py` 接入 replace/remove 路径
- Gate 核心：
  - `wrapper_tool` 必须正式 onboarded
  - `procedure_spec` 必须继续 reserved，并明确推迟到 `P2-M2`
  - `wrapper_tool.notes` 与 `procedure_spec.notes` 必须同步更新，避免 milestone 口径残留歧义
  - `ToolRegistry` 必须支持 rollback / disable / supersede 的 replace/remove 语义
  - current-state / ledger / registry 不得漂移

### Phase 3：Growth Case Catalog + Runner
- 目标：
  - 新增 case catalog 与 case runner
  - 落地 `GC-1` 和 `GC-2`
  - `GC-3` 仅在 import 协议已冻结时进入
  - 串起 bead / artifact / proposal / eval / apply / rollback refs
- Gate 核心：
  - `GC-1` 必须证明 skill 学成后在相似任务中复用
  - `GC-2` 的 core apply path 依赖 `wrapper_tool` runtime 已完成
  - `GC-2` 的完整闭环依赖 `builder work memory + wrapper_tool runtime`
  - case 失败时必须给出 `candidate_only` / `veto` / `rollback`
  - 成功 case 必须有 replay / before-after 级证据

### Phase 4：Acceptance Closeout
- 目标：
  - 用 roadmap 用例 A~F 收口 `P2-M1c`
  - 汇总 evidence packet
  - 跑 lint / test / targeted integration / smoke
- Gate 核心：
  - 至少完成 `GC-1 + GC-2`
  - skill 必须先 reuse，再 promote
  - 至少一条失败 case 完成 `veto` 或 `rollback`
  - 收口前必须跑：
    - `just lint`
    - `just test`

## 7. Respawn 策略
1. 默认采用 phase 边界 respawn：
   - 每个 Gate 关闭后，Backend / Tester 默认 respawn
2. 中途 respawn 触发条件：
   - context compaction >= 2 次
   - 连续两次遗漏明确约束
   - 恢复后一次 `STATE_SYNC_OK` 无法对齐
   - PM 判定上下文噪声已影响交付质量
3. respawn 前必须：
   - commit + push 当前可提交工作
   - 更新 beads issue
   - devcoord 落盘当前状态
   - 产出 handoff 文件
4. 禁止无 handoff respawn。

## 8. 协作控制协议（强制）
### 8.1 Gate 状态机
1. 只有 PM 可以发布 Gate 状态。
2. 放行格式固定：
   - `GATE_OPEN gate=<gate-id> phase=<phase> target_commit=<sha> allowed_role=<role>`
3. 关闭格式固定：
   - `GATE_CLOSE gate=<gate-id> result=<PASS|PASS_WITH_RISK|FAIL> report=<path> report_commit=<sha>`
4. 无 `GATE_OPEN + target_commit`：
   - Backend 不得进入下一 phase
   - Tester 不得启动验收
5. phase 完成后 teammate 必须发送：
   - `PHASE_COMPLETE role=<role> phase=<N> commit=<sha>`

### 8.2 ACK 生效机制
1. `STOP`、`WAIT`、`RESUME`、`GATE_OPEN`、`PING` 必须 ACK 才生效。
2. ACK 格式：
   - `[ACK] role=<role> cmd=<cmd> gate=<gate-id|na> commit=<sha|na>`

### 8.3 恢复握手
1. teammate 重启 / 压缩后先发：
   - `RECOVERY_CHECK role=<role> last_seen_gate=<gate-id|unknown>`
2. PM 回复状态快照。
3. teammate 仅在收到：
   - `STATE_SYNC_OK role=<role> gate=<gate-id> target_commit=<sha>`
   后才能继续。

### 8.4 worktree / 分支同步
1. Backend phase 完成后必须先 `commit + push` 再回传 sha。
2. Tester 启动验收前必须执行并回传：
   - `git fetch --all --prune`
   - `git merge --ff-only origin/<backend-branch>`
   - `git rev-parse HEAD`
3. Tester 禁止基于未 push 的本地中间态给结论。

### 8.5 心跳与超时
1. 每个 teammate 至少每 15 分钟发一次心跳。
2. 长任务开始即发，结束后 2 分钟内补结果。
3. 心跳格式固定：
   - `[HEARTBEAT] role=<role> phase=<phase> status=<working|blocked|done> since=<ISO8601> eta=<min> next=<one-line>`

## 9. 输出与归档要求
1. PM 汇总写入：
   - `dev_docs/logs/phase2/p2-m1c_<YYYY-MM-DD>/pm.md`
2. Tester 报告固定路径：
   - `dev_docs/reviews/phase2/p2-m1c_<phase>_<YYYY-MM-DD>.md`
3. 如发生 respawn，handoff 固定路径：
   - `dev_docs/logs/phase2/p2-m1c_<YYYY-MM-DD>/handoff/<role>_<phase>_<ts>.md`
4. 最终验收必须包含：
   - 命令列表与结果摘要
   - 风险关闭情况
   - beads issue 关闭情况
   - `GC-1 / GC-2` Requirement-Evidence Matrix
   - 未完成项（若有）

## 10. 启动前检查（所有角色）
1. 执行：
   - `pwd`
   - `git branch --show-current`
   - `git status --short`
2. 确认当前 worktree 与分支符合 PM 指派。
3. 确认已阅读本文件要求与对应 skill 文档。
4. 确认知道：
   - issue tracking = `bd ... --json`
   - devcoord control plane = `uv run python scripts/devcoord/coord.py ...` -> `.devcoord/control.db`
5. 若仍不确定 `bd` issue tracking、builder work memory 与 devcoord SQLite control plane 的边界，先停下澄清，不要开工。
