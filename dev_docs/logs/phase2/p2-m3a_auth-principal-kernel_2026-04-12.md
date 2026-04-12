---
doc_id: 019d82f5-fdf8-775f-82f3-21ac7a96765b
doc_id_format: uuidv7
doc_id_assigned_at: 2026-04-12T20:30:52+02:00
---
# P2-M3a 实现日志：Auth & Principal Kernel

> 日期：2026-04-12
> 计划：`dev_docs/plans/phase2/p2-m3a_auth-principal-kernel_2026-04-12.md`

## 实现总结

为 WebChat 引入可验证身份，建立 canonical principal 与 binding 模型。密码 + JWT 认证、WebSocket pre-auth 握手、全链路 principal_id 传播、Telegram 自动 binding、前端 Login UI。

### 新增文件 (11)

| 文件 | 说明 |
|------|------|
| `src/auth/__init__.py` | 包标记 |
| `src/auth/errors.py` | BindingConflictError |
| `src/auth/settings.py` | AuthSettings (bcrypt hash 验证, no-auth mode) |
| `src/auth/store.py` | PrincipalStore — 7 async CRUD methods + BindingResolution |
| `src/auth/jwt.py` | create_token, verify_token, generate_secret (HS256 PyJWT) |
| `src/auth/rate_limiter.py` | LoginRateLimiter (IP-based, in-memory, 5/min → 5min lockout) |
| `src/gateway/auth_guard.py` | authorize_and_stamp_session (entry guard + authorize + stamp) |
| `alembic/versions/f3a4b5c6d7e8_create_principals_and_bindings.py` | Migration: 2 新表 + sessions.principal_id 列 |
| `src/frontend/src/stores/auth.ts` | Zustand auth store (checkAuthStatus, login, logout) |
| `src/frontend/src/components/LoginForm.tsx` | 密码登录表单 |
| `tests/test_auth_boundary.py` | 10 个 Origin/Telegram/HTTP error 边界测试 |

### 修改文件 (25)

| 文件 | 变更 |
|------|------|
| `pyproject.toml` | +bcrypt, +PyJWT 依赖 |
| `src/session/models.py` | PrincipalRecord (partial unique owner), PrincipalBindingRecord (FK RESTRICT), SessionRecord.principal_id |
| `src/session/database.py` | ensure_schema: _create_principal_tables + _add_principal_id_to_sessions |
| `src/session/scope_resolver.py` | SessionIdentity.principal_id |
| `src/session/manager.py` | ClaimResult, claim_session_for_principal (原子 SQL), set_mode(principal_id, auth_mode), get_session_principal, stamp_session_principal |
| `src/config/settings.py` | AuthSettings 集成, GatewaySettings.allowed_origins |
| `src/gateway/app.py` | lifespan PrincipalStore wiring, POST /auth/login, GET /auth/status, WebSocket pre-auth (_authenticate_ws), RPC handler authorization, NeoMAGIError HTTP handler, _is_allowed_origin Origin guard |
| `src/gateway/dispatch.py` | dispatch_chat(auth_mode=), _claim_session_or_raise → claim_session_for_principal |
| `src/gateway/protocol.py` | AuthParams, AuthResponseData, RPCAuthResponse |
| `src/channels/telegram.py` | PrincipalStore dep, _enrich_identity_with_principal (3-branch: verified/unverified/not_found), auth_mode 传递 |
| `src/agent/message_flow.py` | RequestState.principal_id, _assemble_request_state(principal_id=) |
| `src/tools/context.py` | ToolContext.principal_id |
| `src/agent/tool_runner.py` | execute_tool(principal_id=) |
| `src/agent/agent.py` | _execute_tool(principal_id=) |
| `src/agent/tool_concurrency.py` | _run_single_tool + _run_procedure_action 传播 principal_id |
| `src/infra/preflight.py` | _check_auth_mode (no-auth claimed sessions WARN, auth 0.0.0.0 no origins WARN) |
| `scripts/backup.py` | TRUTH_TABLES +principals, +principal_bindings |
| `.env_template` | AUTH_ 变量 |
| `justfile` | hash-password 任务 |
| `src/frontend/src/lib/websocket.ts` | authToken + pendingAuth + onAuthFailed |
| `src/frontend/src/stores/chat.ts` | connect(url, authToken) |
| `src/frontend/src/App.tsx` | auth 路由 (status check → LoginForm or ChatPage) |
| `src/frontend/src/components/chat/ChatPage.tsx` | 传递 authToken |
| `tests/conftest.py` | truncation +principal_bindings, +principals |
| 6 个已有测试文件 | mock 适配 (claim_session_for_principal, get_session_principal, auth_settings) |

