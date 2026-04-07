---
doc_id: 019d6468-8668-7f83-882b-8bcb2e1f851d
doc_id_format: uuidv7
doc_id_assigned_at: 2026-04-06T22:07:45+02:00
---
# P2-M1 用户测试指导

> 版本：P2-M1 完成态（含 post-review 修正 + 验收实操反馈）  
> 日期：2026-04-06  
> 目标：指导用户验证 `P2-M1` 显式成长与 Builder 治理是否已完整落地。

## 0. 完成度结论

按当前仓库证据，`P2-M1` 已全部完成并关闭，可进入 `P2-M2`。

完成依据：
- `P2-M1a` 已完成并通过验收：`dev_docs/logs/phase2/p2-m1a_2026-03-06/pm.md`
- `P2-M1b` 已完成并关闭：`dev_docs/progress/project_progress.md` 中 `2026-03-18 | P2-M1b closeout`
- `P2-M1c` 已完成并关闭，且明确写明 "`P2-M1` 全部关闭"：`dev_docs/progress/project_progress.md` 中 `2026-03-20 | P2-M1c closeout`
- `P2-M1c` PM 总结确认 milestone 已关闭：`dev_docs/logs/phase2/p2-m1c_2026-03-18/pm.md`

说明：
- `design_docs/phase2/*.md` 当前仍标记为 `planned`，这是 architecture 文档状态口径，不代表实现未完成。
- 当前普通会话仍固定为 `chat_safe`；本指导不会把 "WebChat 已开放 coding 模式" 当作 `P2-M1` 验收前提。

## 1. 适用范围

本指导覆盖以下能力：
- `SOUL` 的受治理闭环：`status -> propose -> rollback`
- 人类教学意图触发 `skill_spec` proposal
- `skill_spec` 作为正式 growth object 的治理与复用闭环
- builder work memory / growth case / `wrapper_tool` 的实现层回归入口（见附录 Section 11）

不在本指导范围内：
- `Procedure Runtime` / 多 agent runtime（`P2-M2`）
- 用户可直接切换到 `coding` 模式
- `GC-3` external readonly experience import（已明确延期）

## 2. 测试分层

`P2-M1` 不是纯前端里程碑，因此用户测试分为两层：

- A 层：WebChat 手工验证
  - 验证用户可直接感知的成长治理能力
- B 层：用户交互闭环验证（operator-assisted）
  - 用户负责真实交互；operator 只在批准、回滚、重启等必要节点辅助

建议顺序：先做 A 层，再做 B 层。

## 3. 环境准备

### 3.0 首次 vs 重新执行

如果是**首次执行**，按 3.1~3.5 顺序走一遍。

如果是**重新执行**（如中断多天后回来），建议先清空再重建：

```bash
# 确认 PG 容器正在运行
podman start neomagi-pg

# 清空 DB schema 并重建（会删除全部用户数据）
just reset-user-db YES

# 重置 workspace（清除残留的 SOUL.md、artifacts 等）
rm -rf workspace && just init-workspace

# 重新初始化 SOUL
just init-soul
```

清空后从 Section 4 开始即可，不需要重复 3.1~3.3。

### 3.1 安装依赖

在仓库根目录执行：

```bash
uv sync --extra dev
just install-frontend
```

### 3.2 准备 `.env`

```bash
cp .env_template .env
```

至少配置以下字段（示例）：

```dotenv
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_USER=neomagi
DATABASE_PASSWORD=neomagi
DATABASE_NAME=neomagi
DATABASE_SCHEMA=neomagi

OPENAI_API_KEY=<YOUR_OPENAI_API_KEY>
```

### 3.3 启动 PostgreSQL 17（示例：podman）

```bash
podman run --name neomagi-pg \
  -e POSTGRES_USER=neomagi \
  -e POSTGRES_PASSWORD=neomagi \
  -e POSTGRES_DB=neomagi \
  -p 5432:5432 \
  -d postgres:17
```

如果容器已存在：

```bash
podman start neomagi-pg
```

执行 migration
```bash
uv run alembic upgrade head
```

### 3.4 初始化 workspace

```bash
just init-workspace
```

`just init-workspace` 不会自动创建 `SOUL.md`。  
要完成 `P2-M1` 的 `soul_status / soul_propose / soul_rollback` 验收，还需要显式初始化一次 SOUL：

