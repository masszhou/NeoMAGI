# P2-M1 Post Works 架构规划（草案）

- Date: 2026-04-06
- Status: draft
- Scope: `P2-M1` closeout 后、`P2-M2` 开工前的一组窄范围 post-works；只解决直接阻塞后续 coding / multi-session / runtime 轻量演进的缺口，不提前实现 `Procedure Runtime`
- Basis:
  - [`design_docs/phase2/roadmap_milestones_v1.md`](/Users/zhiliangzhou/devel/Zhiliang/NeoMAGI/design_docs/phase2/roadmap_milestones_v1.md)
  - [`design_docs/phase2/p2_m2_architecture.md`](/Users/zhiliangzhou/devel/Zhiliang/NeoMAGI/design_docs/phase2/p2_m2_architecture.md)
  - [`dev_docs/plans/phase2/p2-m1c_growth-cases-capability-promotion_2026-03-18.md`](/Users/zhiliangzhou/devel/Zhiliang/NeoMAGI/dev_docs/plans/phase2/p2-m1c_growth-cases-capability-promotion_2026-03-18.md)
  - [`src/frontend/src/stores/chat.ts`](/Users/zhiliangzhou/devel/Zhiliang/NeoMAGI/src/frontend/src/stores/chat.ts)
  - [`src/frontend/src/components/chat/ChatPage.tsx`](/Users/zhiliangzhou/devel/Zhiliang/NeoMAGI/src/frontend/src/components/chat/ChatPage.tsx)
  - [`src/agent/message_flow.py`](/Users/zhiliangzhou/devel/Zhiliang/NeoMAGI/src/agent/message_flow.py)
  - [`src/agent/tool_runner.py`](/Users/zhiliangzhou/devel/Zhiliang/NeoMAGI/src/agent/tool_runner.py)
  - [`src/tools/base.py`](/Users/zhiliangzhou/devel/Zhiliang/NeoMAGI/src/tools/base.py)
  - [`src/tools/registry.py`](/Users/zhiliangzhou/devel/Zhiliang/NeoMAGI/src/tools/registry.py)
  - [`src/session/manager.py`](/Users/zhiliangzhou/devel/Zhiliang/NeoMAGI/src/session/manager.py)

## Context

`P2-M1` 已经完成 growth governance、`skill_spec` runtime 与 `wrapper_tool` onboarding 的主线闭环，但在真正进入 `P2-M2` 之前，还存在 3 个现实缺口：

1. WebChat 仍把 `session_id` 固定写死为 `"main"`，当前用户无法在前端创建、切换、观察多个 session。
2. tool runtime 仍按单 turn 串行执行 tool calls；对只读型 repo inspection 工具而言，这会人为放大 latency。
3. `coding / builder` 相关 atomic tool surface 仍过窄；后续 coding capability 测试缺少最低可用的原子操作面。

这些缺口与 `P2-M2` 的关系是：

- 它们都不是 `Procedure Runtime` 本体。
- 但它们会直接影响 `P2-M2` 之前的手测、coding eval 和 runtime 演进质量。
- 若不先做，后续很容易把 `P2-M2` 变成“同时补 UI、补原子工具、补调度语义”的混合里程碑，复杂度失控。

因此建议在 `P2-M2` 前明确插入一个窄范围 tranche：`P2-M1 post works`。

## Core Decision

`P2-M1 post works` 只做 3 组工作，而且每组都保持最小边界：

1. 前端加入 multi-session 切换，但不把它做成完整聊天产品的 server-synced 会话中心。
2. 在 tool interface 上增加 fail-closed 的并发元数据，让 runtime 可以自动并行调度同一 turn 内的只读、安全 tool。
3. 按风险分层扩展 coding atomic tools，优先补齐 repo inspection，再补文件写入，最后才考虑 `bash`。

这里的关键原则是：

- 不把 post-works 膨胀成 `P2-M2` 的提前实现。
- 不引入重型 scheduler / workflow engine。
- 不为了“会写代码”而提前放开无边界执行面。

## Goals

- `G1.` 让用户可以在 WebChat 中显式创建、切换多个 session，并允许非当前激活 session 在后台继续运行。
- `G2.` 让 runtime 能在同一 turn 中对明确声明为 `read_only + concurrency_safe` 的 tool calls 做有界并行。
- `G3.` 为后续 coding capability 测试补齐最小 atomic tool surface：`glob`、`grep`、`write_file`、`edit_file`、`bash`。
- `G4.` 保持 `P2-M2` 边界清晰：post-works 不承诺 `ProcedureSpec`、`ActiveProcedure`、checkpoint steering、resume state machine。

