# 0058-coding-mode-open-conditions

- Status: accepted
- Date: 2026-04-07
- Related: ADR 0025, ADR 0026

## 选了什么

- 开放 `coding` mode 的入口必须是 per-session、用户显式动作。
- `chat_safe` 继续作为默认 mode；`SESSION_DEFAULT_MODE` 继续只允许 `chat_safe`，不通过全局配置把所有新会话默认切到 `coding`。
- 模型无权自行切换 mode；不做基于请求内容的自动意图识别升级。
- `SessionManager.get_mode()` 应尊重已持久化的合法 per-session `coding` 值；异常、缺失或非法值仍 fail-closed 到 `chat_safe`。
- 开放 `coding` 前，必须提供明确的 per-session 写入路径，例如 `SessionManager.set_mode()` 与对应的显式用户触发入口。
- coding-only tools 仍必须通过 mode 暴露闸门与执行闸门保护；`chat_safe` 下 hallucinated coding tool call 必须被拒绝。

## 为什么

- ADR 0025 已确定 mode 切换权归用户，不归模型；本决议把“后续开放 coding”的条件具体化。
- per-session 切换能保留不同会话的安全边界，避免全局默认配置扩大 blast radius。
- 保持 `chat_safe` 默认值能让现有普通聊天路径继续 fail-closed。
- 尊重 DB 中合法 `coding` 值是让 coding-only tools 真正可达的最小运行时前提。
- 继续保留双闸门能避免 prompt 暴露与工具执行之间出现能力漂移。

## 放弃了什么

- 方案 A：允许 `SESSION_DEFAULT_MODE=coding`，把所有新会话默认切到 coding。
  - 放弃原因：全局扩大风险面，不符合默认安全路径。
- 方案 B：由模型或请求内容自动判断是否升级到 coding。
  - 放弃原因：不可预测，难以审计，违反 ADR 0025 的用户显式控制原则。
- 方案 C：只移除 M1.5 guardrail，不提供明确的 per-session 写入入口。
  - 放弃原因：会让运行态变成只能靠 DB 手工修改进入 coding，无法形成可用产品路径。
- 方案 D：把 coding tools 暴露给 `chat_safe`，仅靠工具内部拒绝高风险动作。
  - 放弃原因：暴露闸门与执行闸门会漂移，prompt 层也会误导模型。

## 影响

- P2-M1 Post Works P3 的实现计划不再需要让实现者决定 mode 治理策略，只需要按本 ADR 落地代码路径。
- `SessionSettings.default_mode` validator 应继续拒绝非 `chat_safe` 默认值。
- `SessionManager.get_mode()` 中的 M1.5 hard guardrail 应被移除或条件化为可尊重合法 per-session `coding` 值。
- 需要补齐 mode 写入、读取、暴露闸门、执行闸门和 `chat_safe` 负向测试。