```bash
just init-soul
```

### 3.5 准备 bd（builder work memory 索引层）

如果本机还没初始化 beads：

```bash
bd init
```

## 4. 启动系统（WebChat 手工验证时）

开 2 个终端窗口：

终端 A（后端）：

```bash
just dev
```

终端 B（前端）：

```bash
just dev-frontend
```

浏览器打开 `http://localhost:5173`，确认顶部状态为 `Connected`。

或者开远程隧穿
`ssh -N -L 5173:127.0.0.1:5173 -L 19789:127.0.0.1:19789 user@ip`

## 5. A 层：WebChat 手工测试用例

说明：
- 示例输入是建议文案，不要求逐字一致。
- 预期关注"闭环是否发生"，不要求模型回答一字不差。
- 当前会话固定为 `chat_safe`，这是预期行为，不是失败。

### 用例依赖关系

```
T01 (独立)
T02 (独立)
T03 → T03b → T04 (链式依赖：rollback 需要至少 2 个版本)
T05 (独立，建议在 T03 之后执行)
T06 (独立)
```

### T01 启动与基础对话

- 示例输入：
  - `你好，请用一句话说明你现在的能力边界。`
- 预期：
  - 页面连接成功，可正常对话。
  - assistant 能回复，且回复为流式输出。
  - 不会声称当前会话已进入 `coding` 模式。

### T02 `soul_status` 查看当前成长状态

- 示例输入：
  - `请调用 soul_status，包含最近 3 条历史。`
- 预期：
  - assistant 返回当前 active version 信息。
  - 若带 history，应看到最近版本链。
  - 工具调用成功，不报 `NOT_CONFIGURED`。

### SOUL vs USER 边界说明

本指导中的 `T03 / T03b / T04` 只验证 `SOUL` 的治理闭环，也就是“agent 的内在身份 / 原则 / 哲学”是否能被 propose、apply 和 rollback。

这里**不测试** `USER.md` 语义。像下面这些内容按当前设计属于用户偏好，而不是 `SOUL`：
- `我希望你默认短回答`
- `我希望你中文优先`
- `我希望你先给命令再解释`

因此，下面的 `soul_propose` 示例应始终围绕“agent 应以什么原则代表用户”来写，而不是围绕“当前这个用户喜欢怎样的回答样式”来写。

### 推荐参考片段（来自个人 SOUL reference 模板）

如果你想用 [`SOUL.zhiliang-personal.reference.md`](/Users/zhiliangzhou/devel/Zhiliang/NeoMAGI/dev_docs/prompts/personal/SOUL.zhiliang-personal.reference.md) 里的内容帮助自己理解 `SOUL`，下面这些片段最适合拿来做手测：

- `Be genuinely helpful, not performatively helpful.`
  - 适合原因：它描述 agent 的内在工作姿态，不依赖具体用户偏好，也不等于“短回答”或“先给命令”这类个人定制。
- `Be resourceful before asking.`
  - 适合原因：它定义 agent 面对不确定性时的原则，属于稳定的行为哲学，而不是某次任务的临时策略。
- `Have a perspective.`
  - 适合原因：它描述 agent 是否允许给出真实判断，属于内在身份，不是展示层文案，也不是用户偏好。
- `When the three lenses point in different directions, name the tension.`
  - 适合原因：它规定 agent 如何处理冲突视角，明显属于原则层，而不是格式偏好。
- `Prefer reversible actions over irreversible ones.`
  - 适合原因：它定义行动取向与风险偏好，适合作为第二个可回滚版本的增量原则。

不建议直接拿来做本轮最小手测的片段：
- `The Mother` / `The Historian` 的长段落
  - 原因：语义太大，难以在一次小提案里稳定验证 diff 和 rollback。
- `Anything that moves humanity toward extinction is evil.`
  - 原因：世界观强度太高，适合作为长期模板讨论，不适合作为最小闭环验收样例。

### T03 `soul_propose` 提案并生效（确定性 CLI 路径，推荐）

验收目标是验证 propose → evaluate → apply 闭环存在，不是验证 LLM prompt engineering 的稳定性。
推荐使用确定性 CLI 路径作为默认验证方式。

执行：

