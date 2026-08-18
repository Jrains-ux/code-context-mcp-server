# Phase A TDD report

## Scope

本地实现 `add-phase-a-code-graph` 的四个实现任务组：图谱 artifact/parser、快照持久化、图查询路径、JSON-RPC stdio。没有提交或推送。

## RED/GREEN evidence

| Task group | RED evidence | GREEN evidence |
|---|---|---|
| Graph artifacts | `ModuleNotFoundError: No module named 'code_context.graph'`；后续作用域、相对 import、控制流去重、类方法和 lambda 回归测试分别暴露预期错误 | `tests/test_graph_phase_a.py`: 11 tests OK |
| Snapshot persistence | `AttributeError`/`TypeError` 暴露缺少批量持久化和 publisher parent API；`AssertionError: 2 != 3` 暴露外部 artifact manifest 缺失；edge revision mismatch 初始被错误接受 | `tests/test_graph_persistence_phase_a.py`: 6 tests OK |
| Graph query | `paths` 为空、`node_scope` 参数不存在、非法 direction 未报错、预算超限仍返回结果 | `tests/test_graph_query_phase_a.py`: 5 tests OK |
| JSON-RPC stdio | `ModuleNotFoundError: No module named 'code_context.tools.stdio'`；CLI stdio 未接入；后续发现 `--database` 丢失并由回归测试捕获 | `tests/test_stdio_phase_a.py`: 6 tests OK |

| Final P1 fixes | CAS regression initially allowed the second stale-parent publish; qualified-name search returned no function hit for legal FTS query `"service.run"` | `tests/test_graph_persistence_phase_a.py`: 8 tests OK; both P1 regression tests pass |

## Review gates

- 每个实现任务组均先完成规格符合性审查，再完成代码质量审查。
- 发现的问题均先补回归测试，再由实现代理修复并复审。
- 任务组 1、2、3、4 的规格审查和质量审查最终均为 `APPROVED`。

## Final verification

```text
python -m unittest discover -s tests -v
Ran 60 tests ... OK
openspec validate add-phase-a-code-graph --strict
Change 'add-phase-a-code-graph' is valid
git diff --check
```

## Known non-blocking risks

- Phase A 仍只实现 Python AST parser；没有非 Python parser、业务 Mining、Git diff 增量同步或向量检索。
- 动态分派、对象方法、反射和运行时猴子补丁不解析为高置信度 calls。
- 外部引用以 `external:*` 节点保存，后续查询层需要确定展示和合并策略。
- stdio 当前未定义负数/非整数预算、未知 scope 字段等更细粒度错误契约。
- migration 由 `schema_migrations` 版本表保证常规流程幂等；单独重复执行迁移 SQL 文件不是目标。
