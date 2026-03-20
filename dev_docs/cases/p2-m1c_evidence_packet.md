# P2-M1c Evidence Packet

- **Milestone**: P2-M1c (Growth Cases + Capability Promotion)
- **Date**: 2026-03-19
- **Branch**: `feat/backend-m1c-impl`
- **HEAD**: `596260a85c9c71b976b8d81a88b29c7db7b1a716`
- **Total tests**: 1495 (all passed)
- **Lint**: clean (ruff check + complexity guard: 0 block findings)

---

## Use Case A~F Requirement-Evidence Matrix

| Use Case | Requirement | Evidence |
|----------|-------------|----------|
| **A** (G1/G8) | Agent can answer "what changed, why, how verified, how to rollback" | `src/growth/case_runner.py:26-47` — `_render_run_markdown()` writes proposal/eval/apply/rollback refs into artifact. `tests/growth/test_gc1_integration.py:242-245` — `_assert_artifact_contains()` verifies artifact has `gv:1`, `passed=True`, `success=True`, summary. Commit `ea5d9db`. |
| **B** (G2) | Builder work memory has brief+decisions+blockers+validation+artifact refs | `src/builder/types.py:10-36` — `BuilderTaskRecord` frozen model with `task_brief`, `decision_snapshots`, `blockers`, `validation_summary`, `artifact_refs`. `src/builder/work_memory.py:60-99` — `create_builder_task()` dual-layer: artifact file + bd issue index. `dev_docs/cases/bd_feasibility_spike.md` — 7/7 bd capabilities verified. `tests/builder/test_work_memory.py` — 11 tests covering create/update/link lifecycle. Commit `30026c8`. |
| **C** (G3) | wrapper_tool onboarded, ToolRegistry visible | `src/growth/policies.py:32-38` — `wrapper_tool: onboarding_state=onboarded`. `tests/growth/test_wrapper_tool_adapter.py:407-435` — `test_apply_success_upserts_and_registers`: apply calls `upsert_active` + `registry.replace`. `tests/growth/test_policies.py:83-93` — `test_wrapper_tool_onboarded`. Commit `2348a9a`. |
| **D** (G5) | Skill reused before promote via second similar task | `tests/growth/test_gc1_integration.py:199-212` — `_run_reuse_phase()`: resolver matches taught skill, projector produces delta with `ruff` keyword. Line 207: `assert len(candidates) >= 1`, line 208: `assert candidates[0][0].id == spec.id`, line 211-212: `assert len(view.llm_delta) > 0; assert "ruff" in view.llm_delta[0].lower()`. Commit `ea5d9db`. |
| **E** (G6) | At least one case completes propose -> evaluate -> apply | `tests/growth/test_gc2_integration.py:275-298` — `TestGC2FullFlow.test_promote_skill_to_wrapper_tool`: full propose -> eval -> apply -> finalize, asserts `registry.replace` called, `upsert_active` called, status `passed`, artifact contains `gv:1` and `passed=True`. Commit `ea5d9db`. |
| **F** (G7) | Failure case: veto or rollback | `tests/growth/test_gc2_integration.py:343-377` — `TestGC2EvalFailure.test_eval_failure_vetoes_run`: eval fails on `typed_io_validation` (bad `input_schema`), `record_veto` called, status `vetoed`. `tests/growth/test_gc2_integration.py:385-415` — `TestGC2Rollback.test_apply_then_rollback`: apply then `engine.rollback`, `registry.unregister` asserted, `remove_active` asserted, status `rolled_back`, `rollback:executed` in refs. Commit `ea5d9db`, fix `596260a`. |

---

## Acceptance Criteria Checklist (A1~A9)

### A1: Growth case answers why/what/how/rollback
- `src/growth/case_runner.py` — `CaseRunner` records each lifecycle step (proposal, eval, apply, rollback) as refs in `GrowthCaseRun` and persists as markdown artifact
- `src/growth/case_types.py:35-66` — `GrowthCaseRun` model with `proposal_refs`, `eval_refs`, `apply_refs`, `rollback_refs`, `artifact_refs`
- `tests/growth/test_gc1_integration.py:229-245` — full flow asserts all refs present in artifact

