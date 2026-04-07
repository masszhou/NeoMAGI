---
doc_id: 019cf8bb-6e58-7941-96b7-10214caebe63
doc_id_format: uuidv7
doc_id_assigned_at: 2026-03-16T23:19:19+01:00
---
# 0054-growth-eval-contracts-immutable-and-object-scoped

- Status: accepted
- Date: 2026-03-16
- Note: 本 ADR 只定义 `P2-M1` growth eval 的治理原则与对象边界，不在本轮引入完整自治代码搜索系统，也不定义具体阈值或 benchmark 细节。

## 背景

- `P2-M1a` 已建立统一治理入口：`propose -> evaluate -> apply -> rollback`，并明确未接入对象必须 fail-closed。
- 当前 `soul` 已有最小 deterministic eval，但 NeoMAGI 还没有一套跨对象的 growth eval 口径。
- `P2-M1b` 将接入 `skill_spec`，如果不先固定评估契约边界，后续容易退回“每个对象各自定义 judge”的状态。
- `autoresearch` 的主要启示不是单一指标，而是：
  - 被优化对象和 judge / harness 分离；
  - keep / revert 规则先固定；
  - 不能通过修改评测器本身来“优化成绩”。

## 选了什么

- 将 `GrowthEvalContract` 视为一等治理对象。
- `GrowthEvalContract` 必须同时满足：
  - `object-scoped`
  - `versioned`
  - `immutable`
- 每个 growth object kind 都应绑定自己的 eval contract；不同对象不共享一个模糊的大评测面。
- 普通 proposal 可以修改对象本身，但不能与其 judge / harness 一起修改。
- contract change 必须走单独治理路径，不与普通 object proposal 混提。
- `raw code patch` 在 `P2-M1` 中不是 growth object；它只是：
  - implementation artifact
  - supporting evidence
  - promote 候选的实现材料
- `P2-M1` 的 canonical eval 结构固定为四层：
  - `Boundary gates`
  - `Effect evidence`
  - `Scope claim`
  - `Efficiency metrics`
- 四层结构的默认解释固定为：
  - `Boundary gates`：硬门槛，关注可回滚、接口清晰、依赖显式、隐藏耦合受控
  - `Effect evidence`：证明改动确实带来改善，至少要有固定 before / after cases；需要时可增加轻量 ablation
  - `Scope claim`：明确该改进声称的适用范围，如 `local` / `reusable` / `promotable`
  - `Efficiency metrics`：在质量达标后再比较 token、延迟、成本等效率指标，不单独决定 apply
- `immutable` 在工程上至少包含以下不变量：
  - proposal 不能修改自己所依赖的 judge / harness
  - 每次评测都必须绑定固定的 contract version
  - contract 升级不回写历史结论
  - keep / veto / rollback 规则必须在评测前固定

## 为什么

- 如果 `GrowthEvalContract` 不是一等对象，eval 很容易退化成“每个 adapter 自己决定做什么”，无法形成稳定治理面。
- `object-scoped` 比单一全局指标更适合 NeoMAGI：
  - `soul`、`skill_spec`、`wrapper_tool`、`procedure_spec` 面对的风险和证据类型不同；
  - 强行统一成一个分数会掩盖关键差异。
- `versioned` 是为了审计和可追溯：
  - 同一个 proposal 为什么 PASS / FAIL，必须能回答“它是按哪一版 contract 被判断的”。
- `immutable` 是为了避免 Goodhart 式漂移：
  - 如果对象和 judge 一起改，评测结果就不再可信。
- 将 contract change 与 object change 分开，可以保持 ownership 清晰，降低一次 proposal 的认知负担和 blast radius。
- 不把 `raw code patch` 提升为 growth object，可以避免 `P2-M1` 过早滑向“任意代码自我修改”框架。
- 四层结构可以把不同问题分开处理：
  - 先判断边界是否安全；
  - 再判断效果是否成立；
  - 再判断声称的范围是否合理；
  - 最后才比较效率。
- 把 `Efficiency metrics` 放在最后，可以防止系统只为了省 token 而牺牲质量、稳定性或长期可维护性。

## 放弃了什么

- 方案 A：继续维持“统一接口存在，但每个对象自行定义 judge”的隐式模式。
  - 放弃原因：难以形成稳定、可审计、可跨对象比较的治理口径。
- 方案 B：把 `raw code patch` 直接定义为新的 growth object kind。
  - 放弃原因：会把 `P2-M1` 过早推向无边界代码自我修改，扩大治理面和回归面。
- 方案 C：用一个统一单指标或 reward score 覆盖所有 growth object。
  - 放弃原因：不同对象的风险、效果和证据类型差异太大，单分数容易误导。
- 方案 D：允许普通 proposal 同时修改对象和 judge / harness。
  - 放弃原因：会破坏评测可信度，导致“改裁判来赢”而不是“改对象来变好”。
- 方案 E：把 token / cost 效率作为默认主 gate。
  - 放弃原因：效率是重要信号，但不应先于安全、效果和边界正确性。

## 影响

- 后续 `P2-M1b` 的 `skill_spec` onboarding 必须绑定明确的 object-scoped eval contract，而不是只写“schema 校验 + preconditions 检查”。
- `soul` 将被视为第一个正式 contract profile，而不只是历史特例。
- `wrapper_tool`、`procedure_spec`、`memory_application_spec` 即使暂未实现，也应先有 contract skeleton，避免后续重新争论 judge 面。
- 任何 future promote / demote 讨论，都应先回答：
  - 对象是什么
  - contract 是什么
  - judge 面是否独立
  - claim 的范围是什么
- 本 ADR 不决定：
  - 具体阈值
  - benchmark corpus
  - contract 的最终物理存储形态
  - runtime 如何执行全部 checks
