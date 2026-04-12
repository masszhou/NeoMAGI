---
doc_id: 019d83a2-21a6-750f-81d1-7168cffee662
doc_id_format: uuidv7
doc_id_assigned_at: 2026-04-12T23:38:53+02:00
---
# P2-M3b 实现日志：Memory Ledger & Visibility Policy

> 日期：2026-04-12
> 计划：`dev_docs/plans/phase2/p2-m3b_memory-ledger-visibility-policy_2026-04-12.md`

## 实现总结

将 P2-M2d 的 DB append-only source ledger 接入 principal identity 与 visibility policy。memory 写入、检索、reindex、workspace projection、PromptBuilder daily notes 注入全路径具备可解释的身份与可见性语义。

### 新增文件 (2)

| 文件 | 说明 |
|------|------|
| `alembic/versions/a1c2d3e4f5g6_add_principal_visibility_to_memory.py` | Migration: ledger + memory_entries 新增 principal_id + visibility 列, CHECK 约束, 3 索引 |
| `tests/test_m3b_visibility.py` | 28 个 M3b 专属测试 (searcher SQL, prompt 3-way 等价, tool/flush/reindex 隔离) |

### 修改文件 (25)

| 文件 | 变更 |
|------|------|
| `src/memory/models.py` | MemoryEntry 增加 principal_id + visibility 列 + 2 索引 |
| `src/session/database.py` | `_add_principal_visibility_to_memory()` idempotent DDL (列+CHECK+索引) |
| `src/memory/ledger.py` | `append()` 新增 principal_id + visibility 参数; `get_current_view()` 全字段返回; `get_entries_for_parity()` 返回新字段 |
| `src/memory/writer.py` | `append_daily_note()` 新增 principal_id + visibility; visibility fail-closed 检查; workspace metadata 渲染 principal/visibility; 增量索引改由 ledger_written 驱动 (D13); `process_flush_candidates()` 透传 `candidate.principal_id` |
| `src/memory/contracts.py` | `ResolvedFlushCandidate.principal_id` 新字段 |
| `src/memory/indexer.py` | `index_entry_direct()` 新增 principal_id + visibility; `_parse_entry_metadata()` 返回 principal + visibility; `_parse_daily_entries()` 传播 principal_id + visibility 到 row; `reindex_from_ledger()` 从 ledger current view 重建; `reindex_all(scope_key, ledger=)` 支持 ledger-based + scope_key=None |
| `src/memory/searcher.py` | `search(principal_id=)` + `_build_search_sql()` WHERE principal + visibility 过滤 (D5 deny-by-default); `MemorySearchResult` 新增 principal_id + visibility |
| `src/memory/parity.py` | 比较新增 principal_id + visibility 维度; workspace scan 提取 principal + visibility |
| `src/tools/builtins/memory_append.py` | 从 `context.principal_id` 读取, 传递给 writer |
| `src/tools/builtins/memory_search.py` | 从 `context.principal_id` 读取, 传递给 searcher |
| `src/agent/message_flow.py` | **调用顺序修正**: principal_id 提取移到 _fetch_memory_recall() 之前; _build_system_prompt + _apply_compaction_result 透传 principal_id; _apply_compaction 传递到 try_compact |
| `src/agent/agent.py` | `_fetch_memory_recall(principal_id=)` 传递给 searcher; `_persist_flush_candidates(principal_id=)` 填充到 ResolvedFlushCandidate; `_try_compact(principal_id=)` 透传 |
| `src/agent/compaction_flow.py` | `try_compact` / `_finalize_compaction_result` / `_persist_flush_candidates` 全链路 principal_id |
| `src/agent/tool_concurrency.py` | `_handle_publish_flush()` 传递 `state.principal_id` |
| `src/agent/prompt_builder.py` | `build(principal_id=)` per-request; `_layer_workspace` / `_load_daily_notes` 透传; `_filter_entries()` 替代 `_filter_entries_by_scope()` — scope + principal + visibility 3-way 等价过滤 (D10) |
| `src/backend/cli.py` | `reindex` 命令 ledger-based + scope_key=None (全 scope 重建) |
| `scripts/restore.py` | ledger-based reindex (scope_key=None), 空 ledger fallback workspace |
| `design_docs/data_models/postgresql/memory_source_ledger.md` | 新列 + 新索引文档 |
| `design_docs/data_models/postgresql/memory_entries.md` | 新列文档 |
| `design_docs/data_models/postgresql/index.md` | 表描述更新 |
| `.complexity-baseline.json` | 刷新 baseline |
| `tests/test_cli.py` | MemoryLedgerWriter mock + ledger-mode scope_key=None 测试 |
| `tests/test_memory_search_tool.py` | search 调用断言加 principal_id=None |
| `tests/test_memory_parity.py` | ledger mock 数据加 principal_id + visibility |
| `tests/test_restore.py` | MemoryLedgerWriter mock patch (11 patches) |

