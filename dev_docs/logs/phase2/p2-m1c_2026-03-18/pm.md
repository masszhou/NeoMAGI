---
doc_id: 019d0d4b-d5d8-75a6-b48b-bee4907b7406
doc_id_format: uuidv7
doc_id_assigned_at: 2026-03-20T23:09:27+01:00
---
# P2-M1c Growth Cases 与 Capability Promotion — PM 阶段汇总

> 日期：2026-03-18 ~ 2026-03-20
> 状态：已完成，milestone 已关闭，已合并到 main，post-review 修复完成

## 1. Milestone 总结

P2-M1c 交付 growth case 最小闭环 + builder work memory 证据层 + `skill_spec -> wrapper_tool` capability promotion + replay/rollback 可审计证据。5 个 Phase、10 个 Gate 全部通过验收。

核心成果：
- `wrapper_tool` 从 reserved 升格为 onboarded，成为 P2-M1 的第三类正式 growth object
- GC-1 (human_taught_skill_reuse) 和 GC-2 (skill_to_wrapper_tool_promotion) 两条 curated growth case 完整闭环
- builder work memory 双层结构：workspace artifact (canonical) + bd/beads (index)
- GC-3 (external_readonly_experience_import) 因 import 协议未冻结，推迟至后续 milestone

| Phase | 交付 | Gate 结论 | Backend Commit | 测试增量 |
|-------|------|-----------|---------------|---------|
| Phase 0: Contract V1 + GLOSSARY + GC-3 Decision | WRAPPER_TOOL_EVAL_CONTRACT_V1 (5 checks), GLOSSARY 8 新术语, GC-3 推迟决策, bd feasibility checklist | PASS | 2a5a7b2 | +14 |
| Phase 1: Builder Work Memory Substrate | BuilderTaskRecord, workspace/artifacts/, work_memory 模块, bd feasibility spike (7/7 通过) | PASS_WITH_RISK | 30026c8 + 77dfd76 (fix) | +29 |
| Phase 2: Wrapper Tool Onboarding | WrapperToolSpec, WrapperToolStore, WrapperToolGovernedObjectAdapter, Alembic migration, ToolRegistry unregister/replace, policies onboarding, gateway wiring | PASS_WITH_RISK | 2348a9a + f19b861 (fix) | +85 |
| Phase 3: Growth Case Catalog + Runner | GrowthCaseSpec catalog (gc-1, gc-2), CaseRunner, GC-1/GC-2 集成测试, veto/rollback 失败 case | PASS | ea5d9db + 596260a (fix) | +48 |
| Phase 4: Acceptance Closeout | 全量 lint/test green (1495 tests), evidence packet, beads epic 关闭 | PASS | 8099419 | +16 |

Post-review 修复后最终测试总数：1503 tests，0 failures，ruff clean，0 complexity block findings。
基线增长（相对 P2-M1b 收口）：约 +200 tests。

## 2. Acceptance Criteria (A1~A9) 达成情况

| ID | 要求 | 状态 | 证据 |
|----|------|------|------|
| A1 | growth case 回答"改了什么、为什么、怎么验证、如何回滚" | ✅ | CaseRunner artifact 含 proposal/eval/apply/rollback refs |
| A2 | builder work memory 双层结构 | ✅ | BuilderTaskRecord + workspace/artifacts/ + bd spike 7/7 |
| A3 | wrapper_tool onboarded, procedure_spec reserved | ✅ | policies.py:L27 onboarded, L34 reserved for P2-M2 |
| A4 | skill → wrapper_tool promote 注册到 ToolRegistry | ✅ | test_gc2_integration: apply → registry.get() 成功 |
| A5 | skill reuse 先于 promote | ✅ | test_gc1_integration: resolver 命中 + projector delta |
| A6 | propose → evaluate → apply 闭环 | ✅ | test_gc2_integration: 完整 promote flow |
| A7 | 失败 case veto/rollback | ✅ | test_gc2_integration: eval fail→veto, apply→rollback→registry removed |
| A8 | GC-1 + GC-2 replay 级证据 | ✅ | 集成测试覆盖完整 lifecycle |
| A9 | lint clean + test green | ✅ | 1495 passed, ruff clean |

## 3. 变更清单（文件级）

### 新增文件（25 个）

