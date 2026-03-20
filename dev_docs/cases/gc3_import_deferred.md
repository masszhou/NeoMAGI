# GC-3 Decision: Import Protocol Deferred

- **Date**: 2026-03-18
- **Milestone**: P2-M1c Phase 0
- **Status**: deferred

## Decision

GC-3 (cross-agent skill/tool import protocol) 推迟，不纳入 P2-M1c acceptance criteria。

## Rationale

- 当前 import 协议尚未冻结；skill_spec 与 wrapper_tool 的跨 agent 共享边界仍未确定。
- P2-M1c 的核心闭环是 GC-1 (human-taught skill reuse) 和 GC-2 (skill → wrapper_tool promotion)，不依赖 import。
- ADR 0057 指导原则：先冻结难以后补的基础约束，import 协议属于可后续演化的 orchestration 层。
- 在 GC-1/GC-2 落地并积累运行证据后，再回来定义 import 边界更合适。

## Follow-up

- GC-3 的正式设计推迟到 P2-M2 或后续 milestone。
- 若 GC-1/GC-2 执行过程中发现 import 是硬依赖，可重新评估。

---

## bd Feasibility Checklist (Phase 1 Spike)

Phase 1 spike 需要验证 bd 作为 builder work memory 索引层的最小能力。以下为验收清单：

| # | Capability | Command | Expected | Verified |
|---|-----------|---------|----------|----------|
| 1 | 创建 issue | `bd create --title "..." --description "..." --json` | 返回 issue ID | |
| 2 | 更新 state | `bd update <id> --status <state> --json` | state 更新成功 | |
| 3 | 追加评论 | `bd comments add <id> "comment text"` | 评论持久化、可查询 | |
| 4 | 查询评论 | `bd comments <id> --json` | 返回评论列表 | |
| 5 | artifact path 引用 | 在 description/comment 中写入 `workspace/artifacts/<path>` | 可存可读、无截断 | |
| 6 | label 管理 | `bd label add <id> <label>` | label 附着成功 | |
| 7 | JSON 输出 | 所有命令 `--json` | 结构化输出、可程序化解析 | |

### Spike 验收标准

- 上述 7 项中至少 1-5 全部通过，spike 判定为 pass。
- 若 #3 (comments) 不可用，退化为 `artifact-first + bead-pointer-only` 模式（ADR 0055 fallback）。
- 若 #1 或 #2 不可用，spike 判定为 fail，需要替代索引方案。
