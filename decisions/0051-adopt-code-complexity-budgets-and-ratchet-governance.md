# 0051-adopt-code-complexity-budgets-and-ratchet-governance

- Status: accepted
- Date: 2026-03-08

## 背景

- NeoMAGI 当前已有多处复杂度热点：`scripts/devcoord/service.py`、`scripts/devcoord/sqlite_store.py`、`src/agent/agent.py`、`tests/test_devcoord.py` 等文件已经明显超出“渐进披露上下文”和“快速定位代码”的可维护区间。
- 仅靠“重构时顺手优化”不足以对抗熵增。没有统一阈值和自动检查，新代码会继续向大文件、长函数、多分支和高嵌套滑坡。
- 但仓库已经存在较多存量债务；如果一次性把全仓强制到红线以内，会立即让日常开发失去可执行性。

## 选了什么

- 为 NeoMAGI 采用两层复杂度治理：
  - 目标值：`src/`、`scripts/` 默认追求 `单文件 <= 500`、`单函数 <= 30`、`嵌套 <= 3`、`分支 <= 3`。
  - 硬门禁：`src/`、`scripts/` 一旦出现 `单文件 > 800`、`单函数 > 50`、`嵌套 > 3`、`分支 > 6`，视为 block 级复杂度风险。
- `tests/` 采用放宽的文件级阈值：`单文件 <= 1200`；函数级红线仍沿用 `50 / 3 / 6`，避免大型测试 helper 持续恶化。
- `alembic/versions/` 这类迁移文件不纳入自动文件长度治理，避免把生成式/历史性产物混入日常复杂度门禁。
- 采用 ratchet 策略，而不是一次性清债：
  - `.complexity-baseline.json` 记录当前 block 级存量债务。
  - `just lint` 执行 `uv run python -m src.infra.complexity_guard check`，只阻止“新增或恶化”的 block 级问题。
  - `just complexity-report` 用于查看全仓 target/block 快照，`just complexity-baseline` 用于在完成一轮明确的治理后下调 baseline。
- `src.infra.complexity_guard` 的扫描范围保持固定：
  - 只扫描 git tracked 的 `src/`、`scripts/` 与测试路径下的 `*.py/*.ts/*.tsx/*.js/*.jsx`。
  - `alembic/versions/` 与其他路径默认忽略，不通过 override 文件扩展扫描范围。
- `.complexity-overrides.json` 只提供局部覆盖，而不是 inclusion list：
  - 当前仅支持 `skip_file_lines`，按 repo 相对路径跳过 `file_lines` 检查。
  - 它不会关闭 Python 的 `function_lines` / `function_branches` / `function_nesting` 检查。
- 当前自动检查覆盖范围分阶段落地：
  - 全部 tracked `*.py/*.ts/*.tsx/*.js/*.jsx` 文件都检查 file lines。
  - Python 文件额外检查 function lines / branches / nesting。
  - TypeScript / TSX / JS 的函数级治理暂不自动化，先通过 file-level 约束和人工 review 控制，后续再补充专用检查器。

## 为什么

- 复杂度预算本质上是熵增预算。没有数字化边界，就无法把“保持简单”落实为日常工程动作。
- 目标值与硬门禁分离，能同时满足两个诉求：
  - 设计时有明确的“理想形态”；
  - 现实里又不会因为存量历史债务让 CI 全面失效。
- ratchet 比“一次性大扫除”更符合项目当前阶段：
  - 先冻结坏状态，阻止继续变坏；
  - 再按热点文件逐步拆分，把 baseline 一轮轮压低。
- 将检查入口挂到 `just lint`，可以复用现有开发路径，不引入新的记忆负担。
- 明确说明“当前自动化只对 Python 做函数级检查”，可以避免规则写得过满、工具实现却跟不上，形成新的名实不符。

## 放弃了什么

- 方案 A：只写一段文档约定，不做自动检查。
  - 放弃原因：无法形成真实门禁，几轮迭代后约定会失效。
- 方案 B：立即对全仓启用无 baseline 的硬门禁。
  - 放弃原因：当前存量债务较多，会直接阻塞正常开发，治理本身会失去可执行性。
- 方案 C：继续只用 `ruff` / `mccabe` 等单一规则。
  - 放弃原因：它们只能覆盖部分复杂度维度，无法表达单文件长度和分层阈值。
- 方案 D：把 tests 与 scripts 完全排除在治理之外。
  - 放弃原因：复杂度热点恰好集中在这些目录，排除它们等于绕开主要问题。

## 影响

- 复杂度治理从“口头要求”升级为仓库级质量规则，后续重构和评审都要引用同一套阈值。
- `just lint` 现在同时承担 style lint 和复杂度回退保护；任何引入新 block 级复杂度债务的改动都会失败。
- `.complexity-baseline.json` 成为显式技术债台账；清债后必须同步刷新 baseline，确保治理持续收紧而非永久豁免。
- 后续应优先针对 block 热点创建和推进 issue，例如 `scripts/devcoord/service.py`、`scripts/devcoord/sqlite_store.py`、`src/agent/agent.py`、`tests/test_devcoord.py`。