**源码（14 个）**
- `src/builder/__init__.py` — 包初始化
- `src/builder/types.py` — BuilderTaskRecord (frozen, 含 artifact_id)
- `src/builder/artifact.py` — generate_artifact_id, render_artifact_markdown, write_artifact
- `src/builder/work_memory.py` — create_builder_task, update_task_progress, link_artifact_to_bead
- `src/wrappers/__init__.py` — 包初始化
- `src/wrappers/types.py` — WrapperToolSpec (frozen, 11 fields)
- `src/wrappers/store.py` — WrapperToolStore (PG raw SQL, current-state + governance ledger, transaction())
- `src/growth/adapters/wrapper_tool.py` — WrapperToolGovernedObjectAdapter (5 eval checks, atomic apply/rollback)
- `src/growth/case_types.py` — GrowthCaseStatus, GrowthCaseSpec, GrowthCaseRun
- `src/growth/cases.py` — GROWTH_CASE_CATALOG (gc-1, gc-2), get_case_spec, list_case_specs
- `src/growth/case_runner.py` — CaseRunner (thin orchestration, artifact persistence)
- `alembic/versions/b9c0d1e2f3a4_create_wrapper_tool_tables.py` — wrapper_tools + wrapper_tool_versions

**测试（11 个）**
- `tests/builder/test_types.py` — 8 tests
- `tests/builder/test_artifact.py` — 10 tests
- `tests/builder/test_work_memory.py` — 11 tests
- `tests/wrappers/test_types.py` — 12 tests
- `tests/wrappers/test_store.py` — 19 tests
- `tests/growth/test_wrapper_tool_adapter.py` — 50 tests
- `tests/growth/test_case_types.py` — 9 tests
- `tests/growth/test_cases.py` — 9 tests
- `tests/growth/test_case_runner.py` — 18 tests
- `tests/growth/test_gc1_integration.py` — GC-1 完整闭环 (teach→propose→eval→apply→reuse)
- `tests/growth/test_gc2_integration.py` — GC-2 完整闭环 (promote→eval→apply + veto/rollback)

### 修改文件（4 个）

- `src/growth/contracts.py` — 新增 WRAPPER_TOOL_EVAL_CONTRACT_V1, _CONTRACTS 切到 V1
- `src/growth/policies.py` — wrapper_tool → onboarded, procedure_spec notes 更新
- `src/tools/registry.py` — 新增 unregister(), replace()
- `src/gateway/app.py` — 接入 WrapperToolStore + WrapperToolGovernedObjectAdapter

### 文档 & 配置

- `design_docs/GLOSSARY.md` — 8 新术语
- `dev_docs/cases/gc3_import_deferred.md` — GC-3 推迟决策 + bd feasibility checklist
- `dev_docs/cases/bd_feasibility_spike.md` — bd spike 结果 (7/7 通过)
- `dev_docs/cases/p2-m1c_evidence_packet.md` — 最终验收 evidence packet

总计：**42 files changed, +4,965 insertions, -77 deletions**。

## 4. Gate 验收报告索引

| Gate | Phase | Status | Result | Backend Commit | Tester Commit |
|------|-------|--------|--------|---------------|--------------|
| g0 | 0 | closed | PASS | 2a5a7b2 | b1bbd4e |
| g1 | 1 | closed | PASS_WITH_RISK | 77dfd76 | 1213395 |
| g2 | 2 | closed | PASS_WITH_RISK | f19b861 | 8faace6 |
| g3 | 3 | closed | PASS | 596260a | f192ac5 |
| g4 | 4 | closed | PASS | 8099419 | e6e59ca |

Tester review 报告：
- `feat/tester-m1c-g0`: `dev_docs/reviews/phase2/p2-m1c_p0_2026-03-18.md`
- `feat/tester-m1c-g1`: `dev_docs/reviews/phase2/p2-m1c_p1_2026-03-18.md`
- `feat/tester-m1c-g2`: `dev_docs/reviews/phase2/p2-m1c_p2_2026-03-18.md`
- `feat/tester-m1c-g3`: `dev_docs/reviews/phase2/p2-m1c_p3_2026-03-18.md`
- `feat/tester-m1c-g4`: `dev_docs/reviews/phase2/p2-m1c_p4_2026-03-18.md`

## 5. 跨 Gate 累计 Findings 与修复

| Gate | ID | 严重度 | 问题 | 修复 Commit |
|------|----|--------|------|------------|
| G1 | F1 | P1 | render_artifact_markdown / create_builder_task / update_task_progress 超复杂度门禁 | 77dfd76 |
| G2 | F1 | P1 | _check_typed_io_validation 8 branches 超 block limit | f19b861 |
| G2 | F2 | P2 | ToolRegistry 内存变更与 DB 事务不在同一原子边界（V1 已知限制） | 已记录，V1 接受 |
| G3 | F1 | P1 | 4 个集成测试函数超 50 行限制 | 596260a |
| G3 | F2 | P1 | ruff errors: unused imports/var + import sort | 596260a |
| G3 | F3 | P3 | finalize() status guard 未覆盖 vetoed | 596260a |
| G3 | F4 | P3 | CaseRunner 缺 record_veto() | 596260a |

