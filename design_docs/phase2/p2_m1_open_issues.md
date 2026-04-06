# P2-M1 Open Issues

> 说明：`bd` 仍是 canonical issue tracker；本文件只记录 `P2-M1` 设计/验收层面的 root cause 摘要，避免问题背景散落在聊天记录中。

## OI-01 Skill Proposal Reuse 被 Memory 提前短路

- 现象：`T08` 中，即使 `skill_spec_versions` 里最新记录仍是 `status='proposed'`，新 session 也可能已经稳定表现出用户在 `T07` 教进去的固定格式。
- root cause：
  - `T07` 使用的教学语句同时命中了两条路径：
    - `teaching_intent` → 生成 `skill_spec` proposal，写入 `skill_spec_versions`
    - 普通记忆/笔记路径 → 写入 `workspace/memory/YYYY-MM-DD.md`，并进入 `memory_entries`
  - `PromptBuilder` 会在新 session 中直接注入 `[Recent Daily Notes]`，并按需注入 recalled memories；这两条 memory 路径都不依赖 skill proposal 被 `apply`
  - 因此，在 `skill_specs` / `skill_evidence` 仍为空时，模型也可能因为 memory 注入而复用这条格式经验
- 影响：
  - `T08/T11` 的观测会被 memory reuse 与 skill reuse 串线，无法仅凭“新 session 中是否出现固定结构”判断 skill proposal 是否已真正生效
  - 当前实现对 `skill` 与 `memory` 的硬冲突仲裁仍不完整；设计意图已定义，但 runtime 还没有把这层边界严格落地