### DB 变更

- `memory_source_ledger` 新增: `principal_id VARCHAR(36) NULL`, `visibility VARCHAR(32) NOT NULL DEFAULT 'private_to_principal'` + CHECK 约束 + `idx_memory_source_ledger_principal`
- `memory_entries` 新增: `principal_id VARCHAR(36) NULL`, `visibility VARCHAR(32) NOT NULL DEFAULT 'private_to_principal'` + `idx_memory_entries_principal` + `idx_memory_entries_visibility`

### 关键设计决策

- **D5 三路等价 (searcher / PromptBuilder / auto recall)**: 所有 memory 消费路径执行相同 principal + visibility policy — 有 principal_id 的请求看自己的 + legacy NULL; anonymous 只看 NULL; shared_in_space deny-by-default
- **D13 增量索引改由 ledger_written 驱动**: projection 失败但 ledger 成功时, memory_entries 仍有条目可搜索
- **Workspace projection principal 渲染**: `principal_id=None` 时省略 `principal:` 字段 (不渲染 "principal: None"), 避免 PromptBuilder 误判为 principal-owned
- **Visibility fail-closed**: `shared_in_space` 在 writer 层拦截, unknown visibility 拒绝
- **Ledger reindex scope_key=None**: restore 和 CLI reindex 从 ledger 重建时使用全 scope, 不丢弃非 main 条目

## Review Findings & Fixes

### Plan Review (pre-implementation)

计划在实施前已对齐 P2-M3a 实际实现 (commit 7d3221a):
- ToolContext.principal_id / execute_tool / tool_concurrency 传播标注为 M3a 已完成
- D3 收缩为消费 M3a 能力, D12 聚焦 flush 旁路
- Slice D 拆分为 "M3a 已提供" + "M3b 剩余"
- PrincipalStore.resolve_principal_id() 修正为 "M3b 不调用"
- AUTH_PASSWORD → AUTH_PASSWORD_HASH
- D11 明确调用顺序修正

### Implementation Review (2 rounds, post-implementation)

**R1 (3 findings)**:

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| 1 | P2 | `_parse_daily_entries` 丢弃 principal_id + visibility → workspace reindex 变匿名可见 | row dict 新增 principal_id + visibility 从 `_parse_entry_metadata` 传播 |
| 2 | P2 | restore 只重建 main scope → 非 main ledger 条目丢失 | `scope_key=None` 传给 `reindex_all(ledger=)`; `reindex_all` 签名改为 `scope_key: str | None = "main"` |
| 3 | P3 | ensure_schema 漏建 memory_entries 的 2 个索引 | `_add_principal_visibility_to_memory()` 追加 `CREATE INDEX IF NOT EXISTS` |

**R2 (2 findings)**:

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| 1 | P2 | CLI reindex ledger 模式传 `scope_key="main"` 丢弃非 main scope (同 R1#2) | `scope_key=None` + `test_ledger_mode_rebuilds_all_scopes` |
| 2 | — | `test_m3b_visibility.py` ruff 未通过 (unused imports, sort) | `ruff check --fix` 清理 |

## Commits

| Hash | 说明 |
|------|------|
| `7d3221a` | Plan alignment: M3b baseline 对齐 M3a 实际实现 |
| `e1b555f` | Gate 0+1+2: Slice A-G 主实现 (26 files, +665/-81) |
| `41afe8b` | Post-review R1: workspace reindex fix, restore scope, indexes, 27 tests |
| `2dc5e4f` | Post-review R2: CLI reindex scope fix, ruff clean, 1 test |

## 测试

- 新增 **28 tests** in `tests/test_m3b_visibility.py`:
  - TestSearcherBuildSql (3): authenticated/anonymous/shared_in_space SQL WHERE
  - TestPromptFilterEntries (10): own/cross-principal/anonymous/legacy/shared_in_space/unknown/shareable_summary/daily_notes 端到端
  - TestMemoryAppendPrincipal (2): principal_id 写入 + anonymous 不渲染
  - TestMemorySearchPrincipal (2): principal_id 传递 + None 传递
  - TestFlushPrincipal (2): flush candidate principal + anonymous
  - TestWriterVisibility (3): shared_in_space 拒绝 / unknown 拒绝 / shareable_summary 接受
  - TestParseEntryMetadata (3): 含 principal+visibility / 缺失 / 非 metadata 行
  - TestWorkspaceReindexPreservesVisibility (2): P2 fix 回归验证
  - TestReindexCli (1): ledger-mode scope_key=None 验证
- 现有测试适配: test_memory_search_tool (principal_id=None 断言), test_memory_parity (mock 加新字段), test_restore (11 patches), test_cli (ledger mock)
- 全量回归: **1851 unit passed**, 0 failed
