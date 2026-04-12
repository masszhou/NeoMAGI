---
doc_id: 019d7de4-0eae-769b-8e59-71e1351365ad
doc_id_format: uuidv7
doc_id_assigned_at: 2026-04-11T20:53:11+02:00
---
# P2-M2d 实现计划：Memory Source Ledger Prep for P2-M3

> 状态：approved
> 日期：2026-04-11
> 输入：`design_docs/phase2/p2_m2_post_self_evolution_staged_plan.md` Section 4
> 架构基础：ADR 0060 (Memory Source Ledger DB with Workspace Projections)
> 前置完成：P2-M2c (ProcedureSpec Governance Adapter)

## 0. 目标

按 ADR 0060 迁移步骤 1-2，为 P2-M3 (Identity / Principal / Visibility / Memory Policy) 准备最薄的 DB memory source ledger 写入地基。

回答的问题：**后续 memory visibility policy 的事实落点在哪里？**

完成后：
- 新 memory 写入同时出现在 DB ledger 与 workspace daily note projection
- Ledger 使用 append-only 语义，不静默覆盖历史
- Parity check 能报告 DB ledger 与 workspace projection 之间的不一致
- 所有现有 memory recall / search 行为保持完全兼容

## 1. 当前基线

| 组件 | 状态 |
|------|------|
| `MemoryWriter` (`src/memory/writer.py`) | 写入 `workspace/memory/YYYY-MM-DD.md`；生成 UUIDv7 entry_id；best-effort 增量 index 到 `memory_entries` |
| `MemoryIndexer` (`src/memory/indexer.py`) | delete-reinsert 策略；从 workspace files 扫描重建 `memory_entries` |
| `MemorySearcher` (`src/memory/searcher.py`) | tsvector + ts_rank 查询 `memory_entries`；scope_key 强制过滤 |
| `MemoryAppendTool` (`src/tools/builtins/memory_append.py`) | 调用 `MemoryWriter.append_daily_note()`；scope_key/source_session_id 从 context 获取 |
| `memory_entries` 表 | 检索 projection（非真源）；13 列 + GIN index + search trigger |
| `process_flush_candidates()` | 批量写入 compaction_flush 条目到 daily note |
| `doctor D2` (`src/infra/doctor.py`) | 比较 memory_entries 行数 vs workspace 文件条目数 |
| `doctor DD3` | 逐文件对比 workspace → memory_entries 一致性 |
| 真源位置 | workspace Markdown 文件（ADR 0060 将其迁移为 DB ledger） |

## 2. 核心决策

### D1：Ledger 表设计 — 极薄 append-only，不承载检索结构

ADR 0060 要求 "DB source ledger 必须保持极薄"。新表 `memory_source_ledger` 只记录：
- 独立事件 identity (`event_id` UUIDv7)
- 指向 memory 条目的 identity (`entry_id` UUIDv7)
- provenance (`source`, `source_session_id`)
- scope (`scope_key`)
- 正文 (`content`)
- 最小治理元数据 (`event_type`, `created_at`)

**event_id 与 entry_id 分离**：每行有自己的 `event_id`（UUIDv7 PK），`entry_id` 标识被操作的 memory 条目。V1 只有 `append` event，每个 `entry_id` 只会出现一次；但后续 `correction` / `retraction` / `contested` 等事件需要对同一 `entry_id` 追加多条记录。因此 `entry_id` 只设 partial unique index（`WHERE event_type = 'append'`）而非全表 UNIQUE，避免锁死未来修正/撤回路径。

**不放入 ledger**：title、tags、confidence、search_vector、embedding — 这些是检索 projection 的关注点，由 `memory_entries` 继续承载。

### D2：Event type 语义 — V1 只做 `append`

ADR 0060 定义了 append-only 语义：普通新增、修正、撤回、争议标记都追加事件。但 P2-M2d 的 scope 只做写入预备，不实现修正/撤回/争议。

V1 `event_type` 枚举：
- `append` — 新增条目（memory_append + compaction_flush 统一使用）

后续 P2-M3+ 扩展：`correction`、`retraction`、`contested`、`hard_erase`（合规删除用 tombstone）。

### D3：写入顺序 — DB ledger truth first

系统尚未上线，P2-M2d 采用 clean-start baseline（见 D7），没有必要保留"workspace 仍是用户可见写入确认、ledger 失败不阻断"的过渡语义。ADR 0060 已接受 DB ledger 为 truth，从第一天就按 truth-first 写入，避免"用户看到写入成功但 ledger 缺失"的不一致。

写入顺序：
1. 写入 DB ledger（truth）
2. 写入 workspace daily note projection
3. 增量 index 到 memory_entries

**失败语义**：
- DB ledger 写入失败 → 整体失败，不写入成功确认
- Workspace projection 写入失败 → warning 日志，不阻断（truth 已持久化，projection 可 rerender）
- memory_entries index 失败 → warning 日志，可 reindex 修复（现有行为不变）

