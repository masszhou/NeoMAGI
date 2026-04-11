---
doc_id: 019d7d5f-0bfc-7a3c-9997-c8a9aa27340f
doc_id_format: uuidv7
doc_id_assigned_at: 2026-04-11T18:27:54+02:00
---
# P2-M2c 实现计划：ProcedureSpec Governance Adapter

> 状态：draft  
> 日期：2026-04-11  
> 输入：`design_docs/phase2/p2_m2_post_self_evolution_staged_plan.md` Section 3  
> 参照模式：`SkillGovernedObjectAdapter` + `WrapperToolGovernedObjectAdapter`

## 0. 目标

让 `procedure_spec` 从 `reserved` kind 进入正式治理路径：

```
propose → evaluate → apply → rollback / veto → audit
```

验收后，NeoMAGI 能安全地修改自己的流程定义，且每次变更可解释、可回滚、可审计。

## 1. 当前基线

| 组件 | 状态 |
|------|------|
| `GrowthObjectKind.procedure_spec` | enum 已存在 |
| `PolicyRegistry` | `procedure_spec: reserved`，无 adapter |
| `PROCEDURE_SPEC_EVAL_CONTRACT_SKELETON` | 5 checks 已命名，实现为空 |
| `ProcedureSpecRegistry` | 内存 registry，有 `register()` + `validate_procedure_spec()` 静态校验 |
| `ProcedureStore` | 只管 `active_procedures`（运行实例），不管 spec governance |
| `_build_governance_engine()` | 已接 soul / skill_spec / wrapper_tool，无 procedure_spec |

## 2. 实现切片

### Slice A：ProcedureSpecGovernanceStore（DB 层）

新增 spec governance 的持久化层，复用 SkillStore 的 current-state + ledger 双表模式。

**新增 DB 表**（alembic migration）：

`procedure_spec_definitions`（current-state）：
| 列 | 类型 | 说明 |
|----|------|------|
| id | TEXT PK | spec_id |
| version | INTEGER | spec version |
| payload | JSONB | ProcedureSpec.model_dump() |
| disabled | BOOLEAN default FALSE | rollback 后标记禁用 |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

`procedure_spec_governance`（append-only ledger）：
| 列 | 类型 | 说明 |
|----|------|------|
| governance_version | SERIAL PK | 自增序列 |
| procedure_spec_id | TEXT | spec_id |
| status | TEXT | proposed / active / rolled_back / vetoed / superseded |
| proposal | JSONB | GrowthProposal payload |
| eval_result | JSONB | GrowthEvalResult |
| created_by | TEXT | |
| created_at | TIMESTAMPTZ | |
| applied_at | TIMESTAMPTZ | nullable |
| rolled_back_from | INTEGER | nullable，指向被回滚的 governance_version |

**新增文件**：`src/procedures/governance_store.py`

方法清单（参照 SkillStore）：
- `create_proposal(proposal) → int`
- `get_proposal(governance_version) → record | None`
- `store_eval_result(governance_version, result)`
- `update_proposal_status(governance_version, status, *, applied_at?, rolled_back_from?, session?)`
- `upsert_active(spec_payload, session?)`
- `disable(spec_id, session?)`
- `find_last_applied(spec_id) → record | None`
- `find_previous_applied(spec_id, before) → record | None`
- `list_active() → list[record]`
- `transaction() → AsyncContextManager[AsyncSession]`

### Slice B：Eval Contract V1（5 个确定性检查）

将 `PROCEDURE_SPEC_EVAL_CONTRACT_SKELETON` 升级为 `PROCEDURE_SPEC_EVAL_CONTRACT_V1`，实现 5 个检查：

**新增文件**：`src/growth/adapters/procedure_spec.py`（检查函数 + adapter 类）