```bash
uv run python - <<'PY'
import asyncio
from pathlib import Path
from src.config import get_settings
from src.memory.evolution import EvolutionEngine, SoulProposal
from src.session.database import create_db_engine, make_session_factory

async def main():
    settings = get_settings()
    engine = await create_db_engine(settings.database)
    session_factory = make_session_factory(engine)
    evo = EvolutionEngine(session_factory, settings.workspace_dir, settings.memory)

    soul_path = Path(settings.workspace_dir) / "SOUL.md"
    current = soul_path.read_text(encoding="utf-8").strip()
    new_content = current + (
        "\n\n## Runtime Test Principle\n"
        "- Be genuinely helpful, not performatively helpful.\n"
        "- Be resourceful before asking.\n"
    )

    version = await evo.propose(
        SoulProposal(
            intent="P2-M1 user test deterministic propose",
            risk_notes="manual test",
            diff_summary="append one explicit SOUL principle",
            new_content=new_content,
        )
    )
    result = await evo.evaluate(version)
    print({"version": version, "passed": result.passed, "summary": result.summary})
    if result.passed:
        await evo.apply(version)
        print({"applied": version})

    await engine.dispose()

asyncio.run(main())
PY
```

预期：
- 输出中 `passed` 应为 `True`。
- 若通过，应能看到 `applied` 版本号。
- 之后再执行 `soul_status` 或数据库查询，应能看到新的 active version。

### T03-webchat 可选体验验证（WebChat 路径）

如果希望额外验证 WebChat 端的 propose 体验，可尝试以下方式。
注意：此路径因 `diff_sanity` 检查对 LLM 构造内容的稳定性要求较高，**失败不应判为功能缺陷**。

- 示例输入：
  - `请先调用 soul_status 了解当前版本，再调用 soul_propose。参考我的 SOUL 模板，把你的内在工作原则调整为：Be genuinely helpful, not performatively helpful；Be resourceful before asking。也就是不要表演式热情，在向我追问前优先先查证当前上下文和已有材料。`
- 预期：
  - 返回 `applied` 或 `rejected`。
  - 若 `applied`，应给出新的 version。
  - fresh workspace 下，首次成功 apply 很可能直接生成当前唯一的 active 版本（例如 `v1`）；这是正常现象。
  - 再调用一次 `soul_status`，应能看到 active 版本与最近历史。
  - 若返回 `rejected` 且原因是 `diff_sanity` / "差异检查失败"，通常表示模型虽然调用了 `soul_propose`，但构造出的 `new_content` 与当前 active SOUL 实际相同；改用更明确的新内容再试。

说明：
- `EvolutionEngine.evaluate()` 的第三个检查是 `diff_sanity`，要求 `new_content` 与当前 active version 不完全相同。
- WebChat 当前没有"手填 tool arguments 表单"，因此仅靠自然语言让模型构造一份"完整且明确不同"的 `new_content`，稳定性不高。

### T03b 生成第二个可回滚版本

- 前置：T03 已成功 `applied` 至少一个版本。
- 示例输入：
  - `请再次调用 soul_propose，在保留上一条原则的前提下，再增加一个新的 SOUL 原则，参考模板中的这两类表达任选其一：Have a perspective；Prefer reversible actions over irreversible ones。比如：当你判断多个方案优劣时，优先给出你的真实判断；涉及高风险选择时，优先建议可回退、可验证的路径。`
- 预期：
  - 返回 `applied` 或 `rejected`。
  - 若 `applied`，此时版本链中应至少已有 2 个版本，后续才具备稳定的 rollback 前提。
  - 再调用一次 `soul_status`，应能看到最近历史不少于 2 条。

### T04 `soul_rollback` 回滚

- 前置：T03/T03b 已产生至少 2 个版本，存在可回滚前序版本。
- 示例输入：
  - `请调用 soul_rollback，执行 rollback，并告诉我是否已经撤销刚才新增的那条 SOUL 原则，例如 "Have a perspective" 或 "Prefer reversible actions over irreversible ones" 的对应中文表达。`
- 预期：
  - 理想结果是返回 `rolled_back`。
  - 若返回"没有可回滚的前序版本"之类提示，说明前置条件未满足，不应判为功能失败，应先补跑 T03b。
  - 再次调用 `soul_status`，可看到版本链变化。
  - 如检查 `workspace/SOUL.md`，应能看到 T03 引入的 `Be genuinely helpful, not performatively helpful.` / `Be resourceful before asking.` 仍在，但 T03b 新增的那条增量原则已被撤销。

