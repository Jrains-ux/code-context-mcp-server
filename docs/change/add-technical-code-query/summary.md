# TECH-03 执行总结

- 新增 SQLite FTS5 `node_fts`，Bootstrap 发布后显式建立 published snapshot 索引。
- 新增 `TechnicalQueryService` 和本地 `search` / `expand` CLI。
- search 只查 active published snapshot，返回节点、命中字段、evidence refs 和 snapshot_ref；无 published snapshot 返回 `SNAPSHOT_NOT_PUBLISHED`，未索引返回 `INDEX_UNAVAILABLE`。
- expand 受 depth、node/edge budget 约束，只遍历同一 snapshot 的边并返回 `truncated`。
- 验证：22 passed、4 subtests passed；compileall 与 OpenSpec 严格校验通过。
- 不包含业务路由、Mining、Sync 或查询写入。
