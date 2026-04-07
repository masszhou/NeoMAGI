---
doc_id: 019d66f0-d728-7c0a-b0ba-5831780f01f7
doc_id_format: uuidv7
doc_id_assigned_at: 2026-04-07T09:55:53+02:00
---
# P2-M1 Post Works P1: Multi-Session Threads — 验收通过

- Date: 2026-04-07
- Plan: `dev_docs/plans/phase2/p2-m1-post-works-p1_multi-session-threads_2026-04-06.md`
- Status: **accepted**

## 交付摘要

4 commits, 7 文件变更 (+1637 / -455), 41 frontend tests.

| Commit | 内容 |
|--------|------|
| `a578556` | feat: multi-session store + ThreadRail + event routing |
| `02bf000` | fix [P1]: disconnect 回收 in-flight request + [P2]: lastActivityAt 排序 |
| `e69420f` | fix [P2]: 断线标记 message/tool terminal state |
| `31f8563` | fix [P2]: tool call aborted 终态替代误导性 complete |

## 计划验收项对照

| 验收项 | 状态 |
|--------|------|
| 可创建至少两个不同 thread | pass |
| streaming 期间切换不取消其他 thread | pass |
| 后台完成后左侧 rail 有可见信号 | pass |
| 两个 thread 的 history 与 tool calls 不互相污染 | pass |
| active thread 不被其他 thread 全局 streaming 锁死 | pass |
| 首次进入新 UI 仍能看到 main 下既有历史 | pass |
| 刷新后 thread 列表与 active 选择恢复 | pass |

## Review Findings 及修复

共 3 轮 review，5 个 findings 全部修复：

1. **[P1] 断线不回收 in-flight request** — `_setConnectionStatus` 增加 `requestToSession` 清空 + `isStreaming` 复位
2. **[P2] thread 列表未按活动排序** — ThreadRail 改为 `lastActivityAt` 降序，持久化 `lastActivityAt`
3. **[P2] 断线后 message/tool 未进入 terminal state** — streaming message → `error`，running tool → terminal
4. **[P2] tool call 断线后误标 complete** — 新增 `aborted` 终态，UI 渲染中性灰色 "interrupted"

## 关键实现

- **Store**: `sessionsById` per-session 状态, `requestToSession` 事件路由, `pendingHistoryId` per-session history 匹配
- **ThreadRail**: 左侧 rail, New Thread, active 高亮, streaming/unread/aborted 指示
- **兼容性**: 默认 `main` thread 保留旧历史, 新 thread `web:{uuid}`
- **持久化**: `localStorage` 存 sessionOrder + activeSessionId + titles + lastActivityAt

## P2-M1 级 Open Issues（P1 scope 外，交叉引用）

- **OI-01 Skill Proposal Reuse 被 Memory 提前短路** — 详见 `design_docs/phase2/p2_m1_open_issues.md`
  - `teaching_intent` 同时写入 skill proposal 和 memory/daily notes；`PromptBuilder` 通过 memory 注入即可复现教学行为，不依赖 skill proposal `apply`
  - T08/T11 无法仅凭新 session 行为区分 skill 通路与 memory 通路
  - 不影响 P1 multi-session threads 验收，属于 P2-M1 skill/memory 边界的已知设计缺口
