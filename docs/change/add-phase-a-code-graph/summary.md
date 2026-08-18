## 状态

**Phase A：COMPLETED**

完成时间：2026-08-18

完成依据：OpenSpec 任务 1.1～5.2 全部完成，最终整体复审 `READY`，全量测试 60/60 通过。

## 变更摘要

Phase A 将原先只有 Python 结构节点、没有关系边和路径返回的原型，扩展为可发布、可查询、可通过 stdio 调用的技术代码图谱最小闭环。

## 已完成

- Python AST 生成 module/class/function 节点，以及 contains/imports/静态 calls 边。
- 节点、边、evidence、artifact manifest 和 FTS 在同一 staging transaction 中写入并校验 revision。
- Bootstrap 发布 graph snapshot，失败 staging 不切换 active snapshot。
- 查询支持 out/in/both、边类型、canonical key/file path scope、BFS 路径和预算截断。
- 增加 JSON-RPC 2.0 line-oriented stdio；错误请求不阻断后续请求；CLI `--database` 可作为默认数据库路径。

## 未包含

业务 Mining、业务路由闭环、Git diff 增量 Sync、向量检索、非 Python parser、远程服务和 SQLite 替换均属于后续阶段。

## 交付位置

- OpenSpec：`openspec/changes/add-phase-a-code-graph/`
- 本地交接：`docs/change/add-phase-a-code-graph/`
- 实现分支：`feature/phase-a-code-graph`
