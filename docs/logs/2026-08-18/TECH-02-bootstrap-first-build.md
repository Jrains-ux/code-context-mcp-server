# TECH-02 Bootstrap first build

> 日期：2026-08-18 | 分支：master

## Q1: 继续执行 TECH-02

在 TECH-01 初始化控制面之上执行 TECH-02 / EXEC-02。继续采用个人本地项目约束：允许所需 SQLite migration，需要执行总结和本地提交，不推送、不创建飞书文档、不接入 RDC/SCM。

## Q2: TECH-02 的实现边界是什么？

实现 Bootstrap 首次建图的原型闭环：revision-bound manifest admission、scope task allocation、Python AST 抽取、artifact/evidence staging、conflict/coverage/expected-parent gate 和原子发布。明确不实现 MCP stdio、外部 AI Agent、Mining initial、Query、业务路由或 Sync。

## Q3: 如何以 TDD 验证 Bootstrap？

首先添加 Bootstrap CLI fixture，确认未实现命令返回 2；随后实现最小 admission/extraction/publish 路径使其发布 snapshot。再补回归验证缺少 source revision、空 scope 覆盖、重复 canonical artifact、expected-parent mismatch 和 active snapshot 保持。

## Q4: 实施中发现并修复了什么？

失败测试揭示两个问题：缺少 revision 时 ValidationError 泄漏，根 scope `.` 没有匹配根目录文件、导致在 CAS 之前错误触发 coverage gate。修复后 CLI 以稳定错误码返回，`.` 被规范化为根范围。

## Q5: 最终结果如何？

新增 SQLite `003` migration 和 `BootstrapService`。服务使用 Python 标准库 AST 生成 module/class/function artifact，绑定 hash 与 immutable evidence；失败将 conflict report 留在 staging，成功才调用既有 SnapshotPublisher。完整验证结果为 21 passed、4 subtests passed，compileall 和 OpenSpec 严格校验通过。

## 关键决策与结论

- 增量 migration 增加 `artifact_manifests`、`task_runs`、`conflict_reports`，不重写历史 migration。
- canonical key 为 `file_path:qualified_name:kind`；重复键 fail-closed。
- active snapshot 仅可在全部 gate 成功且 expected parent 相符时切换。
- CodeGraphContext 只用于机制参考，没有被引入为运行时依赖。

## 关联信息

- 需求：TECH-02 / EXEC-02
- OpenSpec：`openspec/changes/add-bootstrap-first-build/`
- 执行总结：`docs/change/add-bootstrap-first-build/summary.md`
- 本地提交：`435b7ee feat: add bootstrap first build`

## 遗留问题 / 待办

- 下一个执行包为 TECH-03：技术代码查询与 FTS/关系/路径查询。
