# TECH-00 code context foundation

> 日期: 2026-08-18 | 分支: master

## Q1: 本次需要完成什么范围？

用户要求执行 `tdd-pipeline`，针对 TECH-00 在本地 code-context-mcp-server 项目中完成技术基线与最小数据面。用户确认放宽数据库修改规则，项目为个人本地项目，不需要 RDC/迭代绑定，也不需要推送。

## Q2: 采用了哪些实现决策？

基于需求文档、TECH-00/EXEC-01 事实文档和项目现状，新增 Python 包与本地 SQLite 迁移。实现 manifests、snapshots、nodes、edges、evidence、mappings 等基础表，使用 staging → published 原子发布保留 active snapshot，并通过 immutable evidence 和 stale replacement linkage 保证可追溯性。CodeGraphContext 只作为机制参考，不作为运行时依赖。

## Q3: 如何验证实现？

`python -m pytest -q` 通过，结果为 11 passed、4 subtests passed；`python -m compileall -q src tests` 通过；CLI `init` 返回 initialized，`doctor` 返回 healthy。误暂存的 `__pycache__` 已清理，尾随空格已修正。

## Q4: 最终提交和遗留范围是什么？

已创建本地提交 `50275f0 feat: add code context foundation`，未执行 push，工作区干净。当前仅完成 TECH-00/EXEC-01；MCP stdio transport、真实源码解析、Bootstrap、Query、Sync、Mining、Evaluation、Knowledge 和 push 仍待后续任务实现。

## 关键决策与结论

- 本次使用本地标识 `local`，不做 RDC/SCM 需求绑定。
- 数据库变更限定为本次 TECH-00 的本地 SQLite 原型范围。
- 执行总结保存在 `docs/change/add-code-context-foundation/summary.md`。

## 关联信息

- 需求文档：`E:/AiDoc/工单和赔付/docs/requirements/2026-08-17-code-context技术方案拆分/2026-08-17-code-context技术方案拆分.md`
- OpenSpec：`openspec/changes/add-code-context-foundation/`
- 提交：`50275f0`

## 遗留问题 / 待办

- 后续需要为 TECH-01 及之后的执行包创建独立 OpenSpec change。
