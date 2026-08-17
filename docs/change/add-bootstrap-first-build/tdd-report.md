# TDD 执行报告

- 变更名称：`add-bootstrap-first-build`
- 执行范围：TECH-02 / EXEC-02
- 开发模式：TDD（RED → GREEN → REFACTOR）
- 开发分支：`master`（本地个人项目，无远端）

## TDD 明细

| 场景 | RED 结果 | GREEN 实现 | 结果 |
|---|---|---|---|
| scoped Bootstrap CLI | `bootstrap` 不是有效命令，CLI 返回 2 | 新增 admission、AST extractor、staging 和 `bootstrap` CLI | 通过 |
| 缺 source revision | 业务异常向调用者泄漏 | CLI 转换为稳定 `SOURCE_REVISION_REQUIRED` | 通过 |
| 根 scope 与父快照 CAS | `.` 未匹配根文件，先触发 coverage gate | 根 scope 规范化并执行 expected-parent 校验 | 通过 |
| 失败 staging | 空 scope、重复 canonical key、parent mismatch | conflict report + active pointer 保持 | 通过 |

## 验证结果

- `python -m pytest -q -p no:cacheprovider`：21 passed，4 subtests passed
- `python -m compileall -q src tests`：通过
- `openspec.cmd validate add-bootstrap-first-build --strict`：通过
- CLI fixture：初始化后，`bootstrap --source-root … --source-revision rev-1 --scope pkg` 发布有效 snapshot