| 检查 | 输入 | 判定 |
|------|------|------|
| `_check_transition_determinism` | ProcedureSpec | 每个 state 的每个 action 只有一个 target；initial_state 存在于 states；所有 action.to target 存在 |
| `_check_guard_completeness` | ProcedureSpec + GuardRegistry | enter_guard 和每个 action.guard 在 registry 中可解析（或为 None） |
| `_check_action_tool_binding` | ProcedureSpec + ToolRegistry | 每个 action.tool 存在于 ToolRegistry；action_id 满足 OpenAI function name 约束；不与 RESERVED_ACTION_IDS 冲突 |
| `_check_interrupt_resume_safety` | ProcedureSpec | 至少有一个 terminal state（actions 为空）；non-terminal states 都有至少一个 action |
| `_check_context_model_validity` | ProcedureSpec + ContextRegistry | context_model 在 ProcedureContextRegistry 中可解析 |

说明：
- `checkpoint_recoverability` 和 `scope_claim_consistency` 在 skeleton 中已命名，但对 V1 而言，上面 5 个检查已覆盖核心安全约束。将 skeleton 的 5 checks 重映射为上述 5 个可实现的检查，更新 contract 定义。
- 所有检查纯确定性，无 LLM 调用。
- 复用 `ProcedureSpecRegistry.validate_procedure_spec()` 已有的静态校验逻辑，避免重复实现。

### Slice C：ProcedureSpecGovernedObjectAdapter（7 个协议方法）

在 `src/growth/adapters/procedure_spec.py` 中实现完整 adapter：

```
kind = GrowthObjectKind.procedure_spec

propose(proposal) → int
  - 校验 payload 包含 procedure_spec dict
  - 解析 ProcedureSpec（fail-fast）
  - store.create_proposal() → governance_version

evaluate(version) → GrowthEvalResult
  - early-exit: missing / not proposed
  - 解析 ProcedureSpec from payload
  - 运行 5 个 checks（Slice B）
  - store.store_eval_result()
  - 返回 composite result

apply(version)
  - 校验: exists, proposed, eval passed
  - 解析 ProcedureSpec
  - 安全检查: 如果 spec_id 在 ProcedureStore 有 active instance → 拒绝
  - ATOMIC:
    - store.upsert_active(spec_payload)
    - store.update_proposal_status(version, active, applied_at=now())
  - spec_registry.register(spec)（内存副作用，DB-first + compensating）

rollback(**kwargs)
  - kwarg: procedure_spec_id: str
  - find current/previous applied
  - 安全检查: 如果 spec_id 在 ProcedureStore 有 active instance → 拒绝
  - ATOMIC:
    - restore previous spec 或 disable
    - update current status → rolled_back
    - create rollback ledger entry → new governance_version
  - 更新 spec_registry（unregister 或 replace）
  - 返回 new governance_version

veto(version)
  - proposed → mark vetoed
  - active → delegate to rollback

get_active() → list[ProcedureSpec]
  - 从 spec_registry.list_specs() 返回
```

**Active instance 安全检查**：apply/rollback 前查询 `ProcedureStore.get_active(session_id=None)` — 需要在现有 `ProcedureStore` 中新增 `has_active_for_spec(spec_id) → bool` 方法（查询 `active_procedures WHERE spec_id = ? AND completed_at IS NULL`）。

**Registry 副作用**：遵循 P2-M1c 的 DB-first + compensating semantics：
1. 先 commit DB
2. 再操作 spec_registry
3. registry 失败则补偿回滚 DB

**`ProcedureSpecRegistry` 需补充**：
- `unregister(spec_id)` — 移除 spec（rollback/veto 使用）
- `replace(spec)` — 替换已注册 spec（restore previous 使用）

### Slice D：Wiring + Startup Restore + Policy 升级

**`src/growth/policies.py`**：
- `procedure_spec` 从 `reserved` → `onboarded`

**`src/growth/contracts.py`**：
- `PROCEDURE_SPEC_EVAL_CONTRACT_SKELETON` → `PROCEDURE_SPEC_EVAL_CONTRACT_V1`
- 更新 `required_checks` 对应 Slice B 的 5 个实际检查名

**`src/gateway/app.py`**：
- `_build_governance_engine()` 新增 `procedure_spec_registry` 参数
- 构造 `ProcedureSpecGovernanceStore` 和 `ProcedureSpecGovernedObjectAdapter`
- 注入 `adapters` dict
- `_build_memory_and_tools()` 传递 `spec_registry` 给 `_build_governance_engine()`

