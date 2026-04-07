---
doc_id: 019cc283-4608-7be4-8d4b-555b7306df57
doc_id_format: uuidv7
doc_id_assigned_at: 2026-03-06T10:38:29+01:00
---
# Reports README

`dev_docs/reports/` 用于保存阶段性评测、验收与结论报告。

## 目录结构

- `dev_docs/reports/phase1/`
  - Phase 1 历史报告归档。
- `dev_docs/reports/phase2/`
  - Phase 2 当前与后续报告。

原则：

- 根目录不再直接放报告文件，避免跨 phase 默认混读。
- 新报告默认写入当前 active phase 子目录。
