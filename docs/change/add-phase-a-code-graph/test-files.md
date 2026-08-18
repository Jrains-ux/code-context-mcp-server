# Phase A test files

The persistence test file also covers atomic expected-parent publication and end-to-end qualified-name FTS search.

- `tests/test_graph_phase_a.py` — Python module/class/function nodes、contains/imports/calls、作用域、相对 import、控制流去重、类方法和 lambda 边界。
- `tests/test_graph_persistence_phase_a.py` — graph staging transaction、canonical key、external node、evidence/revision、FTS、Bootstrap 发布和失败回滚。
- `tests/test_graph_query_phase_a.py` — direction、edge type、node scope、BFS path、node/edge budget、snapshot isolation。
- `tests/test_stdio_phase_a.py` — JSON-RPC correlation、malformed/invalid/unknown/params error、继续处理后续行、subprocess CLI 和数据库参数。
- `tests/test_foundation.py` — 原有基础回归测试，未删除或替换。
