# TECH-05 执行总结

- 新增 `sync_operations` 和 `SyncService`。
- Sync 必须基于 active baseline，缺失时返回 `BASELINE_REF_NOT_FOUND`；相同 operation_id 返回首次记录结果。
- 旧 mapping 追加 stale event 并标记 stale，新结果经 Bootstrap staging 和 expected-parent 原子发布。
- Query 不会自动触发 Sync。
- 验证：25 passed，4 subtests passed；compileall 与 OpenSpec 严格校验通过。