## Non-Goals

- 不在此阶段实现 `Procedure Runtime`、checkpoint、interrupt / resume state machine。
- 不在此阶段引入 server-side session list / title generation / shared inbox 式聊天产品层。
- 不在此阶段做通用 tool DAG 调度、tool dependency inference 或跨 turn 并发计划。
- 不在此阶段默认向普通 `chat_safe` 用户开放高风险 coding tools。
- 不在此阶段承诺“刷新页面后仍可恢复后台 streaming 中间态”。

## Work Package A: Frontend Multi-Session Switching

### A.1 目标

让 WebChat 拥有最小但真实可用的 multi-session UX，并且语义上对齐你观察到的 Codex / Claude 风格行为：

- 切换 active session 不等于取消当前运行。
- 非当前激活 session 可以在后台继续跑。
- 后台运行结束后，前端需要给出完成信号，而不是静默结束。

### A.2 当前约束

- 前端当前把 `chat.history` 与 `chat.send` 的 `session_id` 都写死为 `"main"`。
- 前端当前的 `messages`、`isStreaming`、`isHistoryLoading` 也是全局状态，而不是 per-session 状态。
- 后端 WebSocket 协议已经支持任意 `session_id`；这不是后端协议缺失，而是前端状态没建起来。
- 后端 dispatch 是按 `session_id` 做 claim / release；这意味着“同一 session 串行、不同 session 可并发”在后端语义上已经成立。
- 当前后端没有正式的 “list sessions” API；因此前端无法从服务端拉到一个全局会话目录。

### A.3 架构决策

V1 采用“单连接、多 session、本地已知列表”的极简方案：

- 保留一个 WebSocket 连接。
- 前端 store 新增 `activeSessionId`。
- 前端维护 `sessionsById` / `sessionOrder` / `requestToSession` 三类本地状态。
- 新建 session 只是生成新的 `session_id` 并切换 active session。
- 切到其他 session 时，不自动取消正在运行的旧 session 请求。
- 允许“每个 session 同时最多一个 active request”，但不同 session 可并发运行。

这里必须区分两个概念：

- `active session`
  - 当前用户正在看的会话。
- `running request`
  - 某个 `session_id` 下正在 streaming 的请求。

这两个概念不能再复用同一个布尔状态，否则切走就会误伤后台运行。

当前协议的一个好处是：

- streaming 事件已经以 `request_id` 作为关联键返回
- 因此前端只要维护 `requestToSession` 映射，就可以在不改协议的前提下把后台事件正确归属到对应 session

这意味着 V1 不必先改 WebSocket 协议，就可以落地后台 session 语义。

### A.4 建议状态模型

- `activeSessionId: string`
- `sessionsById: Record<sessionId, SessionViewState>`
- `sessionOrder: string[]`
- `requestToSession: Record<requestId, sessionId>`

建议最小 `SessionViewState`：

- `messages`
- `isHistoryLoading`
- `isStreaming`
- `lastActivityAt`
- `hasUnreadCompletion`
- `lastError`

其中：

- `requestToSession` 用来把后台流式事件路由回正确 session。
- `hasUnreadCompletion` 用来表达“你切走后，它已经跑完了”。

### A.5 交互建议

V1 不需要完整左侧会话中心，但至少应有：

- `New Session` 按钮
- 当前 active session 标识
- 最近若干 session 的切换入口
- 非 active session 的 running / done badge

推荐行为：

- 用户在 `session-A` streaming 时切到 `session-B`，`session-A` 继续在后台接收流。
- 若 `session-A` 在后台完成，UI 显示 completion badge。
- 回到 `session-A` 时可以看到完整结果。

### A.6 边界与取舍

V1 不要求：

- 后端提供全局 session list
- 跨设备同步 session 列表
- 刷新页面后恢复所有后台请求的中间 streaming 状态

若未来需要完整聊天产品体验，再单独追加：

- `chat.sessions.list`
- 会话标题摘要
- 最近活动排序
- server-synced unread / completion 状态

### A.7 验收建议

- 用户可以从前端创建至少两个不同 `session_id` 的会话。
- 在 `session-A` streaming 期间切到 `session-B` 不会取消 `session-A`。
- 后台完成的 `session-A` 能在前端显式显示完成信号。
- 两个 session 的历史不会互相污染。

## Work Package B: Tool Concurrency Metadata 与轻量并行调度

### B.1 目标

引入一套足够轻量、但能真实减少只读 tool latency 的元数据与调度规则。

### B.2 关键判断

单独一个 `is_read_only` 不够，原因是：

