---
doc_id: 019d6808-256a-73d4-9331-ce49e216bf07
doc_id_format: uuidv7
doc_id_assigned_at: 2026-04-07T15:00:57+02:00
---
# P2-M1 Post Works P3: Atomic Coding Tools (Stage A/B) — 验收通过

- Date: 2026-04-07
- Plan: `dev_docs/plans/phase2/p2-m1-post-works-p3_atomic-coding-tools_2026-04-06.md`
- Status: **accepted**

## 交付摘要

3 commits, 24 文件变更 (含 8 新文件), 1615 backend tests + 41 frontend tests passed.

| Commit | 内容 |
|--------|------|
| `77f536f` | feat(tools): implement atomic coding tools (P3 Stage A/B) |
| `3a1650f` | fix(tools): address P1/P2 review findings (round 1) |
| `695e6e7` | fix(tools): address P1/P2 review round 2 |

## 计划验收项对照

| 验收项 | 状态 |
|--------|------|
| coding 路径下可用 `glob` / `grep` / `read_file` | pass |
| coding 路径下可用 `write_file` / `edit_file` | pass |
| `chat_safe` 默认不暴露 coding-only tools，hallucinated call 被执行闸门拒绝 | pass |
| workspace boundary 覆盖 `glob` / `grep` / `read_file` / `write_file` / `edit_file` | pass |
| `read_file` 支持 line range 与 output truncation，记录 read state | pass |
| `edit_file` 对 0 次匹配和多次匹配都有负向测试 | pass |
| `edit_file` 对 `replace_all=true` 多处匹配成功和 0 次匹配失败都有测试 | pass |
| `write_file` 对未显式 overwrite 的既有文件有负向测试 | pass |
| `write_file` 对 partial read 后尝试 full-file update 有负向测试 | pass |
| `write_file` replace 与 `edit_file` 对未读过 / stale read state 都有负向测试 | pass |
| `write_file` 成功后返回 `operation=create\|update` | pass |
| `read_file.is_concurrency_safe` 保持 `False` | pass |
| Stage C (bash) 未纳入，保留为 follow-up | pass |

## Review Findings 及修复

共 3 轮 review：

**Round 1** — 4 findings:

1. **[P1] write_file `overwrite: "false"` 绕过检查** — 新增 `coerce_bool()` 严格布尔转换，仅 `True` 和 `"true"` 为真
2. **[P2] edit_file `replace_all: "false"` 全量替换** — 同上 `coerce_bool()`
3. **[P2] 前端缺 `session.set_mode` 响应路由** — `SessionViewState` 增加 `mode` + `pendingModeRequestId`，`ChatState` 增加 `setMode` action，`_handleServerMessage` 增加 mode response 路由
4. **[P2] glob/grep 全量排序后截断** — 改为惰性迭代 + 有界收集 `max_results+1` 后再排序

**Round 2** — 3 findings:

1. **[P1] chat.ts TS2352 构建失败** — `ResponseMessage.data` 改为 `Record<string, unknown>`，mode response 用 `"mode" in message.data` narrowing
2. **[P1] 复杂度门禁失败 (9 regressions)** — 拆分 `write_file.execute`→3 函数、`edit_file.execute`→4 函数、`grep._grep_sync`→3 函数；`coerce_bool` + `resolve_search_dir` 提取到 `read_state.py`；`chat.ts` 808→796 行
3. **[P2] 无 UI 调用 `setMode`** — 新增 `ModeToggle.tsx` 组件挂载在 `ChatPage` header

**Round 3** — 0 findings，验收通过。

## 关键实现

### Slice A: Coding Entry (ADR 0058)

- `SessionManager.get_mode()`: 移除 M1.5 guardrail，尊重 DB 中合法 per-session `coding` 值
- `SessionManager.set_mode()`: 新增 per-session mode 写入，pg upsert
- `session.set_mode` WebSocket RPC: 新方法 + `SessionSetModeParams` / `SessionModeData` / `RPCSessionModeResponse` 协议类型
- `_handle_rpc_message`: 重构为 dict-based dispatch (消除 nesting regression)
- `SessionSettings.default_mode`: 继续只接受 `chat_safe` (ADR 0025/0058)
- `ModeToggle.tsx`: 最小 UI 入口，显式切换 session mode

### Slice B1: read_file Upgrade

- `ReadFileTool`: 支持 `file_path` (绝对路径, preferred) + `path` (相对路径, V1 alias)
- `offset` / `limit` 参数，输出截断 (`_DEFAULT_MAX_LINES=2000`)
- 返回 `file_path` (canonical) + `relative_path` + `total_lines` + `truncated` + line range 元数据
- Newline-safe I/O: `read_bytes()` + explicit UTF-8 decode (不使用 Python universal newline mode)
- 非 UTF-8 文件返回 `ENCODING_ERROR`

### Read State Infrastructure (`src/tools/read_state.py`)

- `ReadState` / `ReadScope`: frozen dataclass，记录 `session_id` / `file_path` / `mtime_ns` / `size` / `read_scope` / `truncated` / `read_at`
- `ReadStateStore`: 进程内 map keyed by `(session_id, file_path)`，V1 不持久化
- `check_staleness()`: `mtime_ns + size` 比对
- `is_full_read()`: `offset=0 and truncated=False`
- `validate_workspace_path()`: 共享 path 验证 (resolve + boundary check + symlink escape)
- `coerce_bool()`: 共享严格布尔转换
- `resolve_search_dir()`: 共享子目录解析

### Slice B2: glob + grep

- `GlobTool`: `asyncio.to_thread` 非阻塞，`is_concurrency_safe=True`，有界收集 + 排序
- `GrepTool`: regex + glob filter + case_insensitive，`asyncio.to_thread`，`is_concurrency_safe=True`
- `_grep_file()` / `_is_searchable()`: 拆分为独立函数 (complexity compliance)

### Slice C: write_file + edit_file

- `WriteFileTool`: create-only 默认，`overwrite=true` 才允许 replace；read-before-write + staleness check + full-read enforcement
- `EditFileTool`: `old_string→new_string` 精确匹配，unique match 或 `replace_all=true`；read-before-edit + staleness check
- `_check_overwrite_preconditions()` / `_match_and_replace()`: 拆分为独立函数

### Tool Registration

- `builtins/__init__.py`: 注册 `GlobTool`, `GrepTool`, `WriteFileTool`, `EditFileTool`

## Evidence

- Commits: `77f536f`, `3a1650f`, `695e6e7`
- Backend tests: 1615 passed (62 new: `test_read_file_security` 22 + `test_glob_grep` 20 + `test_write_edit_file` 30 中含 4 boolean coercion)
- Frontend tests: 41 passed
- Frontend build: `pnpm build` passed
- Lint: `ruff check` passed (P3 变更文件无 regression)
- Complexity guard: P3 变更文件无 block-level regression (3 个既有 regression 在 cli.py / chat.test.ts / test_skill_store_pg.py)

## 残余风险

- `ModeToggle` / `setMode` UI 路径主要靠 build + 现有 frontend tests 间接覆盖，无专用 store/UI 测试 — 不阻塞合并
- Stage C (`bash`) 保留为独立 follow-up，按计划在 Stage A/B 稳定后再评估
