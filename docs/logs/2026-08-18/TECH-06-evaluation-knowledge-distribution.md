# TECH-06 evaluation knowledge distribution

> 日期: 2026-08-18 | 分支: master

## Q1: TECH-06 执行

按 TECH-06、TECH-00 公共基线和 TDD 管线创建 OpenSpec 变更 `add-evaluation-knowledge-distribution`。实现评测、知识生成和分发消费侧能力；此前已明确仅本地提交、不推送、不创建飞书文档，因此外部适配器未启用。

## 关键决策与结论

- 评测、知识和分发各自写入 consumer-side SQLite 记录，禁止修改 nodes、edges、snapshots 和 mappings。
- 评测绑定 dataset、golden set、tool version 和 active published snapshot 版本；样本不足以 `EVALUATION_INSUFFICIENT` 失败，不生成指标结论。
- 技术知识记录 evidence 与版本；业务知识仅接受 confirmed mapping。
- 分发仅允许 `local` 成功，其他 target 记录 retryable failure，不发起网络请求。
- migration runner 原先会重复执行所有脚本。migration 007 的 ALTER TABLE 测试暴露此问题；通过读取 `schema_migrations` 的已应用版本跳过已执行 migration 修复。首次 migration 时记录表尚不存在，因此先检查 `sqlite_master`。

## 关联信息

- 技术方案：`E:\AiDoc\工单和赔付\docs\requirements\2026-08-17-code-context技术方案拆分\TECH-06-评测知识生成与分发.md`
- OpenSpec：`openspec/changes/add-evaluation-knowledge-distribution/`
- 核心代码：`src/code_context/consumer.py`、`migrations/007_evaluation_knowledge_distribution.sql`、`src/code_context/tools/mcp_tools.py`
- 验证：`30 passed, 4 subtests passed`；OpenSpec strict validation passed。

## 遗留问题 / 待办

- 如需真实外部推送，必须在用户显式放宽本地-only 边界后新增受控 GitLab、飞书 Wiki 或 RAGFlow 适配器。
- 如需业务消歧/路径黑盒评测，需要先定义可复用 golden fixture 契约。
