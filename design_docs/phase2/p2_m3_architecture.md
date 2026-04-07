---
doc_id: 019cc262-8b20-74d2-bc66-4a4ea19f3839
doc_id_format: uuidv7
doc_id_assigned_at: 2026-03-06T10:02:44+01:00
---
# P2-M3 Architecture（计划）

> 状态：planned  
> 对应里程碑：`P2-M3` 身份认证、用户连续性与记忆质量  
> 依据：`design_docs/phase2/roadmap_milestones_v1.md`、`design_docs/memory_architecture_v2.md`、ADR 0034、ADR 0044、ADR 0048

## 1. 目标

- 为 WebChat 引入可验证身份，使“同一个已认证用户”的连续性具备产品基础。
- 固化 canonical `user / principal` 语义，并保留 `account_id` / `peer_id` 作为绑定证据。
- 在身份前提稳定后，建立受控的跨渠道连续性与跨 agent 上下文共享规则。
- 提升记忆检索质量，并让 memory applications 开始进入正式演化入口。

## 2. 当前基线（输入）

- WebChat 当前仍是匿名会话，默认 `main`。
- Telegram 已实现 `per-channel-peer`，但仅 Telegram 侧具备受控 identity 输入。
- `SessionIdentity` 已为 `peer_id` / `account_id` 预留字段，但尚未成为完整 principal / binding 模型。
- 记忆真源已明确在 workspace，DB 作为 retrieval plane。
- 检索质量已有基础能力，但 hybrid search、memory applications、跨渠道共享规则仍未正式落地。

实现参考：
- `src/session/scope_resolver.py`
- `src/channels/telegram.py`
- `src/tools/builtins/memory_search.py`
- `design_docs/memory_architecture_v2.md`
- `decisions/0034-openclaw-dmscope-session-and-memory-scope-alignment.md`

## 3. 复杂度评估与建议拆分

`P2-M3` 复杂度：**很高**。  
原因：同时跨越 identity、session scope、channel binding、search quality、memory applications。

建议拆成 3 个内部子阶段：

### P2-M3a：Auth & Principal Kernel
- WebChat 认证登录
- canonical principal
- binding 模型

### P2-M3b：User Continuity & Sharing Policy
- verified binding 之后的 per-user continuity
- 跨渠道 / 跨 agent 分享规则
- fail-closed 默认边界

### P2-M3c：Retrieval Quality & Memory Applications
- hybrid search
- recall quality eval
- memory application spec / manifest

## 4. 目标架构（高层）

### 4.1 Principal / Binding Plane

- 产品层目标语义是：
  - `per-user continuity`
- 实现层建议区分：
  - `principal_id`
  - `account_id`
  - `peer_id`
  - `channel_type`
  - `verified`
- 未验证 binding 不允许合并到同一用户连续体。

### 4.2 Auth Plane

- WebChat 不再只依赖匿名 `session_id`。
- 登录后 session 应绑定到可验证 principal。
- 匿名路径继续存在时，默认 fail-closed，不进入用户级连续性。

### 4.3 Continuity / Sharing Plane

- 跨渠道连续性不再表达为产品层的 `per-peer`。
- 最终产品语义是“同一个已认证用户”。
- 默认共享应保持保守：
  - 不默认跨渠道共享全部上下文
  - 不默认跨 agent 共享全部记忆
  - 只允许按 policy publish / merge

### 4.4 Retrieval Quality Plane

- 检索路径建议从单一 lexical/BM25 升级为：
  - lexical
  - vector
  - hybrid template
- 记忆质量必须通过已知 miss case 回归评测，而不是只看主观体感。

### 4.5 Memory Applications Plane

- 在 memory kernel 之上允许更明确的 application spec 进入正式路径。
- 这层不改变：
  - workspace truth
  - DB retrieval plane
- 这层只增加：
  - 领域化组织方式
  - 作用域与共享策略
  - capability / skill 对 memory app 的可见性

## 5. 边界

- In:
  - WebChat 认证登录。
  - principal / binding 模型。
  - verified continuity。
  - cross-channel / cross-agent sharing policy。
  - hybrid search 与 retrieval quality eval。
  - memory application 入口。
- Out:
  - 不在匿名 Web 路径上开放用户级连续性。
  - 不把未经验证 identity 直接合并。
  - 不做重型知识图谱工程。
  - 不默认全局共享全部上下文。

## 6. 验收对齐（来自 roadmap）

- 在有身份与绑定前提时，同一用户可获得受控的跨渠道连续性。
- 在无身份前提时，系统继续正确拒绝危险共享。
- 系统能解释为什么某个渠道身份被视为同一个用户，或为什么没有被合并。
- 已知自然语句检索 miss 至少有一部分被稳定消除。
- 记忆共享范围始终可解释。