### DB 表

- `principals`: id(VARCHAR 36 PK), name, password_hash, role; partial unique `uq_principals_single_owner WHERE role='owner'`
- `principal_bindings`: id(PK), principal_id(FK RESTRICT), channel_type, channel_identity, verified; UNIQUE (channel_type, channel_identity)
- `sessions.principal_id`: nullable VARCHAR(36) FK → principals.id ON DELETE RESTRICT

### 关键设计决策

- **claim-on-first-auth**: `claim_session_for_principal()` 原子 SQL INSERT ON CONFLICT + COALESCE(principal_id) + post-claim validation 在同一事务
- **authorize-and-stamp**: 读路径 (chat.history/session.set_mode) 用 `authorize_and_stamp_session()` 无 lock stamp；写路径 (chat.send) 额外 claim_session_for_principal defense-in-depth
- **entry guard 一致性**: auth_mode=True + principal_id=None → reject，读/写路径统一
- **no-auth 不泄漏**: 已 claim session 在 no-auth mode 下仍被拒绝（authorize 和 claim 两层）
- **Telegram 3-branch**: verified → 使用, unverified + 同 owner → verify_binding() 升级, not_found → ensure_binding(verified=True)
- **no-auth Telegram**: principal_store=None when AUTH_PASSWORD_HASH unset → auth_mode=False
- **Origin enforcement**: _is_allowed_origin() 用于 /auth/login (403) 和 /ws (close 4003 before accept)

## Review Findings & Fixes

### Plan Review (5 rounds, v1→v5)

| Round | 关键修正 |
|-------|---------|
| v1→v2 (5必须+5建议) | session 绑定矛盾→claim-on-first-auth; WS/前端竞态→pre-auth+onAuthenticated; scope_key 修正; 传播链具体化; 密码策略→hash-only |
| v2→v3 (2P1+3P2) | no-auth 泄漏→双层拒绝; 原子 claim 路径→claim_session_for_principal; tool_runner 签名; ProcedureMetadata 范围缩回; 静态 CORS+WS Origin guard |
| v3→v4 (2P1+1P2+1P3) | history stamp→authorize_and_stamp_session; auth_mode+None fail-closed; Telegram auth_mode 传递; U+FFFD 清理 |
| v4→v5 (2P1+1P2+1P3) | unverified binding→verify_binding() 升级; set_mode principal_id; authorize_and_stamp entry guard; SQL interval 备注 |
| v5→approved (3 建议) | D9 对齐 Slice F; 验收 claim/stamp; no-owner 测试期望 |

### Implementation Review (2 rounds, post-implementation)

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| 1 | P1 | GATEWAY_ALLOWED_ORIGINS 无运行时 enforcement | _is_allowed_origin() 用于 /auth/login + /ws |
| 2 | P1 | Telegram no-auth 误判 auth mode (principal_store 总是非 None) | no-auth 时传 principal_store=None |
| 3 | P2 | /auth/login 失败路径 500 (GatewayError 无 HTTP handler) | 注册 NeoMAGIError exception handler → 401/403/405/429 |
| 4 | P3 | allowed_origins whitespace 误判 | .strip() |
| 5 | P3 | 安全边界缺测试 | 10 个 test_auth_boundary.py 测试 |

## Commits

| Hash | 说明 |
|------|------|
| `0f794dc` | Gate 0: principals schema + PrincipalStore |
| `9ea6959` | Gate 1: JWT, login, WebSocket auth, identity propagation |
| `254bdaa` | Gate 2: Telegram binding, frontend login, network boundary |
| `f5ad43e` | Post-review fix: Origin enforcement, Telegram no-auth, HTTP errors |
| `4a28695` | Post-review fix: boundary tests + allowed_origins strip |