- 有些 tool 虽然不写状态，但并不适合并发跑。
- 风险来源可能是 rate limit、共享临时路径、顺序敏感外部 API、资源竞争，而不只是“是否写文件”。

因此建议显式保留两个 fail-closed 属性：

- `is_read_only: bool = False`
- `is_concurrency_safe: bool = False`

只有两者都为 `True`，runtime 才允许自动并行。

### B.3 运行时语义

post-works 不做通用 scheduler，只做“同一 LLM turn 内、连续只读批次”的并行。

建议规则：

1. 扫描同一轮模型返回的 `tool_calls_result`。
2. 按模型顺序切分 execution groups。
3. 只有“连续出现、且每个 tool 都声明 `read_only + concurrency_safe`”的 group 才并行执行。
4. 任意非并发安全或写入型 tool 都是 barrier；barrier 之后重新开始下一组。

示例：

- `[grep, glob, read_file]` 可并行
- `[grep, write_file, grep]` 只能按 `grep` 并行组 -> `write_file` 串行 -> `grep` 新组
- `[bash, grep]` 默认按串行处理，除非未来 `bash` 的具体实现明确声明并发安全

### B.4 Transcript 与 determinism

即使并行执行，也不建议按完成先后把 `tool` messages 写回 transcript。

建议保持：

- 执行可以并行
- transcript 写入顺序仍按模型给出的 tool call 顺序

原因：

- 这样最接近当前串行语义，历史稳定。
- 可以降低 compaction、replay 与 debug 的复杂度。
- 不会让“完成快的工具先入 transcript”污染模型的预期顺序。

### B.5 并发上限

即使 tool 声明允许并发，也要有全局上限。

建议 V1 只支持：

- 每组最多 `2~4` 个并行 tool calls
- 超出部分按顺序分批执行

理由：

- read-only 并不等于免费
- repo scan、IO、第三方 API 都可能被并发放大

### B.6 Observability

建议补充运行时可观测字段：

- `tool_parallel_group_started`
- `tool_parallel_group_finished`
- `group_size`
- `serial_barrier_tool`

这样后续如果延迟改善不明显，能判断问题是：

- 模型没有产生并行友好的 call pattern
- tool metadata 标注过于保守
- 或某个 barrier tool 过早切断批次

### B.7 验收建议

- 至少两种只读 tool 能在同一 turn 内并行执行。
- 任意写入型 tool 会形成串行 barrier。
- transcript 中的 `tool` message 顺序保持 deterministic。
- 所有未显式声明的工具默认继续串行，保持 fail-closed。

## Work Package C: Atomic Tools 扩展用于 Coding Capability 测试

### C.1 目标

为后续 coding ability 手测与 benchmark 提供最低可用的 atomic tool surface，而不是继续靠 prompt 内想象 repo 状态。

### C.2 现实约束

当前 runtime 虽然已有 `ToolMode.coding` 概念，但 session mode 读取处仍把非 `chat_safe` 模式强制降级。  
这意味着：

- 如果不先定义一个明确的 coding eval / experimental 入口，
- 后续即使实现了 `grep` / `glob` / `edit_file` / `bash`，
- 它们也不会真正进入运行路径。

因此 `WP-C` 的前置动作不是直接加 5 个工具，而是先冻结“这些工具在哪个 mode / 入口下可用”。

### C.3 建议拆分

不建议把这 5 个工具作为同一风险层一起落地。  
建议拆成三个子层：

#### C.3.1 Read-Only Repo Inspection

- `glob`
- `grep`

建议属性：

- `allowed_modes = coding`
- `risk_level = low`
- `is_read_only = True`
- `is_concurrency_safe = True`

用途：

- 文件发现
- 文本 / 符号搜索
- 与现有 `read_file` 形成最小 repo inspection 组合

#### C.3.2 Deterministic File Mutation

- `write_file`
- `edit_file`

建议属性：

- `allowed_modes = coding`
- `risk_level = high`
- `is_read_only = False`
- `is_concurrency_safe = False`

建议语义：

- `write_file` 负责 create / replace whole file
- `edit_file` 负责受上下文约束的局部编辑
- 任何 path 都必须限制在 workspace 内
- `edit_file` 需要 fail-fast；上下文不匹配时直接失败，不做模糊 patch

#### C.3.3 Guarded Shell

- `bash`

建议属性：

- `allowed_modes = coding`
- `risk_level = high`
- `is_read_only = False`
- `is_concurrency_safe = False`

建议边界：

- workspace-bounded `cwd`
- 明确 timeout
- 输出截断
- 禁止交互式命令
- 默认不继承危险环境变量