**启动恢复**：
- 新增 `_restore_active_procedure_specs(governance_store, spec_registry, context_registry, guard_registry)`
- 从 `governance_store.list_active()` 加载已 apply 的 spec → `spec_registry.register(spec)`
- 在 `_build_procedure_runtime()` 之后、`_build_governance_engine()` 之前调用

**Alembic migration**：
- 新增 `procedure_spec_definitions` 和 `procedure_spec_governance` 两张表

### Slice E：测试 + 端到端验证

**单元测试**（`tests/growth/test_procedure_spec_adapter.py`）：
- `test_propose_valid_spec` — 合法 spec payload → 返回 governance_version
- `test_propose_invalid_payload` — 缺少必需字段 → 拒绝
- `test_evaluate_all_checks_pass` — 合法 spec → passed=True, 5 checks 全通过
- `test_evaluate_transition_determinism_fail` — action.to 指向不存在 state → 检查失败
- `test_evaluate_guard_completeness_fail` — guard 不在 registry → 检查失败
- `test_evaluate_tool_binding_fail` — tool 不在 ToolRegistry → 检查失败
- `test_apply_success` — eval passed → upsert + registry.register()
- `test_apply_with_active_instance_rejected` — 有 active procedure → 拒绝 apply
- `test_rollback_restores_previous` — rollback → previous spec restored in registry
- `test_rollback_disables_when_no_previous` — 无 previous → disable
- `test_rollback_with_active_instance_rejected` — 有 active procedure → 拒绝 rollback
- `test_veto_proposed` — proposed → vetoed
- `test_veto_active_delegates_to_rollback` — active → rollback
- `test_get_active` — 返回已注册 specs

**集成测试**（`tests/integration/test_procedure_spec_governance.py`）：
- 端到端 propose → evaluate → apply → rollback 在真实 PG 上跑通
- governance ledger 记录完整

**CLI 验证脚本**（写入 user test guide 或独立脚本）：
- 注册一个 3 状态 test spec → propose → evaluate → apply → 确认 runtime 可用 → rollback → 确认 spec 不再可用

## 3. 执行顺序

```
Slice A (DB store)  →  Slice B (eval checks)  →  Slice C (adapter)  →  Slice D (wiring)  →  Slice E (测试)
```

A→B→C 是严格依赖；D 依赖 C；E 覆盖全部。

## 4. 影响范围

| 位置 | 变更类型 |
|------|---------|
| `src/procedures/governance_store.py` | **新增** |
| `src/growth/adapters/procedure_spec.py` | **新增** |
| `alembic/versions/` | **新增** migration |
| `src/procedures/registry.py` | 补充 `unregister()` / `replace()` |
| `src/procedures/store.py` | 补充 `has_active_for_spec()` |
| `src/growth/policies.py` | `procedure_spec: reserved → onboarded` |
| `src/growth/contracts.py` | skeleton → V1 |
| `src/gateway/app.py` | wiring + startup restore |
| `tests/growth/test_procedure_spec_adapter.py` | **新增** |
| `tests/integration/test_procedure_spec_governance.py` | **新增** |

## 5. 不做的事

- 不做 Claude Code CLI / Codex CLI wrapper
- 不做 git worktree 编排
- 不做 self-evolution workflow
- 不做 memory source ledger（P2-M2d）
- 不做 in-place upgrade（已有 active spec 的版本迁移）
- 不做 spec 的 WebChat 用户入口（propose 仍通过 CLI 或 operator 脚本）
- 不改 ProcedureRuntime 核心逻辑（enter/apply_action 不变）

## 6. 风险

| 风险 | 缓解 |
|------|------|
| Registry 内存副作用不受 DB transaction 保护 | DB-first + compensating semantics（P2-M1c 已验证） |
| apply 时有 active instance 导致 spec 替换冲突 | apply/rollback 前查询 `has_active_for_spec()` fail-closed |
| 启动恢复时 context_registry / guard_registry 尚未就绪 | 恢复调用放在 `_build_procedure_runtime()` 之后（registry 已构造） |
| Eval 检查可能遗漏边界 case | V1 先覆盖 5 个核心检查，后续可追加；检查不足时 fail-open 风险低（apply 前有人工 gate） |
