# TECH-01 initialization control plane

> 日期：2026-08-18 | 分支：master

## Q1: 执行 TECH-01

在 TECH-00 已提交的 SQLite、snapshot 和基础 CLI 之上，执行 TECH-01 / EXEC-01。用户确认项目是个人本地项目：允许本次数据库演进、需要本地提交和执行总结、不推送、不做 RDC/SCM 绑定、不创建飞书文档。

## Q2: TECH-01 和 TECH-00 的边界如何处理？

TECH-00 已提供初始 schema、静态权限矩阵、注册表和 `init/migrate/doctor` 雏形。TECH-01 的缺口确定为初始化控制面：持久化项目 manifest、从 manifest 同步注册表、health/doctor fail-closed gate、显式 CLI 初始化参数，以及与 published snapshot 连通的最小 fixture。

## Q3: 如何保证实现遵循 TDD？

先后增加并观察到三个失败测试：默认初始化未返回 manifest、`health` 为未知命令而非 `SERVICE_NOT_READY`、CLI 不识别显式 manifest 参数/非法空项目。随后以最小实现使测试通过，再补充 registry 漂移、发布 fixture 后 ready 的回归覆盖。

## Q4: 实施过程是否遇到阻塞？

PowerShell 执行策略阻止了 `openspec.ps1`。确认根因是 shell 对 `.ps1` 的限制后，使用同目录的 `openspec.cmd` 等价入口继续，不修改系统执行策略。pytest cache 路径没有写权限，因此验证命令使用 `-p no:cacheprovider`；测试本身不受影响。

## Q5: 最终实现和验证结果是什么？

新增 SQLite `002` migration，并在 init 时保存 singleton manifest 与 permissions；`init` 支持 project/workspace/source revision/config version 参数。`health`/`doctor` 检查 schema、manifest、registry、active published snapshot；没有已发布快照时返回 `SERVICE_NOT_READY`，发布一致快照后 `runtime_ready=true`。验证：16 passed、4 subtests passed，compileall 通过，OpenSpec 严格校验通过。

## 关键决策与结论

- 采用加性 migration，不重写 `001_initial.sql`，以保持既有数据库的可升级性。
- manifest 是单项目本地 SQLite singleton，权限声明不能超出静态 `PermissionMatrix` allow-list。
- runtime ready 必须包括 active published snapshot；仅 migration 或 init 成功不能假装后续 Skill 可执行。
- 不实现 TECH-02 及以后能力：MCP stdio、源码解析、Bootstrap、Query、Sync、Mining、Evaluation、Knowledge、push。

## 关联信息

- 需求：TECH-01 / EXEC-01
- OpenSpec：`openspec/changes/add-initialization-control-plane/`
- 执行总结：`docs/change/add-initialization-control-plane/summary.md`
- 本地提交：`31f8153 feat: add initialization control plane`

## 遗留问题 / 待办

- 下一执行包应从 TECH-02 开始，建立 Bootstrap 首次建图；不得将后续能力并入 TECH-01。