所有 G0~G4 P0/P1 findings 已修复。

## 5.1 用户 Post-Review Findings（合并后）

三轮 post-review，共 5 个 finding，全部修复：

| 轮次 | ID | 严重度 | 问题 | 修复 Commit |
|------|----|--------|------|------------|
| R1 | PR-1 | P1 | rollback() 找到当前 active 版本后重新 upsert 回去，实际不回退任何东西 | 858c699 |
| R1 | PR-2 | P1 | tool.name vs wrapper_tool_id 不绑定，错误命名的 wrapper 可注册但不可回滚 | 858c699 |
| R1 | PR-3 | P2 | apply/rollback 宣称 atomic 但 ToolRegistry 副作用不在事务内 | 858c699 |
| R2 | PR-4 | P1 | 升级路径下补偿逻辑会丢失旧版本；veto 对多 active 版本回滚错对象 | 764a823 |
| R3 | PR-5 | P1 | 启动时不恢复 active wrappers 到 ToolRegistry，且 apply guard 堵死恢复路径 | d9caef0 |

修复措施总结：
- rollback 改为 disable-on-rollback（移除 + 反注册，不 re-upsert）
- `_resolve_and_register()` 强制 `tool.name == spec.id`
- apply/rollback 改为 DB-first + compensating semantics
- apply() 加 fail-closed guard：已有 active 时拒绝 in-place upgrade
- veto() 改为 version-aware：version 与 find_last_applied 不一致时拒绝
- Alembic 新增 partial unique index `uq_wrapper_tool_versions_single_active`
- gateway 启动新增 `_restore_active_wrappers()` 从 DB 恢复 active wrappers
- apply() 拆分 `_validate_apply_preconditions()` 满足复杂度门禁

## 6. 架构决策

| ADR | 标题 | 要点 |
|-----|------|------|
| 0055 | Builder work memory via bd and workspace artifacts | canonical = workspace/artifacts/, bd = index, artifact_id = UUIDv7, 不新增 PG 表 |
| 0056 | Wrapper tool onboarding and runtime boundary | wrapper_tool = onboarded, single-turn governed capability, 不冻结 impl_ref/API/表结构 |
| 0057 | Freeze only hard-to-remediate foundations | ADR 只冻结地基 (stable ID, scope, provenance, truth boundary), V1 形状 = implementation choice |

## 7. 设计约束遵守情况

| 约束 | 状态 |
|------|------|
| wrapper_tool V1 = single-turn typed capability | ✅ 无 cross-turn state |
| procedure_spec 继续 reserved for P2-M2 | ✅ policies.py 明确 |
| ADR 0054 immutable contract | ✅ 新建 V1，skeleton 保留但不被 runtime 使用 |
| builder work memory canonical = workspace/artifacts/ | ✅ 不在 dev_docs/ |
| bd/beads 不承载 control-plane | ✅ 只做 issue/index |
| GrowthCaseSpec = hardcoded catalog | ✅ 不动态创建 |
| GrowthCaseRun 不进 PostgreSQL | ✅ workspace artifact 持久化 |
| ToolRegistry 支持 replace/remove | ✅ unregister() + replace() |
| apply/rollback 原子或显式补偿 | ✅ store.transaction() |
| promote 阈值保守 (usage>=3, success>=0.8) | ✅ 不满足只记 candidate |

## 8. Residual Risks (V1 接受)

| # | 风险 | 等级 | 说明 |
|---|------|------|------|
| R1 | Registry-DB drift | Low | ToolRegistry 内存变更与 DB 事务不在同一原子边界；apply 失败后 registry 可能残留 |
| R2 | Entry condition enforcement gap | Low | promote 条件只在测试中验证，无生产 runtime 自动检查 |
| R3 | Factory validation gap | Low | eval dry-run 只检查模块可导入，不验证 factory 函数存在性 |
| R4 | uuid4 vs UUIDv7 | Low | V1 使用 uuid4 临时方案，TODO 标记后续升级 |

## 9. Beads Issue 树最终状态