### A2: Builder work memory dual-layer structure
- `src/builder/types.py` — `BuilderTaskRecord` (frozen Pydantic model)
- `src/builder/artifact.py` — `write_artifact()` renders markdown to `workspace/artifacts/builder_runs/`
- `src/builder/work_memory.py` — `create_builder_task()` creates artifact + optional bd issue; `update_task_progress()` updates both layers
- `dev_docs/cases/bd_feasibility_spike.md` — 7/7 bd CLI capabilities verified (create, update, comments, query, artifact refs, labels, JSON output)
- `tests/builder/test_work_memory.py` — 11 tests: create, update, link, bd fallback

### A3: wrapper_tool onboarded, procedure_spec reserved
- `src/growth/policies.py:32-38` — `wrapper_tool: onboarding_state=onboarded`
- `src/growth/policies.py:39-45` — `procedure_spec: onboarding_state=reserved`
- `tests/growth/test_policies.py:83-93` — `test_wrapper_tool_onboarded`
- `tests/growth/test_policies.py:95-105` — `test_procedure_spec_reserved`

### A4: Skill -> wrapper_tool promote loop
- `src/growth/adapters/wrapper_tool.py` — `WrapperToolGovernedObjectAdapter` (propose/evaluate/apply/rollback/veto)
- `src/wrappers/store.py` — `WrapperToolStore` (PostgreSQL, `wrapper_tools` + `wrapper_tool_versions` tables)
- `src/wrappers/types.py` — `WrapperToolSpec` domain model
- `src/growth/contracts.py:167-216` — `WRAPPER_TOOL_EVAL_CONTRACT_V1` (5 checks)
- `alembic/versions/b9c0d1e2f3a4_create_wrapper_tool_tables.py` — DB migration
- `tests/growth/test_gc2_integration.py:275-298` — full promote flow test

### A5: Skill reuse prior to promote
- `tests/growth/test_gc1_integration.py:199-212` — `_run_reuse_phase()` demonstrates resolver matching + projector delta
- `tests/growth/test_gc1_integration.py:248-278` — `TestGC1ReuseRequired` negative test: unrelated skill does not match

### A6: propose -> eval -> apply loop
- `tests/growth/test_gc2_integration.py:241-263` — `_run_gc2_propose_eval_apply()`: propose (gv=1), evaluate (passed=True), apply (upsert+register)
- `tests/growth/test_gc1_integration.py:165-196` — `_run_propose_eval_apply()`: propose (gv=1), evaluate (passed=True), apply (active in store)

### A7: Failure case veto/rollback
- `tests/growth/test_gc2_integration.py:343-377` — eval failure -> veto (`GrowthCaseStatus.vetoed`)
- `tests/growth/test_gc2_integration.py:385-415` — apply -> rollback (`GrowthCaseStatus.rolled_back`, `registry.unregister` asserted)
- `tests/growth/test_wrapper_tool_adapter.py:443-477` — adapter-level rollback (restore previous vs disable)

### A8: GC-1 + GC-2 replay-grade evidence
- `tests/growth/test_gc1_integration.py` — 2 tests: full teach/propose/eval/apply/reuse flow + negative resolver test
- `tests/growth/test_gc2_integration.py` — 9 tests: full promote flow + eval failure/veto + apply/rollback + condition checks
- All tests: deterministic, no DB, no LLM, no API quota — fully replayable

### A9: Lint clean + test green
- `just lint`: ruff `All checks passed!`, complexity guard `0 block findings`
- `just test`: `1495 passed, 67 warnings in 21.07s`

---

## File Change Summary

### New source files (14)
| File | Role |
|------|------|
| `src/builder/__init__.py` | Package init |
| `src/builder/types.py` | `BuilderTaskRecord` frozen Pydantic model |
| `src/builder/artifact.py` | Artifact markdown rendering + file writing |
| `src/builder/work_memory.py` | Dual-layer lifecycle: artifact + bd index |
| `src/wrappers/__init__.py` | Package init |
| `src/wrappers/types.py` | `WrapperToolSpec` domain model |
| `src/wrappers/store.py` | `WrapperToolStore` (PostgreSQL raw SQL, governance ledger) |
| `src/growth/adapters/wrapper_tool.py` | `WrapperToolGovernedObjectAdapter` (5 eval checks, atomic apply/rollback) |
| `src/growth/case_types.py` | `GrowthCaseRun`, `GrowthCaseStatus`, `GrowthCaseSpec` |
| `src/growth/cases.py` | Growth case catalog (GC-1, GC-2 specs) |
| `src/growth/case_runner.py` | `CaseRunner` lifecycle orchestration + artifact persistence |
| `alembic/versions/b9c0d1e2f3a4_create_wrapper_tool_tables.py` | DB migration: `wrapper_tools` + `wrapper_tool_versions` |
| `dev_docs/cases/bd_feasibility_spike.md` | bd CLI feasibility verification (7/7 pass) |
| `dev_docs/cases/gc3_import_deferred.md` | GC-3 import deferral decision |