### D4：Parity check — ID + content + metadata 比对，报告差异，不自动修复

ADR 0060 明确 "direct file edits 不能绕过审计成为 truth"。仅比较 `entry_id` 集合会将最危险的一类 projection drift（手工编辑 content/scope/source）误报为 consistent。因此 parity check 分两层：

1. **ID-level**：扫描 workspace daily note 文件提取 `entry_id` 集合，与 DB ledger 对比 → 报告 only_in_workspace / only_in_ledger
2. **Content-level**：对双方都有的 `entry_id`，比较 `content`、`scope_key`、`source`、`source_session_id` → 报告 content_mismatch / metadata_mismatch

集成到 `doctor` 体系（新增 D5 check）。不做自动修复、不做补录命令。

**验收前提**：P2-M2d parity 验收基于 clean-start memory state（见 D7）。它用于验证 P2-M2d 生效后的新双写是否一致，不负责解释或迁移 P2-M2d 之前的本地开发 daily notes。若开发者在非 clean workspace 上运行 doctor D5，旧 daily notes 可能产生 only_in_workspace 噪音；这不属于 P2-M2d 的产品验收范围，正式验收应使用临时 workspace 或先隔离旧 dev artifacts。

### D5：AgentLoop flush path 必须覆盖双写

当前 `AgentLoop.__init__()` (`src/agent/agent.py:93`) 自建 `MemoryWriter(workspace_dir, memory_settings)`，不经过 gateway wiring，因此 `process_flush_candidates()` 的 compaction_flush 写入不会进入 ledger。

解决方案：`AgentLoop` 改为接收外部构造好的 `MemoryWriter` 实例（已注入 ledger），而非内部 `self._memory_writer = MemoryWriter(...)`。gateway 层构造单一 `MemoryWriter` 实例，同时传给 `MemoryAppendTool` 和 `AgentLoop`。

### D6：Backup/restore 必须覆盖新 truth 表

ADR 0060 后 `memory_source_ledger` 是 memory truth 的落点。`scripts/backup.py` 的 `TRUTH_TABLES` 当前只包含 sessions / messages / soul_versions / budget_state / budget_reservations，显式排除 `memory_entries`（derived projection）。新 ledger 表必须加入 `TRUTH_TABLES`，否则备份恢复会丢失 DB memory truth。

### D7：Clean-start ledger baseline — 不做生产历史迁移

NeoMAGI 尚未上线，不存在需要保留的生产 memory truth 迁移。P2-M2d 不承担历史 workspace daily notes 到 ledger 的全量迁移。

P2-M2d 生效后的事实口径：
- DB `memory_source_ledger` 是新 memory truth。
- `workspace/memory/*.md` 是从新写入同步生成的 projection/export。
- P2-M2d 验收环境必须使用 clean-start memory state：空 ledger + 空 daily note projection，或使用一次性测试 workspace。
- 已存在的本地开发 daily notes 只视为 pre-ledger dev artifact，不作为 P2-M2d parity 验收输入。

## 3. 实现切片

### Slice A：DB Schema — `memory_source_ledger` 表

**新增 DB 表**（alembic migration + `ensure_schema()` idempotent DDL）：

`memory_source_ledger`（append-only）：
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `event_id` | VARCHAR(36) | PK | 事件 identity（UUIDv7），每行独立 |
| `entry_id` | VARCHAR(36) | NOT NULL | 被操作的 memory 条目 identity（UUIDv7） |
| `event_type` | VARCHAR(16) | NOT NULL, DEFAULT 'append' | V1 只有 `append`；后续扩展 correction/retraction/contested |
| `scope_key` | VARCHAR(128) | NOT NULL, DEFAULT 'main' | 检索可见性 scope (ADR 0034) |
| `source` | VARCHAR(32) | NOT NULL | `user` / `compaction_flush` |
| `source_session_id` | VARCHAR(256) | NULL | 来源 session provenance |
| `content` | TEXT | NOT NULL | 原文正文 |
| `metadata` | JSONB | NOT NULL, DEFAULT '{}' | 扩展元数据预留（V1 不使用） |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 写入时间 |

**索引**：
- `idx_memory_source_ledger_entry_id` on `entry_id`（非 UNIQUE — 同一 entry 可有多条事件）
- `idx_memory_source_ledger_scope` on `scope_key`
- `idx_memory_source_ledger_created_at` on `created_at`（parity check 按时间范围扫描）

**Partial unique index（幂等防护）**：
```sql
CREATE UNIQUE INDEX uq_memory_source_ledger_entry_append
  ON memory_source_ledger (entry_id)
  WHERE event_type = 'append';
```
同一 `entry_id` 只允许一条 `append` 事件（防重复写入）；后续 `correction` / `retraction` 等事件类型不受此约束，可对同一 `entry_id` 追加多条记录。