```
NeoMAGI-em2  P2-M1c: Growth Cases + Capability Promotion       [closed]
├── em2.1    P0: Contract V1 + GLOSSARY + GC-3 Decision         [closed]
│   ├── em2.1.1  GLOSSARY 更新                                   [closed]
│   ├── em2.1.2  WRAPPER_TOOL_EVAL_CONTRACT_V1                   [closed]
│   └── em2.1.3  GC-3 decision + bd feasibility checklist        [closed]
├── em2.2    P1: Builder Work Memory Substrate                   [closed]
│   ├── em2.2.1  workspace/artifacts/ + BuilderTaskRecord        [closed]
│   └── em2.2.2  bd feasibility spike + work_memory              [closed]
├── em2.3    P2: Wrapper Tool Store + Adapter + Runtime Wiring   [closed]
│   ├── em2.3.1  WrapperToolSpec + WrapperToolStore + migration  [closed]
│   └── em2.3.2  Adapter + policies + ToolRegistry + gateway     [closed]
├── em2.4    P3: Growth Case Catalog + Runner                    [closed]
│   ├── em2.4.1  GC-1: human_taught_skill_reuse                 [closed]
│   ├── em2.4.2  GC-2: skill_to_wrapper_tool_promotion           [closed]
│   └── em2.4.3  Case catalog + case runner                      [closed]
└── em2.5    P4: Acceptance Closeout                             [closed]
```

## 10. 过程经验

| 事件 | 影响 | 改进 |
|------|------|------|
| 每轮 tester review 均发现 complexity guard block regression | 3 次 P1 fix 循环 | Backend commit 前必须跑 `just lint`（不只是 `ruff check`），确认 complexity guard 0 block |
| ADR 0056 明确不冻结 impl_ref/API/表结构 | Phase 0 范围大幅收窄 | 区分 ADR 冻结项 vs implementation choice 可减少前期争论 |
| bd feasibility spike 7/7 通过 | 无需 fallback | bd create/update/comment 可承载最小索引层 |
| tester worktree 与 backend worktree 分支独立 | review 产物分散在多个分支 | 合并时需要收集 tester 分支的 review 文件 |
| GC-3 推迟决策在 Phase 0 明确写下 | 避免后续范围蔓延 | 对可选 scope 尽早做 in/out 决策并记录 |
| 用户 post-review 发现 rollback/补偿/启动恢复 3 类实质性问题 | 5 个 P1/P2 finding，3 轮修复 | mock-heavy 测试容易掩盖集成语义缺陷；adapter 级别需要至少一组用真实 store 行为（而非全 mock）的测试来验证 apply→rollback→registry 端到端一致性 |
| apply() 在引入 fail-closed guard 后堵死了启动恢复路径 | 新增守卫意外阻断正常运维路径 | 加防护性约束时必须同步检查所有消费路径（启动、恢复、运维），否则守卫本身成为新故障源 |

## 11. Devcoord 控制面

- milestone: p2-m1c, closed
- 47 events, 全部 reconciled
- 10 gates (5 backend + 5 review), 全部 closed
- 心跳日志: `dev_docs/logs/phase2/p2-m1c_2026-03-18/heartbeat_events.jsonl`

## 12. Git 合并记录

| 操作 | Commit | 分支 |
|------|--------|------|
| Phase 0 backend | 2a5a7b2 | feat/backend-m1c-impl |
| Phase 1 backend | 30026c8 | feat/backend-m1c-impl |
| Phase 1 fix (complexity) | 77dfd76 | feat/backend-m1c-impl |
| Phase 2 backend | 2348a9a | feat/backend-m1c-impl |
| Phase 2 fix (complexity) | f19b861 | feat/backend-m1c-impl |
| Phase 3 backend | ea5d9db | feat/backend-m1c-impl |
| Phase 3 fix (F1-F4) | 596260a | feat/backend-m1c-impl |
| Phase 4 evidence packet | 8099419 | feat/backend-m1c-impl |
| Post-review R1: rollback/name/compensating | 858c699 | feat/backend-m1c-impl |
| Post-review R2: single-active/veto-aware | 764a823 | feat/backend-m1c-impl |
| Post-review R3: startup restore | d9caef0 | feat/backend-m1c-impl |
| Merge to main | (merge commit) | main |
| Post-merge complexity fix | 834661a | main |
| Tester G0 review | b1bbd4e | feat/tester-m1c-g0 |
| Tester G1 review | 1213395 | feat/tester-m1c-g1 |
| Tester G2 review | 8faace6 | feat/tester-m1c-g2 |
| Tester G3 review | f192ac5 | feat/tester-m1c-g3 |
| Tester G4 final review | e6e59ca | feat/tester-m1c-g4 |

## 13. 未完成项

- GC-3 (external_readonly_experience_import) 推迟至 import 协议冻结后
- uuid4 → UUIDv7 升级 (TODO 已标记)
- promote entry condition 生产 runtime enforcement（当前仅测试验证）
- 启动恢复失败时 degraded health signal（当前 log + skip，非阻塞）
