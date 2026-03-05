# NeoMAGI

[English](README.md) | [Deutsch](README_de.md)

NeoMAGI 是一个开源 personal agent 项目。

它的产品想法很直接：做一个能够跨时间保留记忆、代表用户信息利益、并且可以从商业模型 API 逐步迁移到更本地化、更可控模型栈的 agent。

## 产品定位

NeoMAGI 不想做一个通用的 chatbot 外壳。

它的目标方向是一个长期协作型的伙伴式 AI，核心特征是：
- 能持续记住有用的上下文
- 以用户利益为中心，而不是平台激励为中心
- 能在可控、可审计的前提下扩展能力
- 保留从商业 API 平滑迁移到本地模型的现实路径

## 原则

- 考虑充分，实现极简。
- 优先做最小可用闭环。
- 避免不必要的抽象和依赖膨胀。
- 把治理、回滚、作用域边界当作产品能力，而不只是工程细节。

## 当前状态

这个仓库仍处在较早期的产品构建阶段。

Phase 1 的基础能力已经大体完成，并作为归档参考保留下来。Phase 2 的重点是减少历史上下文负担，明确下一章产品方向，并从基础设施阶段逐步转向更显式的成长与能力进化模型。

这个 README 会刻意保持高层，不承担完整实现契约的职责。它更像项目介绍，而不是详细设计说明。

## 文档入口

- 项目设计入口：`design_docs/index.md`
- Phase 1 归档：`design_docs/phase1/index.md`
- 运行时 prompt 模型：`design_docs/system_prompt.md`
- 记忆原则：`design_docs/memory_architecture_v2.md`
- 仓库治理：`AGENTS.md`、`CLAUDE.md`、`AGENTTEAMS.md`

## 说明

项目仍在持续迭代中。

随着产品方向进一步收敛，以及更多系统能力经过真实使用验证，名称、边界和实现细节都还可能继续调整。