**约束**：
- 不设全表 UNIQUE on `entry_id`（会阻塞未来 append-only event 语义）
- 不设外键到 `memory_entries`（两者是独立层：truth vs retrieval projection）

**新增文件**：
- `alembic/versions/<hash>_create_memory_source_ledger.py`
- `src/session/database.py` 中新增 `_create_memory_source_ledger_table()` + `ensure_schema()` 调用

### Slice B：Ledger Writer API — `MemoryLedgerWriter`

**新增文件**：`src/memory/ledger.py`

```python
class MemoryLedgerWriter:
    """Append-only writer for memory source ledger (ADR 0060)."""

    def __init__(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
    ) -> None: ...

    async def append(
        self,
        *,
        entry_id: str,
        content: str,
        scope_key: str = "main",
        source: str = "user",
        source_session_id: str | None = None,
        metadata: dict | None = None,
    ) -> bool:
        """Append a single 'append' event to the source ledger.

        Generates event_id (UUIDv7) internally.
        Uses INSERT ... ON CONFLICT (entry_id) WHERE event_type='append' DO NOTHING.

        Returns: True if inserted, False if idempotent no-op (duplicate entry_id append).
        Raises: LedgerWriteError on DB failure.
        """

    async def count(self, *, scope_key: str | None = None) -> int:
        """Count ledger entries, optionally filtered by scope_key."""

    async def list_entry_ids(
        self,
        *,
        scope_key: str | None = None,
        since: datetime | None = None,
    ) -> list[str]:
        """List distinct entry_ids with event_type='append' in ledger, for parity check."""

    async def get_entries_for_parity(
        self,
        *,
        scope_key: str | None = None,
    ) -> dict[str, dict]:
        """Return {entry_id: {content, scope_key, source, source_session_id}} for parity check.

        Only returns 'append' events (V1 primary records).
        """
```

**设计要点**：
- 纯 raw SQL（与 SkillStore / ProcedureSpecGovernanceStore 一致），不用 ORM model
- `append()` 使用 `INSERT ... ON CONFLICT (entry_id) WHERE event_type = 'append' DO NOTHING` + `RETURNING event_id` 实现幂等；`RETURNING` 无结果 → 返回 `False`（重复），有结果 → 返回 `True`（新写入）
- `event_id` (UUIDv7) 由 `append()` 内部生成，不暴露给调用方
- `get_entries_for_parity()` 返回 content-level 比对所需的完整字段
- 失败抛 `LedgerWriteError`（新增到 `src/infra/errors.py`）

### Slice C：双写集成 — `MemoryWriter` 改造 + `AgentLoop` writer 统一

**修改文件**：`src/memory/writer.py`、`src/agent/agent.py`、`src/gateway/app.py`

#### C1: MemoryWriter 双模式写入

`MemoryWriter` 有两种运行模式，由 `self._ledger` 是否注入决定：

| | **Ledger-wired 模式**（生产） | **No-ledger fallback 模式**（测试/旧路径） |
|---|---|---|
| Truth 落点 | DB ledger | Workspace daily note |
| Projection 语义 | best-effort（失败 warning） | mandatory（失败 raise `MemoryWriteError`） |
| Size limit | projection 超限 → skip + warning | size limit → raise `MemoryWriteError`（现有行为） |
| 返回值 | `MemoryWriteResult` | `MemoryWriteResult`（`ledger_written=False`） |

改造点：
1. `MemoryWriter.__init__()` 新增可选参数 `ledger: MemoryLedgerWriter | None = None`
2. `append_daily_note()` 返回值从 `Path` 改为 `MemoryWriteResult`
3. Ledger-wired 时：ledger → projection (best-effort) → incremental index
4. No-ledger fallback 时：projection (mandatory, raise on fail) → incremental index — **保留现有异常语义**
5. `process_flush_candidates()` 计数规则更新（见下）

**返回值契约**：

```python
@dataclass(frozen=True)
class MemoryWriteResult:
    """Result of append_daily_note(), reflecting write mode semantics."""
    entry_id: str
    ledger_written: bool       # True only when ledger INSERT succeeded (not idempotent no-op)
    projection_written: bool   # True when daily note file written
    projection_path: Path | None  # None when projection skipped/failed
```

`MemoryAppendTool.execute()` 返回结构更新（向后兼容 + 新增字段）：

```python
# 始终返回的字段
{
    "ok": True,
    "entry_id": result.entry_id,
    "ledger_written": result.ledger_written,
    "projection_written": result.projection_written,
    "message": "...",  # 见下
}
# 仅当 projection 成功时附加（兼容现有消费方）
if result.projection_path:
    response["path"] = str(result.projection_path)
```

`message` 文案：
- `ledger_written=True, projection_written=True` → `"Memory saved (entry_id: {entry_id})"`
- `ledger_written=True, projection_written=False` → `"Memory saved to DB ledger (entry_id: {entry_id}); workspace projection pending"`
- `ledger_written=False, projection_written=True`（no-ledger fallback）→ `"Memory saved to {path.name}"`

