# TECH-04 执行总结
- 新增 business routes、route tokens、confirmation audit SQLite 存储。
- 多候选返回 `needs_user_selection` 与 snapshot-bound token；选择必须来自 token 候选且当前 snapshot 未变化。
- confirm 必须提供 evidence，且 expected_version/CAS 匹配；stale mapping 不能自动恢复 confirmed。
- 未来 Mining 负责产生候选，本包不推断业务概念也不自动确认。