### Modified source files (4)
| File | Change |
|------|--------|
| `src/growth/contracts.py` | Added `WRAPPER_TOOL_EVAL_CONTRACT_V1` + procedure/memory skeletons |
| `src/growth/policies.py` | `wrapper_tool` upgraded to `onboarded` |
| `src/tools/registry.py` | Added `unregister()` + `replace()` methods |
| `src/gateway/app.py` | Extracted `_build_governance_engine()`, wired `WrapperToolStore` + adapter |

### Modified design docs (1)
| File | Change |
|------|--------|
| `design_docs/GLOSSARY.md` | Added wrapper_tool, procedure_spec, growth case, case runner terms |

### New test files (11)
| File | Tests |
|------|-------|
| `tests/builder/test_artifact.py` | 10 |
| `tests/builder/test_types.py` | 8 |
| `tests/builder/test_work_memory.py` | 11 |
| `tests/growth/test_case_runner.py` | 18 |
| `tests/growth/test_case_types.py` | 9 |
| `tests/growth/test_cases.py` | 10 |
| `tests/growth/test_gc1_integration.py` | 2 |
| `tests/growth/test_gc2_integration.py` | 9 |
| `tests/growth/test_wrapper_tool_adapter.py` | 50 |
| `tests/wrappers/test_store.py` | 19 |
| `tests/wrappers/test_types.py` | 13 |

### Modified test files (4)
| File | Change |
|------|--------|
| `tests/growth/test_contracts.py` | +79 lines (wrapper_tool contract tests) |
| `tests/growth/test_engine.py` | +13 lines (wrapper_tool engine integration) |
| `tests/growth/test_policies.py` | +21 lines (wrapper_tool + procedure_spec policy tests) |
| `tests/test_tool_modes.py` | +71 lines (registry unregister/replace tests) |

---

## Test Coverage Summary

| Module | Test file(s) | Test count |
|--------|-------------|------------|
| builder/types | test_types.py | 8 |
| builder/artifact | test_artifact.py | 10 |
| builder/work_memory | test_work_memory.py | 11 |
| wrappers/types | test_types.py | 13 |
| wrappers/store | test_store.py | 19 |
| growth/case_types | test_case_types.py | 9 |
| growth/cases | test_cases.py | 10 |
| growth/case_runner | test_case_runner.py | 18 |
| growth/wrapper_tool_adapter | test_wrapper_tool_adapter.py | 50 |
| growth/contracts (wrapper_tool) | test_contracts.py (delta) | ~15 |
| growth/policies (wrapper_tool) | test_policies.py (delta) | ~5 |
| growth/engine (wrapper_tool) | test_engine.py (delta) | ~3 |
| tools/registry (unregister/replace) | test_tool_modes.py (delta) | ~10 |
| **GC-1 integration** | test_gc1_integration.py | 2 |
| **GC-2 integration** | test_gc2_integration.py | 9 |
| **Total new/modified** | 15 test files | **~192** |
| **Total project** | all test files | **1495** |

---

## Commit History

| SHA | Description |
|-----|-------------|
| `2a5a7b2` | Phase 0: contract V1, glossary, GC-3 decision |
| `30026c8` | Phase 1: work memory substrate + bd feasibility spike |
| `77dfd76` | Phase 1 fix: complexity guard regressions |
| `2348a9a` | Phase 2: wrapper tool store, adapter, runtime wiring |
| `f19b861` | Phase 2 fix: split `_check_typed_io_validation` for complexity |
| `ea5d9db` | Phase 3: growth case catalog + runner + GC-1/GC-2 integration |
| `596260a` | Phase 3 fix: resolve G3 review findings F1-F4 |