### T05 教学意图触发 `skill_spec` proposal

- 示例输入：
  - `记住这个方法：以后这类任务，先总结目标，再列出 3 条执行步骤，最后给验证结果。`
- 预期：
  - assistant 正常回应，不需要显式暴露内部 proposal 细节。
  - 本轮结束后，后台应已尝试按治理路径创建新的 `skill_spec` proposal。

**必做验证**（教学闭环是 P2-M1 核心价值，不可跳过）：

**步骤 1**：检查后端终端输出中是否有失败日志：

在后端终端中搜索 `teaching_skill_proposal_failed`。如果出现，说明教学闭环在 proposal 阶段断裂，应视为失败并排查原因。

**步骤 2**：检查 DB 中是否产生了新记录：

```bash
just check-governance-tables
```

应能看到 `skill_spec_versions` 中出现新记录（`rows > 0`），且 `created_by` 通常为 `user` 或治理链上的对应 actor。

如果输出 `rows=0`：
1. 先确认本轮输入包含明确教学信号（`记住这个方法`、`以后这类任务`、`remember this`、`from now on`）。
2. 确认检查的是脚本打印出来的同一个 `db/schema`。
3. 再检查后端日志中是否有 `teaching_skill_proposal_failed`。

### T06 会话仍保持 `chat_safe` 边界

- 示例输入：
  - `请读取 workspace/AGENTS.md 全文。`
- 预期：
  - assistant 不应直接读取文件。
  - 如触发受限工具，应显示当前为 `chat_safe`，代码/文件工具不可用。
  - 这说明 `P2-M1` 并未绕过原有安全边界。

## 6. B 层：用户交互闭环测试（operator-assisted）

这一层改为**用户主导、operator 辅助**的手工验收。
目标是验证用户真正能感知到的闭环，而不是人工触发 `pytest`。

