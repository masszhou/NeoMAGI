# P2-M4 Architecture（计划）

> 状态：planned  
> 对应里程碑：`P2-M4` 外部协作与动作表面扩展  
> 依据：`design_docs/phase2/roadmap_milestones_v1.md`、ADR 0047、ADR 0048

## 1. 目标

- 在不改变 NeoMAGI 核心身份与 runtime 契约的前提下，扩展外部协作表面与外部动作表面。
- 将 Slack / 群聊定位为协作与审批表面，而不是多 agent 的成立理由。
- 将浏览器 / 外部平台能力按“先读后写、先受控后放开”的顺序接入。
- 为后续真实工作流接入保留统一 channel adapter 与 approval / audit 语义。

## 2. 当前基线（输入）

- 当前已有 WebChat 与 Telegram 两个渠道。
- 多 agent 的 runtime 定义已明确为 execution-oriented，而不是多人格协作。
- 浏览器 / 外部平台操作尚未进入正式产品 runtime；Actionbook 目前更适合作为外部经验源。
- 对外部写动作，当前只有一般性的高风险边界，没有专门的产品级审批表面。

实现参考：
- `src/gateway/`
- `src/channels/telegram.py`
- `decisions/0003-channel-baseline-webchat-first-telegram-second.md`
- `decisions/0044-telegram-adapter-aiogram-same-process.md`

## 3. 复杂度评估与建议拆分

`P2-M4` 复杂度：**中高**。  
原因：它依赖 `P2-M1~M3` 的能力契约稳定，但自身更偏表面和审批集成。

建议拆成 2 个内部子阶段：

### P2-M4a：Read Surfaces & Collaboration Channels
- Slack / 类 Slack 表面
- 外部平台只读采集
- 通知 / 审批 / 状态可见性

### P2-M4b：Approved Write Surfaces
- 发帖 / 回复 / 外部写动作
- 显式审批
- 审计、停用、回滚路径

## 4. 目标架构（高层）

### 4.1 Channel Surface Plane

- 新渠道应继续采用 adapter 思路，而不是复制核心业务逻辑。
- Slack / 群聊价值优先体现在：
  - thread 协作
  - 状态同步
  - 审批 / 确认
  - 通知

### 4.2 External Action Surface Plane

- 外部动作建议按 3 级分类：
  - `read`
  - `draft`
  - `write`
- 其中：
  - `read` 可优先进入低风险路径
  - `draft` 作为用户审阅中间层
  - `write` 必须进入 approval / audit

### 4.3 Browser Skill Plane

- 浏览器能力不建议直接定义为新的 runtime primitive。
- 外部经验源（如 Actionbook）应优先进入：
  - browser skill object
  - capability-level surface
- 只有特别稳定、边界清晰的部分，才再继续 promote。

### 4.4 Approval / Audit Plane

- 所有外部写动作必须具备：
  - 显式用户授权
  - 审计记录
  - 停用 / 撤销路径
- 这层不能只依赖聊天语义，应接到 `Procedure Runtime` 或等价治理路径上。

### 4.5 Group Collaboration Plane

- 若进入群聊场景，重点是：
  - primary agent 与 worker 状态可见
  - 审批点可见
  - 结果可发布回主线程
- 不是“让多个长期人格在群里讨论”。

## 5. 边界

- In:
  - Slack / 等价协作表面候选。
  - 外部平台只读与草稿能力。
  - 外部写动作审批表面。
  - 浏览器 skill object 的外部经验接入。
- Out:
  - 不做广义 social automation。
  - 不做无审批自动发帖 / 自动运营 / 自动拉群。
  - 不把 Slack 群聊作为多人格产品方向的默认载体。
  - 不在前置 identity / procedure / memory 契约未稳定前铺太多新渠道。

## 6. 验收对齐（来自 roadmap）

- 用户可以在 Slack 或等价协作渠道里与多个 agent 进行受控协作。
- 外部平台的信息读取能力遵循与主系统一致的治理边界。
- 任意外部写动作都要求明确授权、可审计记录和清晰停用路径。
