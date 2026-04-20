---
doc_id: 019dad17-5299-78e4-9b11-1e7057413959
doc_id_format: uuidv7
doc_id_assigned_at: 2026-04-21T00:51:20+02:00
---
# P3-M1 Phase 0 实现日志：Runtime Profile + Claude Provider

> 日期：2026-04-21
> 计划：`dev_docs/plans/phase3/p3-m1_daily-mvp_2026-04-20.md`（Slice A + Slice B）

## 实现总结

P3-M1 Phase 0 交付两个并行 Slice：Slice A 引入 `daily` / `growth_lab` runtime profile，让 daily 模式下冻结 evolution / skill / procedure 组件；Slice B 新增 `AnthropicModelClient`，支持 Claude provider 的 chat、streaming 和 tool calling。

### 新增文件 (3)

| 文件 | 说明 |
|------|------|
| `src/agent/anthropic_client.py` | AnthropicModelClient 实现：消息格式转换、streaming、tool calling、retry（从 model_client.py 拆分以满足复杂度门禁） |
| `tests/test_runtime_profile.py` | 20 个 Slice A 测试：RuntimeProfileSettings、ClaudeSettings、OpenAI key 可选、preflight C2/C6/C9/C11 profile-aware |
| `tests/test_anthropic_model_client.py` | 17 个 Slice B 测试：消息转换（flat + nested OpenAI 格式）、tool 定义转换、ModelMessage、streaming 事件归一化 |

### 修改文件 (7)

| 文件 | 变更 |
|------|------|
| `src/config/settings.py` | OpenAI api_key 改可选 (`=""`)、新增 `ClaudeSettings`、`RuntimeProfileSettings`（default `daily`）、`ProviderSettings` 允许 `claude`、`Settings` 增加 `claude` + `runtime` |
| `src/agent/model_client.py` | 新增 `ModelMessage` provider-neutral dataclass、`_openai_message_to_model_message` 转换、`ModelClient.chat_completion` 返回类型改为 `ModelMessage` |
| `src/gateway/app.py` | `_build_memory_and_tools` 按 profile 条件跳过 evolution/skill/procedure、provider registry 条件注册 OpenAI/Gemini/Claude、readiness endpoint profile-aware |
| `src/infra/preflight.py` | `run_preflight` / `run_readiness_checks` 默认 profile 从 `settings.runtime.profile` 读取、C2 识别 claude、C6 daily 下 soul_versions 可选、C9 daily 跳过、C11 daily 轻量 reconcile |
| `pyproject.toml` | 新增 `anthropic>=0.49.0` 依赖 |
| `.env_template` | 新增 `RUNTIME_PROFILE`、`CLAUDE_API_KEY`、`CLAUDE_MODEL`、`CLAUDE_MAX_TOKENS` |
| `tests/test_health_endpoints.py` | mock settings 增加 `runtime.profile` 字段、growth_lab profile 测试 soul_reconcile latched check |

### 关键设计决策

- **Daily profile 隔离**：`daily` 下不构建 EvolutionEngine / SkillStore / Resolver / Projector / Learner / ProcedureRuntime / GovernanceEngine，soul tools 不注册（已有 `evolution_engine=None` guard）
- **轻量 soul reconcile**：daily 下 C11 直接查 `soul_versions` 表 + 写文件，不构建完整 EvolutionEngine；表缺失或无 active version → WARN 不 FAIL
- **Provider optionality**：OpenAI api_key 改可选，支持 Claude-only 部署；registry 只注册 api_key 非空的 provider
- **ModelMessage**：provider-neutral 返回类型替代 `ChatCompletionMessage`，两个 client 都返回它
- **消息格式转换**：`_extract_tool_call_fields` 同时支持 flat `{"id","name","arguments"}` 和 nested `{"id","type":"function","function":{"name","arguments"}}` 格式，避免 replay 历史工具调用时丢失 name/arguments
- **复杂度拆分**：Anthropic 实现拆到独立 `anthropic_client.py`，转换函数拆成小 helper（`_extract_system`、`_extract_tool_call_fields`、`_parse_arguments`、`_convert_assistant_msg`、`_append_tool_result`、`_StreamAccumulator`），消除循环导入和全部 complexity guard regression

## Review Findings & Fixes

### Implementation Review (2 rounds)

**R1 (4 findings)**:

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| 1 | P1 | Claude 工具历史转换丢失 name/arguments（flat dict 读取，实际持久化是 nested OpenAI 格式） | `_extract_tool_call_fields()` 支持 nested `function.name/function.arguments`，新增回归测试 |
| 2 | P1 | Complexity guard 合并门禁失败（_convert_messages_for_anthropic 64 行/11 分支/8 嵌套等） | Anthropic 实现拆到 `anthropic_client.py`，转换函数拆成小 helper，baseline 刷新 |
| 3 | P2 | `run_preflight` 默认 profile=growth_lab 与 daily 默认运行时不一致 | 参数改为 `profile: str | None = None`，函数内回退到 `settings.runtime.profile` |
| 4 | P3 | `.env_template` 不暴露 Claude 和 daily profile 配置 | 同步模板 |

**R2 (2 findings)**:

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| 1 | P1 | Anthropic 直连导入触发循环依赖（model_client.py re-export → anthropic_client.py 尚未定义） | 删除 eager re-export，gateway/tests 直接从 anthropic_client 导入 |
| 2 | P1 | Complexity guard 仍有 4 个 regression（convert_messages nesting、response_to_model nesting、iter_stream branches/nesting） | dispatch dict 替换 if/elif、提取 _serialize_tool_use_input、_StreamAccumulator.process() 统一事件分发 |

## Commits

| Hash | 说明 |
|------|------|
| `9a5e088` | feat(config): implement P3-M1 Phase 0 — runtime profile + Claude provider |
| `db16206` | fix(agent): address Phase 0 review — complexity, tool history, preflight default |
| `1058e21` | fix(agent): resolve circular import and remaining complexity regressions |

## 测试

- 新增 **37 tests** (20 runtime profile + 17 anthropic client)
- 全量回归: **1978 non-integration passed**, 0 failed
- `just lint` 通过: ruff 0 errors, complexity guard 0 regressions
- Frontend: 41 passed