`bash` 虽然对 coding agent 很重要，但它和 `glob` / `grep` 的风险级别完全不同。  
因此建议在 post-works 中把它放到最后单独落地，而不是和 read-only tools 一起打包。

### C.4 推荐顺序

1. 先冻结 `coding mode` 的实验入口或 eval 入口
2. 落 `glob` / `grep`
3. 落 `write_file` / `edit_file`
4. 最后落 `bash`

这个顺序的好处是：

- 你会尽早得到最有价值、风险最低的 repo inspection 能力
- `WP-B` 的并发调度可以立即作用在 `glob` / `grep`
- 写入与 shell 风险被推迟到更明确的 guard 边界之后

### C.5 验收建议

- agent 能在 coding eval 路径下完成最小 repo inspection：`glob + grep + read_file`
- agent 能通过 `edit_file` 或 `write_file` 完成一次受限文件修改
- agent 能通过 `bash` 运行一次 workspace 内的非交互验证命令
- 默认 `chat_safe` 路径不暴露这些高风险工具

## Recommended Sequencing

建议把 post-works 拆成 4 个执行阶段，而不是 3 个并行大包：

### PW-0: 入口冻结

- 明确 `coding mode` / eval mode 的曝光路径
- 明确 multi-session V1 只做“本地已知列表”，不要求 server-side list API

### PW-1: Multi-Session UX

- 前端 state model
- `New Session`
- session switch
- background completion badge

### PW-2: Tool Concurrency Metadata

- `BaseTool` 元数据
- execution group 切分
- bounded parallel execution

### PW-3: Atomic Coding Surface

- `glob` / `grep`
- `write_file` / `edit_file`
- `bash`

其中：

- `PW-1` 与 `PW-2` 可以并行开发
- `PW-3` 最好在 `PW-2` 之后衔接，这样只读工具一上线就能受益于并行调度

## Risks

### R1. Multi-session 只做前端本地列表，会有“看不到其他设备 / 旧浏览器创建的 session”问题

这是可接受的 V1 取舍，但文档必须明确：  
V1 不是完整会话中心，而是“当前客户端已知 session 列表”。

### R2. 后台运行与页面刷新不是一回事

本规划只保证“同一个前端进程中，切换 active session 不取消运行”。  
它不保证“浏览器刷新 / 断连后仍可继续观察同一个 streaming 中间态”。

### R3. `is_read_only` 被错误等同于“可安全并行”

这会在后期引入很隐蔽的问题。  
因此建议坚持双标记：`read_only` 与 `concurrency_safe` 分开声明。

### R4. `bash` 可能吞掉整个 tranche 的风险预算

如果 `bash` 设计不收边界，它会从“补原子能力”滑向“重新发明 agent harness”。  
因此应明确：

- `bash` 最后做
- `bash` 不和 `glob` / `grep` 打包验收

### R5. coding tools 的真实阻塞可能不是工具本身，而是 mode 入口

若不先解决当前 `chat_safe` downgrade，atomic tools 会变成“代码存在但跑不到”的假进展。

## Open Questions

1. Multi-session V1 是否只做顶部切换器，还是直接做左侧简版 session rail？
2. `background completion signal` 你更偏好：
   - badge
   - toast
   - 还是两者都要
3. coding eval 入口是做成：
   - 独立实验模式
   - 还是沿用现有 session mode，但放开受控创建路径
4. `bash` 在 post-works 中是否应作为可选项，而不是硬验收项？

## Recommendation

我建议正式把这组工作定义为：

**`P2-M1 post works = pre-P2-M2 enablement tranche`**

理由是：

- 它解决的是 `P2-M1` 收尾后、`P2-M2` 之前最真实的使用与演进缺口。
- 它们彼此相关，但还不足以升格为新的大 milestone。
- 先把这 3 件事拆窄，能显著降低 `P2-M2` 被混入 UI / tool surface / scheduler 补洞工作的概率。

如果只按价值 / 风险比排序，我的建议是：

1. `PW-1` multi-session
2. `PW-2` tool concurrency metadata
3. `PW-3a` `glob` / `grep`
4. `PW-3b` `write_file` / `edit_file`
5. `PW-3c` `bash`

其中你提的 Claude Code 风格元数据设计，我的明确反馈是：

- 方向对，而且足够轻量
- 但不建议只保留 `is_read_only`
- 应保留 `is_concurrency_safe`
- runtime 只做“连续只读批次”的有界并行，不做更聪明的依赖推断

这会比“一上来做 procedure-level scheduler”稳很多，也更符合 post-works 的复杂度预算。