```python
async def append_daily_note(self, text, *, scope_key, source, source_session_id, target_date):
    entry_id = str(_uuid7())
    # ... existing: format entry ...

    if self._ledger:
        # ── Ledger-wired mode: truth-first ──
        # 1. DB ledger truth (mandatory)
        ledger_written = await self._ledger.append(
            entry_id=entry_id, content=text, scope_key=scope_key,
            source=source, source_session_id=source_session_id,
        )  # LedgerWriteError propagates; returns bool (True=new, False=idempotent)

        # 2. Idempotent no-op: ledger already has this entry_id → skip projection
        if not ledger_written:
            return MemoryWriteResult(
                entry_id=entry_id, ledger_written=False,
                projection_written=False, projection_path=None,
            )

        # 3. Workspace projection (best-effort)
        projection_written = self._try_write_projection(filepath, entry, entry_bytes)
    else:
        # ── No-ledger fallback mode: projection mandatory ──
        ledger_written = False
        self._check_size_limit(filepath, entry_bytes, filename)  # raises MemoryWriteError
        with filepath.open("a", encoding="utf-8") as f:
            f.write(entry)
        projection_written = True

    # 3. Incremental index (best-effort, both modes)
    if projection_written:
        await self._try_incremental_index(...)

    return MemoryWriteResult(
        entry_id=entry_id,
        ledger_written=ledger_written,
        projection_written=projection_written,
        projection_path=filepath if projection_written else None,
    )

def _try_write_projection(self, filepath, entry, entry_bytes) -> bool:
    """Best-effort workspace projection write. Only used in ledger-wired mode.
    Never raises. Size limit exceeded → skip + warning.
    """
    try:
        current_size = filepath.stat().st_size if filepath.exists() else 0
        if current_size + len(entry_bytes) > self._settings.max_daily_note_bytes:
            logger.warning(
                "daily_note_projection_size_limit",
                path=str(filepath), current_size=current_size,
                entry_size=len(entry_bytes),
                max_bytes=self._settings.max_daily_note_bytes,
            )
            return False
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with filepath.open("a", encoding="utf-8") as f:
            f.write(entry)
        return True
    except OSError:
        logger.warning("daily_note_projection_write_failed", path=str(filepath))
        return False
```

**`_check_size_limit()` 保留给 no-ledger fallback**：在 ledger-wired 模式下不调用（size check 内化到 `_try_write_projection()`）；在 no-ledger fallback 模式下保留现有 raise `MemoryWriteError` 语义，确保测试和旧路径行为不变。

**`process_flush_candidates()` 计数规则更新**：
- 现有逻辑：没有异常 → `written += 1`；`MemoryWriteError` → `break`
- 新逻辑：`result.ledger_written or result.projection_written` → `written += 1`；`LedgerWriteError` → `break`（等同于 DB 不可用）；no-ledger fallback 时 `MemoryWriteError` 仍 `break`（保留现有行为）

#### C2: AgentLoop 改为接收外部 MemoryWriter

**问题**：当前 `AgentLoop.__init__()` (`src/agent/agent.py:93`) 自建 `MemoryWriter(workspace_dir, memory_settings)` 不经过 gateway wiring。这意味着 `process_flush_candidates()` 的 compaction_flush 写入不会进入 ledger，只有 `memory_append` tool 路径（经 gateway wiring 的 writer）会双写。

**修复**：`AgentLoop.__init__()` 改为可选接收外部 `memory_writer: MemoryWriter | None` 参数。有传入 → 直接使用；无传入 → 保留现有内部构造作为 fallback（向后兼容测试场景）。

```python
# src/agent/agent.py
class AgentLoop:
    def __init__(self, ..., memory_writer: MemoryWriter | None = None, ...):
        ...
        if memory_writer is not None:
            self._memory_writer = memory_writer
        elif memory_settings is not None:
            self._memory_writer = MemoryWriter(workspace_dir, memory_settings)
```

**Gateway wiring**：`_build_memory_and_tools()` 中构造单一 `MemoryWriter` 实例（含 indexer + ledger），同时传给 `MemoryAppendTool` 和 `AgentLoop`。

### Slice D：Parity Check — `MemoryParityChecker`（ID + content + metadata）

**新增文件**：`src/memory/parity.py`

```python
@dataclass(frozen=True)
class ParityReport:
    """Comparison result between DB ledger and workspace files."""
    ledger_count: int
    workspace_count: int
    only_in_ledger: list[str]      # entry_ids
    only_in_workspace: list[str]   # entry_ids
    matched: int
    content_mismatch: list[str]    # entry_ids where content differs
    metadata_mismatch: list[str]   # entry_ids where scope_key/source/source_session_id differs

    @property
    def is_consistent(self) -> bool:
        return (
            not self.only_in_ledger
            and not self.only_in_workspace
            and not self.content_mismatch
            and not self.metadata_mismatch
        )


class MemoryParityChecker:
    """Compare memory source ledger with workspace daily note files.

    Two-layer comparison per D4:
    1. ID-level: entry_id set difference
    2. Content-level: for matched entry_ids, compare content + scope_key + source + source_session_id
    """

    def __init__(
        self,
        ledger: MemoryLedgerWriter,
        workspace_path: Path,
    ) -> None: ...

    async def check(self, *, scope_key: str | None = None) -> ParityReport:
        """Run parity comparison. Read-only, no side effects."""
```

