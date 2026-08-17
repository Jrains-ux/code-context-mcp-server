# Design

本地副本对应 `openspec/changes/add-code-context-foundation/design.md`。

实现采用 Python 标准库、单 SQLite 文件、编号迁移、JSON payload 和 guarded publish transaction；不依赖 CodeGraphContext，不实现后续 Bootstrap/Query/Sync 业务流程。
