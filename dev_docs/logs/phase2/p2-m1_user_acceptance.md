# P2-M1 用户验收测试记录

> 对应测试指导：`design_docs/phase2/p2_m1_user_test_guide.md`

## 执行记录模板

每次执行时复制下方表格，填入日期和结果。多次执行时追加新表格。

---

### 2026-04-06 执行

环境：
- PG: running
- 是否执行了 reset-user-db: yes

**A 层：WebChat 手工测试**

| 用例 | 状态 | 备注 |
|------|------|------|
| T01 启动与基础对话 | PASS | |
| T02 soul_status | PASS | |
| T03 soul_propose (CLI) | PASS | |
| T03-webchat soul_propose (可选) | SKIP | CLI 路径已覆盖 |
| T03b 生成第二版本 | PASS | |
| T04 soul_rollback | PASS | 测试期间发现 rolled-back skill 未在 runtime 禁用，修复见 `517dce3` |
| T05 教学意图 + DB 验证 | PASS | 发现 OI-01: skill proposal 与 memory 双写导致观测串线 |
| T06 chat_safe 边界 | PASS | |

**B 层：受控回放测试**

| 用例 | 状态 | 备注 |
|------|------|------|
| T07 Skill Runtime e2e | PASS | |
| T08 GC-1 | PASS | OI-01 影响观测但不阻塞功能 |
| T09 GC-2 | PASS | |
| T10 Builder Work Memory | PASS | |
| T11 Wrapper Tool 启动恢复 | PASS | |

**产物检查**

| 检查项 | 状态 | 备注 |
|--------|------|------|
| 7.1 workspace artifacts | PASS | |
| 7.2 governance tables | PASS | |
| 7.3 bd issue 索引 | PASS | |

**测试期间修复**

- `517dce3` fix(agent): disable rolled-back skills in runtime — T04 期间发现 rollback 后 skill 仍在 runtime 活跃，Codex 协助修复

**Open Issues**

- OI-01: Skill Proposal Reuse 被 Memory 提前短路 — 详见 `design_docs/phase2/p2_m1_open_issues.md`

**结论**：PASS