**实现**：
1. 从 ledger 调用 `get_entries_for_parity()` → `dict[entry_id, {content, scope_key, source, source_session_id}]`
2. 扫描 `workspace/memory/*.md`，用 `MemoryIndexer._parse_entry_metadata()` + `_extract_entry_text()` 提取 entry_id → `{content, scope, source, source_session_id}` 的 dict
3. ID-level 集合差异 → `only_in_ledger` / `only_in_workspace`
4. 对 matched entry_ids：逐条比较 content → `content_mismatch`；比较 scope_key + source + source_session_id → `metadata_mismatch`
5. 跳过无 `entry_id` 的旧条目（ADR 0053 之前写入），不报告 false positive

**Parser 扩展**：当前 `MemoryIndexer._parse_entry_metadata()` 返回 `{entry_id, scope, source_session_id}`，**不含 `source` 字段**（daily note 格式中写入 `source: user` / `source: compaction_flush`）。需要扩展此方法，新增 `source` key 的正则提取（`r"source:\s*(\S+)"`），并补充 `tests/test_memory_indexer.py` 的对应用例。Parity checker 复用扩展后的 parser，不单独实现。

`_parse_entry_metadata()` 和 `_extract_entry_text()` 已经是 `@staticmethod`，无需改签名。

### Slice E：Doctor 集成 — 新增 D5 check

**修改文件**：`src/infra/doctor.py`

新增 `D5: memory ledger parity` 检查：
- 调用 `MemoryParityChecker.check()`
- `is_consistent` → OK
- 差异 > 0 → WARN（附带 only_in_ledger / only_in_workspace / content_mismatch / metadata_mismatch 数量）
- Ledger 表不存在或查询失败 → OK，evidence 说明 `"ledger table not present (P2-M2d not initialized)"`（兼容旧环境的非故障状态，不用 WARN/FAIL；`CheckStatus` 无 SKIP 枚举值）

### Slice F：Wiring + Backup/Restore + 数据模型文档

#### F1: Gateway wiring

**修改文件**：`src/gateway/app.py`

```python
# 在 _build_memory_and_tools() 中：
from src.memory.ledger import MemoryLedgerWriter

memory_ledger = MemoryLedgerWriter(db_session_factory)
memory_writer = MemoryWriter(
    settings.workspace_dir, settings.memory,
    indexer=memory_indexer, ledger=memory_ledger,
)
# memory_writer 同时传给 MemoryAppendTool 和 AgentLoop（单一实例）
```

`MemoryParityChecker` 在 doctor 调用路径中按需构造，不常驻 wiring。

#### F2: Backup/Restore

**修改文件**：`scripts/backup.py`、`scripts/restore.py`

`scripts/backup.py`:
- `TRUTH_TABLES` 新增 `"neomagi.memory_source_ledger"`

`scripts/restore.py`:
- 恢复序列已有 `pg_restore → ensure_schema → ...` 流程，新表通过 `pg_restore` 自动覆盖
- 新增轻量 SQL check：restore 完成后查询 `memory_source_ledger` 表是否存在，存在则 log 行数（不阻断 restore 流程，仅作为恢复确认）

#### F3: 数据模型文档

**新增文件**：`design_docs/data_models/postgresql/memory_source_ledger.md`
**修改文件**：`design_docs/data_models/postgresql/index.md`

逐表文档内容：表名、列定义、索引、partial unique index、ADR 引用、与 `memory_entries` 的关系说明。

### Slice G：测试

测试文件路径按仓库现有平铺结构（`tests/test_*.py`）。

**单元测试（mock session factory）** — `tests/test_memory_ledger.py`：
- `test_append_creates_entry` — 写入后 count=1，list_entry_ids 包含该 id
- `test_append_returns_true` — 首次写入 → `True`
- `test_append_idempotent_returns_false` — 同一 entry_id 写入两次 → 第二次返回 `False`，count=1
- `test_append_different_scopes` — 不同 scope_key 的条目各自独立
- `test_count_with_scope_filter` — scope_key 过滤正确
- `test_list_entry_ids_since` — since 时间过滤
- `test_get_entries_for_parity` — 返回 entry_id → {content, scope_key, source, source_session_id} dict

