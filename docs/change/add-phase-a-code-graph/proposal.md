## Why

当前原型只能从 Python 源码建立模块、类和函数的结构节点，并以 FTS5 搜索名称；它不会生成任何关系边，无法返回调用路径，也不能作为标准 MCP stdio 服务被外部 Skill 调用。Phase A 建立可查询代码图谱的最小闭环，为后续业务路由、Mining 和增量同步提供可信的 raw graph 基础。

## What Changes

- 增加 JSON-RPC 2.0 stdio transport，并复用现有命令服务层。
- 引入统一 node/edge artifact 合同和 Python AST parser adapter。
- 从 Python 源码提取 module、class、function 节点，以及 contains、imports、calls 边。
- 将 node、edge、evidence 和 FTS 索引作为 staging 校验与发布的同一单元。
- 扩展技术查询，支持边类型/方向/scope 过滤、预算截断和可解释路径返回。

## Capabilities

### New Capabilities

- `code-graph-ingestion`: 从受限 Python 源码范围提取版本化的节点、关系边和证据，并以快照发布。
- `code-graph-query`: 在已发布快照内检索节点、遍历关系并返回受预算约束的路径。
- `mcp-stdio-transport`: 通过 JSON-RPC 2.0 stdio 暴露本地代码图谱工具。

### Modified Capabilities

无。当前仓库没有已归档的 canonical OpenSpec capability；本次以新的行为契约建立 Phase A 基线。

## Impact

- 影响 `bootstrap/first_build.py`、`storage/repository.py`、`query.py` 和 CLI 参数。
- 新增 graph parser 和 stdio transport 模块，并新增对应 migration 与单元测试。
- 维持 SQLite/FTS5、现有快照版本和本地 CLI 兼容；不引入外部运行时依赖。