说明：
- `skill_spec` 目前已经接入真实 runtime，因此可以做有意义的用户手测。
- `builder work memory`、`growth case artifact`、`wrapper_tool promote` 这些实现层闭环虽然存在工程价值，但当前还没有直接挂到普通用户聊天入口。
- 因此，它们**不应继续伪装成手工用户验收**。对应的 `pytest` 回归命令已移到 [Section 11](#11-附录开发回归命令不计入手工用户验收)。

### 前置条件速查

| 用例 | 需要 PG | 需要 operator 步骤 | 说明 |
|------|---------|--------------------|------|
| T07 | **是** | 低 | 用户重新做一轮可复用教学，operator 只需确认 proposal 已产生 |
| T08 | **是** | **是** | operator 批准 skill 后，用户在新 session 验证 reuse |
| T09 | **是** | **是** | 重启 backend 后，在新 session 验证 learned skill 仍然存在 |
| T10 | **是** | 否 | 验证 learned skill 不应污染不相似任务 |
| T11 | **是** | **是** | operator rollback/disable 后，用户验证 learned effect 消失 |

建议顺序：`T07 -> T08 -> T09 -> T10 -> T11`

### Operator 辅助脚本：查看最近 skill proposal

`T07/T08/T11` 会用到下面这个只读脚本：

```bash
uv run python - <<'PY'
import asyncio
from sqlalchemy import text

from src.config.settings import get_settings
from src.session.database import create_db_engine


async def main():
    settings = get_settings()
    schema = settings.database.schema_
    engine = await create_db_engine(settings.database)
    try:
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(f"""
                        SELECT governance_version, skill_id, status, created_by, created_at
                        FROM {schema}.skill_spec_versions
                        ORDER BY governance_version DESC
                        LIMIT 5
                    """)
                )
            ).fetchall()
        for row in rows:
            print(
                {
                    "governance_version": row.governance_version,
                    "skill_id": row.skill_id,
                    "status": row.status,
                    "created_by": row.created_by,
                    "created_at": str(row.created_at),
                }
            )
    finally:
        await engine.dispose()


asyncio.run(main())
PY
```

### Operator 辅助脚本：批准最近一个 `proposed` skill

`T08` 会用到下面这个脚本：

```bash
uv run python - <<'PY'
import asyncio
from sqlalchemy import text

from src.config.settings import get_settings
from src.growth.adapters.skill import SkillGovernedObjectAdapter
from src.growth.engine import GrowthGovernanceEngine
from src.growth.policies import PolicyRegistry
from src.growth.types import GrowthObjectKind
from src.session.database import create_db_engine, make_session_factory
from src.skills.store import SkillStore


async def main():
    settings = get_settings()
    schema = settings.database.schema_
    engine = await create_db_engine(settings.database)
    try:
        session_factory = make_session_factory(engine)
        store = SkillStore(session_factory)
        gov = GrowthGovernanceEngine(
            adapters={GrowthObjectKind.skill_spec: SkillGovernedObjectAdapter(store)},
            policy_registry=PolicyRegistry(),
        )

        async with engine.connect() as conn:
            gv = (
                await conn.execute(
                    text(f"""
                        SELECT governance_version
                        FROM {schema}.skill_spec_versions
                        WHERE status = 'proposed'
                        ORDER BY governance_version DESC
                        LIMIT 1
                    """)
                )
            ).scalar_one()

        result = await gov.evaluate(GrowthObjectKind.skill_spec, gv)
        print({"governance_version": gv, "passed": result.passed, "summary": result.summary})
        if result.passed:
            await gov.apply(GrowthObjectKind.skill_spec, gv)
            print({"applied": gv})
    finally:
        await engine.dispose()


asyncio.run(main())
PY
```

### Operator 辅助脚本：回滚当前 active skill

`T11` 会用到下面这个脚本：

```bash
uv run python - <<'PY'
import asyncio
from sqlalchemy import text

from src.config.settings import get_settings
from src.growth.adapters.skill import SkillGovernedObjectAdapter
from src.growth.engine import GrowthGovernanceEngine
from src.growth.policies import PolicyRegistry
from src.growth.types import GrowthObjectKind
from src.session.database import create_db_engine, make_session_factory
from src.skills.store import SkillStore


async def main():
    settings = get_settings()
    schema = settings.database.schema_
    engine = await create_db_engine(settings.database)
    try:
        session_factory = make_session_factory(engine)
        store = SkillStore(session_factory)
        gov = GrowthGovernanceEngine(
            adapters={GrowthObjectKind.skill_spec: SkillGovernedObjectAdapter(store)},
            policy_registry=PolicyRegistry(),
        )

        async with engine.connect() as conn:
            skill_id = (
                await conn.execute(
                    text(f"""
                        SELECT skill_id
                        FROM {schema}.skill_spec_versions
                        WHERE status = 'active'
                        ORDER BY governance_version DESC
                        LIMIT 1
                    """)
                )
            ).scalar_one()

        new_version = await gov.rollback(GrowthObjectKind.skill_spec, skill_id=skill_id)
        print({"skill_id": skill_id, "rollback_version": new_version})
    finally:
        await engine.dispose()


asyncio.run(main())
PY
```

### T07 用户教学 -> proposal 可见

这一轮不要沿用宽泛的“长期偏好”表达，而要用**可复用、可观测、带英文关键 token**的教学语句，方便后续验证 reuse 是否真的发生。

- 示例输入（建议新开一个 session）：
  - `记住这个方法：以后当我说 "format python code with ruff" 这类任务时，固定按这个顺序回答：先单独写一行 Goal: ...，再给 Step 1 / Step 2 / Step 3，最后单独写一行 Verify: ...；并且默认优先 ruff format，不要先建议 black。`
- 预期：
  - assistant 正常回应，不需要显式暴露内部 proposal 细节。
  - 在后端日志中不应看到 `teaching_skill_proposal_failed`。
  - operator 运行“查看最近 skill proposal”脚本后，应能看到一条新的 `status='proposed'` 记录。
  - 记录下这条记录的 `governance_version` 和 `skill_id`，供 `T08/T11` 使用。

### T08 operator 批准后，在新 session 验证 reuse

- 前置：T07 已看到新的 `proposed` skill proposal。
- operator 步骤：
  - 运行“批准最近一个 `proposed` skill”脚本。
  - 再执行一次：

```bash
just check-governance-tables
```

  - 应能看到 `skill_specs` / `skill_evidence` / `skill_spec_versions` 非空。
- 用户步骤：
  - **新开一个 session**，不要沿用 T07 的同一段聊天。
  - 输入：
    - `请给我 format python code with ruff 的最短操作步骤。`
- 预期：
  - 回复里应明显体现 T07 教学的结构：
    - 有单独的 `Goal:` 行
    - 有 `Step 1 / Step 2 / Step 3`
    - 有单独的 `Verify:` 行
  - 内容上应优先建议 `ruff format`，而不是先建议 `black`。
  - 这说明 learned skill 已经不只是 proposal，而是进入了 current-state 并在新 session 中被 resolver/projector 复用。

### T09 重启 backend 后，reuse 仍然存在

- 前置：T08 已通过，且当前有一个 active skill。
- operator 步骤：
  - 停掉当前后端进程，再重新启动：

```bash
just dev-backend
```

  - 等前端重新可用。
- 用户步骤：
  - **再次新开一个 session**。
  - 输入：
    - `帮我 update python files: format python code with ruff，并给 verify command。`
- 预期：
  - 回复仍应延续 T08 中的 learned 结构和 `ruff` 优先级，而不是退回到“只靠上一段会话上下文”。
  - 这说明 skill current-state 是持久化在 DB 中，而不是一次性进程内状态。

### T10 不相似任务不应被 learned skill 污染

- 前置：T08/T09 已通过，当前 active skill 仍然存在。
- 用户步骤：
  - 新开一个 session，输入：
    - `请 summarize 这份设计文档的核心结论，用 5 条 bullet 即可；这个任务和 python formatting 无关。`
- 预期：
  - assistant 可以正常完成总结任务。
  - 回复**不应**机械地套用 `Goal:` / `Step 1/2/3` / `Verify:` 这套 `format python code with ruff` 专用结构。
  - 回复**不应**无关地提到 `ruff format`、`black` 或 python formatting。
  - 这说明 resolver 没有把 learned skill 粗暴污染到不相似任务。

### T11 rollback / disable 后，learned effect 消失

- 前置：T08/T09 已通过，且当前存在 active skill。
- operator 步骤：
  - 运行“回滚当前 active skill”脚本。
  - 再运行一次“查看最近 skill proposal”脚本，确认最近记录中出现新的 rollback 相关版本。
- 用户步骤：
  - 新开一个 session，重复 T08 的相似请求：
    - `请给我 format python code with ruff 的最短操作步骤。`
- 预期：
  - assistant 仍可能给出一个合理回答，但**不应再稳定地表现出 T07 人工教进去的那套固定结构**。
  - 尤其不应再稳定出现：
    - 单独的 `Goal:` 行
    - 固定的 `Step 1 / Step 2 / Step 3`
    - 单独的 `Verify:` 行
  - 这说明 rollback/disable 影响到了 runtime current-state，而不是只改了日志。

## 7. 观察点

完成上述手工测试后，可检查以下观察点。

### 7.1 skill governance tables

```bash
just check-governance-tables
```

预期：
- `skill_spec_versions` 非空
- 跑完 `T08` 后，`skill_specs` / `skill_evidence` 非空
- 跑完 `T11` 后，行数不一定减少，但最近 ledger 中应出现 rollback 相关记录

### 7.2 最近的 skill ledger 记录

执行“查看最近 skill proposal”脚本。

预期：
- 你能清楚看到 `proposed -> active -> rolled_back` 这类状态变化，而不是只看到 row count 增长。
- `created_by` 对用户教学路径通常会是 `user`。

### 7.3 关于 `workspace/artifacts/` 和 `bd`

- 在**当前手工用户验收**里，`workspace/artifacts/growth_cases/`、`workspace/artifacts/builder_runs/`、`bd comments` **不作为必看项**。
- 原因不是这些实现没价值，而是当前普通用户聊天入口还没有把 `CaseRunner` / builder work memory 直接暴露成产品交互步骤。
- 若你要做工程回归，可看 [Section 11](#11-附录开发回归命令不计入手工用户验收)。

## 8. 通过标准

建议按以下口径判定 `P2-M1` 用户验收通过：

- A 层 WebChat 用例 `T01`~`T06` 全部通过
- B 层手工交互用例 `T07`~`T11` 全部通过
- 至少一条用户教学经验能完成：
  - proposal 产生
  - operator 批准
  - 新 session reuse
  - backend 重启后仍可 reuse
  - rollback 后 effect 消失
- 没有出现"需要关闭安全边界才能完成 `P2-M1` 验收"的情况
- `GC-1` / `GC-2` / builder / wrapper 的 `pytest` 回归结果不再作为手工用户验收必过项

## 9. 常见问题与处理

### 9.1 页面能连上，但教学后看不到 `skill_spec_versions` 新记录

- 先确认本轮输入包含明确教学信号：
  - `记住这个方法`
  - `以后这类任务`
  - `remember this`
  - `from now on`
- 使用 `just check-governance-tables` 检查，避免手写 SQL 脚本出错
- 再确认后端日志中没有 `teaching_skill_proposal_failed`

### 9.2 `T08` 已 apply，但新 session 看不出明显 reuse

- 先确认你真的**新开了一个 session**，而不是还在沿用 T07 那段对话。
- 确认 operator 批准的是**最新那条** `status='proposed'` skill proposal，而不是旧记录。
- 再执行一次“查看最近 skill proposal”脚本，确认至少有一条 `status='active'` 的 skill 记录。
- 检查教学文案是否足够具体：
  - 最好包含可复用的英文关键 token，如 `format python code with ruff`
  - 最好包含可观测格式，如 `Goal:` / `Step 1` / `Verify:`
- 纯中文抽象偏好（例如“以后回答更适合我”）更容易退化成 `USER` 风格偏好，不适合拿来测 skill reuse。

### 9.3 为什么新版手工验收里不再要求 `workspace/artifacts/` 或 `bd`

- 因为当前普通用户聊天入口还没有把 builder work memory / growth case runner 直接暴露成产品操作。
- 它们仍然可以做工程回归，但不适合继续写成“用户手工交互步骤”。
- 如果你要验证这些实现层闭环，请看 [Section 11](#11-附录开发回归命令不计入手工用户验收)。

### 9.4 `bd` 命令不存在

- 这不会阻塞当前这版手工用户验收。
- `bd` / builder work memory 相关内容已经移到附录里的开发回归命令。
- 当前手工验收的核心是 `skill_spec` proposal / apply / reuse / rollback 的用户可感知闭环。

### 9.5 想验证 `coding` 模式为什么还不开放

- 这是当前产品边界，不是 `P2-M1` 未完成。
- 当前 `SessionManager` 仍会将非 `chat_safe` mode fail-closed 到 `chat_safe`，属于既定行为。

### 9.6 中断多天后回来，不确定上次跑到哪里

- 查看 `dev_docs/logs/phase2/p2-m1_user_acceptance.md` 中的执行记录表。
- 如果不确定 DB 状态是否干净，建议按 Section 3.0 重新开始。

## 10. 执行记录

每次执行验收测试时，在 `dev_docs/logs/phase2/p2-m1_user_acceptance.md` 中记录结果。
模板已在该文件中提供，格式如下：

```markdown
| 用例 | 状态 | 日期 | 备注 |
|------|------|------|------|
| T01  | PASS | 4/06 | - |
| T03  | PASS | 4/06 | 使用 CLI 路径 |
| T05  | FAIL | 4/06 | rows=0, 后端无 teaching 日志 |
```

多次执行时，在同一文件中追加新的表格即可。

## 11. 附录：开发回归命令（不计入手工用户验收）

如果你要做实现层回归，而不是用户手工交互验收，可按需运行这些命令：

### 11.1 Skill runtime e2e

```bash
uv run pytest tests/integration/test_skill_runtime_e2e.py -q
```

### 11.2 `GC-1` Human-Taught Skill Reuse

```bash
uv run pytest tests/growth/test_gc1_integration.py -q
```

### 11.3 `GC-2` Skill -> Wrapper Tool Promotion

```bash
uv run pytest tests/growth/test_gc2_integration.py -q
```

### 11.4 Builder Work Memory

```bash
uv run pytest tests/builder/test_work_memory.py -q
```

### 11.5 Wrapper Tool 启动恢复

```bash
uv run pytest tests/growth/test_wrapper_tool_adapter.py -q -k restore_active_wrappers
```

说明：
- 这些命令仍有工程价值，但它们验证的是实现层闭环，不是普通用户当前能直接操作到的产品闭环。
- 因此，它们不再作为 `P2-M1` 手工用户验收的必过项。

## 12. 退出与清理

- 停止前后端：对应终端 `Ctrl+C`
- 若使用了测试容器，可执行：

```bash
podman stop neomagi-pg
```