**单元测试** — `tests/test_memory_parity.py`：
- `test_consistent_state` — ledger 与 workspace ID + content 完全一致 → `is_consistent=True`
- `test_only_in_workspace` — workspace 有 ledger 没有 → 报告
- `test_only_in_ledger` — ledger 有 workspace 没有 → 报告
- `test_empty_both` — 双方都为空 → consistent
- `test_content_mismatch` — 同一 entry_id 的 content 不同 → `content_mismatch` 非空，`is_consistent=False`
- `test_metadata_mismatch` — 同一 entry_id 的 scope_key/source 不同 → `metadata_mismatch` 非空
- `test_skips_entries_without_entry_id` — 旧条目（无 entry_id）不报告 false positive

**Parser 扩展测试** — 在 `tests/test_memory_indexer.py` 中新增用例：
- `test_parse_entry_metadata_extracts_source` — `source: user` 和 `source: compaction_flush` 正确提取
- `test_parse_entry_metadata_missing_source` — 缺少 source 字段 → 返回 None

**双写集成测试** — 在 `tests/test_memory_writer.py` 中新增用例：
- `test_ledger_wired_writes_to_ledger_then_file` — result.ledger_written=True, projection_written=True
- `test_ledger_wired_ledger_failure_blocks` — ledger 抛 LedgerWriteError → 整体失败，daily note 不写入
- `test_ledger_wired_projection_failure_does_not_block` — projection 写入失败 → result.ledger_written=True, projection_written=False, warning 日志
- `test_ledger_wired_projection_size_limit_skip` — projection 超限 → ledger 写入成功，projection 跳过 + warning
- `test_ledger_wired_idempotent_noop` — duplicate entry_id → result.ledger_written=False, projection 不写入
- `test_no_ledger_fallback_mandatory_projection` — ledger=None → result.ledger_written=False, projection 正常写入
- `test_no_ledger_fallback_size_limit_raises` — ledger=None + 超限 → raise MemoryWriteError（保留旧行为）
- `test_flush_candidates_ledger_wired` — process_flush_candidates 触发 ledger 写入，计数基于 ledger_written or projection_written
- `test_flush_candidates_no_ledger_fallback` — fallback 模式下计数基于 projection 写入，MemoryWriteError → break
- `test_memory_append_tool_message_ledger_only` — ledger 成功 + projection 失败 → 用户消息包含 "DB ledger"
- `test_memory_append_tool_message_fallback` — no-ledger → 用户消息包含 path.name（现有行为）

**AgentLoop wiring 测试** — 在 `tests/test_agent_flush_persist.py` 中新增用例：
- `test_flush_uses_injected_writer_with_ledger` — 传入含 ledger 的 writer → flush 写入 ledger

**Doctor 测试** — 在 `tests/test_doctor.py` 中新增用例：
- `test_d5_consistent` — mock 一致 → pass
- `test_d5_discrepancy` — mock 不一致 → warn（含 content_mismatch / metadata_mismatch 数量）
- `test_d5_no_ledger_table` — 表不存在 → skip

**Backup/Restore 测试**：
- 在 `tests/test_backup.py` 中新增：`test_truth_tables_includes_memory_source_ledger`
- 在 `tests/test_restore.py` 中新增：`test_restore_checks_memory_source_ledger` — restore 流程包含 ledger 表存在 + 行数确认

**现有测试迁移**（返回值从 `Path` → `MemoryWriteResult`）：
- `tests/test_memory_writer.py`：所有使用 `path = await writer.append_daily_note(...)` + `path.exists()` / `path.name` / `path.read_text()` 的断言，改为 `result = await writer.append_daily_note(...)` + `result.projection_path.exists()` 等；no-ledger fallback 测试确认 `result.ledger_written=False, projection_written=True`
- `tests/test_memory_flush.py`：`process_flush_candidates()` 的 written count 断言保持不变（no-ledger fallback 行为不变）
- `tests/test_memory_append_tool.py`：`execute()` 返回消息中 path 引用改为从 `result.projection_path` 提取；新增 ledger-only 消息分支测试

**回归测试**（无需修改的测试）：
- `tests/test_memory_indexer.py` 全部通过（`_parse_entry_metadata` 扩展向后兼容）
- `tests/test_memory_searcher.py` 不受影响
- `tests/test_memory_contracts.py` 不受影响

## 4. 执行顺序

```
Slice A (DB schema)  →  Slice B (ledger writer)  →  Slice C (双写 + AgentLoop)  →  Slice D (parity check)  →  Slice E (doctor)  →  Slice F (wiring + backup + docs)  →  Slice G (测试)
```

A→B→C 是严格依赖链；D 依赖 B；E 依赖 D；F 依赖 B+C+D；G 覆盖全部。

实际可并行：B 和 D 的类型定义可在 A 完成后同步开始，只要 B 的 `append()` / `get_entries_for_parity()` 接口先确定。F2 (backup) 和 F3 (docs) 与其他 slice 无代码依赖，可随时完成。

## 5. 影响范围

| 位置 | 变更类型 |
|------|---------|
| `src/memory/ledger.py` | **新增** — MemoryLedgerWriter |
| `src/memory/parity.py` | **新增** — MemoryParityChecker + ParityReport |
| `alembic/versions/` | **新增** migration |
| `src/session/database.py` | 新增 `_create_memory_source_ledger_table()` + `ensure_schema()` 调用 |
| `src/memory/writer.py` | 双模式写入（ledger-wired truth-first / no-ledger fallback mandatory projection）；新增 `ledger` 参数 + `_try_write_projection()`；返回值改为 `MemoryWriteResult`；`_check_size_limit()` 保留给 no-ledger fallback |
| `src/tools/builtins/memory_append.py` | `execute()` 返回消息适配 `MemoryWriteResult`（ledger-only / both / fallback） |
| `src/memory/indexer.py` | `_parse_entry_metadata()` 扩展：新增 `source` 字段提取 |
| `src/agent/agent.py` | `AgentLoop.__init__()` 新增 `memory_writer` 可选参数，优先使用外部注入 |
| `src/infra/errors.py` | 新增 `LedgerWriteError` |
| `src/infra/doctor.py` | 新增 D5 check |
| `src/gateway/app.py` | wiring：`MemoryLedgerWriter` → `MemoryWriter` → `MemoryAppendTool` + `AgentLoop` |
| `scripts/backup.py` | `TRUTH_TABLES` 新增 `neomagi.memory_source_ledger` |
| `scripts/restore.py` | 新增轻量 SQL check：恢复后确认 ledger 表存在 + 行数 |
| `design_docs/data_models/postgresql/memory_source_ledger.md` | **新增** — 逐表文档 |
| `design_docs/data_models/postgresql/index.md` | 新增 memory_source_ledger 入口 |
| `tests/test_memory_ledger.py` | **新增** |
| `tests/test_memory_parity.py` | **新增** |
| `tests/test_memory_writer.py` | 现有断言迁移（Path → MemoryWriteResult）+ 新增双写用例 |
| `tests/test_memory_flush.py` | 返回值迁移（若使用 append 返回值） |
| `tests/test_memory_append_tool.py` | 返回消息断言适配 MemoryWriteResult |
| `tests/test_agent_flush_persist.py` | 新增 injected writer 用例 |
| `tests/test_memory_indexer.py` | 新增 `source` 字段提取用例 |
| `tests/test_doctor.py` | 新增 D5 用例 |
| `tests/test_backup.py` | 新增 TRUTH_TABLES 覆盖用例 |
| `tests/test_restore.py` | 新增 ledger 表恢复确认用例 |

## 6. 不做的事

- 不切换 memory read path — `memory_search` 仍走 `memory_entries`
- 不关闭 Markdown daily note projection — workspace 文件继续写入
- 不做历史 memory 全量迁移 — 系统尚未上线，P2-M2d 采用 clean-start ledger baseline；已有本地开发 daily notes 不进入产品迁移范围
- 不实现 shared-space memory
- 不实现 consent-scoped visibility policy
- 不 onboard `memory_application_spec`
- 不实现 `memory render/export/import/reconcile` 命令体系
- 不改变 `MEMORY.md` prompt 注入语义
- 不改变 `MemorySearcher` 或 `memory_search` 工具
- 不改变 `MemoryIndexer.reindex_all()` 的数据来源（仍从 workspace 扫描）
- 不做 `correction` / `retraction` / `contested` 等高级 event type
- 不做 parity 自动修复或补录命令

## 7. 风险

| 风险 | 缓解 |
|------|------|
| Ledger 写入失败阻断 memory_append | truth-first 语义要求阻断（见 D3）；DB 不可用时 memory_append 整体失败，与 session / budget 等其他 DB 依赖行为一致 |
| Ledger 表 DDL 与 alembic migration 不同步 | ensure_schema() idempotent DDL 覆盖 fresh DB；migration 覆盖增量升级 |
| 双写增加 memory_append 延迟 | Ledger 写入是单条 INSERT，PG 本地延迟 <1ms |
| 非 clean 本地 workspace 导致 doctor D5 parity 噪音 | P2-M2d 验收使用 clean-start workspace；旧本地 daily notes 视为 dev artifact，不作为产品迁移输入 |
| AgentLoop fallback 路径（无 memory_writer 注入）不会双写 | 测试中使用无 ledger 的 writer 验证向后兼容；生产路径必须经过 gateway wiring |
| Backup 恢复后 ledger 与 workspace 不一致 | restore 序列先恢复 DB（含 ledger），再恢复 workspace tar，之后 doctor D5 验证 parity |
| Ledger-only entry（projection 失败）在 workspace reindex 后从 memory_entries 消失 | P2-M2d 不改变 reindex 来源（仍从 workspace）；projection 失败时 D5 parity 会 warn `only_in_ledger`，运维可手动触发 projection rerender（P2-M2d 不含自动 rerender）；P2-M3 切换 read path 到 ledger 后此问题自动消除 |
| `_parse_entry_metadata` 扩展 `source` 字段可能影响现有调用方 | 新增 key 只追加，不改变现有 key 语义；现有消费方（indexer、_parse_daily_entries）不使用 `source` key，无影响 |

## 8. Review 修订记录

### Round 1 (2026-04-11)

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| 1 | P1 | `entry_id` UNIQUE 会阻塞未来 correction/retraction/contested 事件 | 改为独立 `event_id` PK + partial unique index `WHERE event_type = 'append'` |
| 2 | P1 | `AgentLoop` 自建 `MemoryWriter` 不经过 gateway wiring，compaction flush 不会双写 | AgentLoop 改为可选接收外部 `memory_writer`，gateway 传入单一实例 |
| 3 | P1 | Parity check 仅比较 ID 集合，会漏报 content/metadata drift | 新增 content-level 比对：比较 content、scope_key、source、source_session_id |
| 4 | P1 | `memory_source_ledger` 不在 `TRUTH_TABLES` 中，backup/restore 会丢失 memory truth | `scripts/backup.py` TRUTH_TABLES 新增该表 |
| 5 | P2 | 缺少 `design_docs/data_models/postgresql/memory_source_ledger.md` | Slice F3 补齐逐表文档 + index.md 更新 |
| 6 | 低风险 | 测试路径应贴合仓库实际平铺结构 | 改为 `tests/test_memory_*.py`，doctor/backup 测试追加到现有文件 |
| 7 | 低风险 | `append()` ON CONFLICT DO NOTHING 返回值语义不明 | 改为 `-> bool`：True=新写入，False=幂等 no-op |

### Round 2 (2026-04-12)

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| 8 | 方向性 | 系统未上线，无需生产历史迁移；clean-start ledger 更合理 | 新增 D7 (clean-start ledger baseline)；验收环境使用空 ledger + 空 projection |
| 9 | 方向性 | 写入顺序应翻转为 DB truth first，消除"写入成功但 ledger 缺失"的不一致 | D3 改为 truth-first：ledger 失败 → 整体失败；projection 失败 → warning |
| 10 | P1 | `_parse_entry_metadata()` 不提取 `source` 字段，parity 无法比对 source | 扩展 parser 新增 `source` key；补 `tests/test_memory_indexer.py` 用例 |
| 11 | P2 | Restore 测试缺失 | 新增 `tests/test_restore.py` 用例；restore.py 新增轻量 SQL check |
| 12 | 低风险 | Parity 验收前提未明确 clean-start | D4 补充验收前提段落；风险表替换过时风险 |

### Round 3 (2026-04-12)

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| 13 | P1 | `_check_size_limit()` 在 ledger 写入前 raise，projection size check 阻断 truth | ledger-wired 模式：size check 内化到 `_try_write_projection()` 中，超限只 warning + skip；no-ledger fallback：保留 `_check_size_limit()` raise 语义 |
| 14 | P2 | Projection 失败时返回可能不存在的 Path + 误导性消息 | 返回值改为 `MemoryWriteResult` (ledger_written / projection_written / projection_path)；`MemoryAppendTool` 消息适配 |
| 15 | P2 | Ledger-only entry 在 workspace reindex 后从 memory_entries 消失 | 风险表显式记录；D5 parity warn `only_in_ledger`；P2-M3 切换 read path 后自动消除 |

### Round 4 (2026-04-12)

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| 16 | P1 | 返回值从 Path 改为 MemoryWriteResult 但回归段声称现有测试不改即通过 | 新增"现有测试迁移"段：test_memory_writer / test_memory_flush / test_memory_append_tool 显式列出断言迁移 |
| 17 | P1 | No-ledger fallback 的 projection 失败/超限变成 best-effort，丢失旧 mandatory 语义 | C1 改为双模式：ledger-wired → projection best-effort；no-ledger fallback → projection mandatory + raise MemoryWriteError（保留现有行为） |
| 18 | P2 | `_write_ledger()` 丢弃 `append()` 返回的 bool，duplicate append 误报 ledger_written=True | 去掉 `_write_ledger()` wrapper，直接调用 `self._ledger.append()` 并传播返回值 |
| 19 | P2 | `process_flush_candidates()` 的 written 计数在新返回值下语义不明 | 计数规则更新：`result.ledger_written or result.projection_written` → written += 1；LedgerWriteError → break；no-ledger MemoryWriteError → break |

### Round 5 (2026-04-12)

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| 20 | P2 | Idempotent no-op (ledger_written=False) 仍无条件写 projection，制造 drift | ledger-wired 分支：`if not ledger_written: return MemoryWriteResult(..., projection_written=False)` early return |
| 21 | P2 | Tool result 只规定了 message 文案，未明确结构化字段迁移（`path` 缺失/变更） | 返回结构明确：始终包含 ok/entry_id/ledger_written/projection_written/message；`path` 仅在 projection 成功时附加（向后兼容） |
