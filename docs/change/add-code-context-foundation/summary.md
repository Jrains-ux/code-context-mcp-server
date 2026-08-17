## 需求来源

需求文档：`E:/AiDoc/工单和赔付/docs/requirements/2026-08-17-code-context技术方案拆分/2026-08-17-code-context技术方案拆分.md`

## 需求概述

本次执行 TECH-00，建立 code-context-mcp-server 的跨包技术基线与最小数据面。实现本地 SQLite schema、版本化快照存储、staging 到 published 的原子发布、证据与 stale mapping 约束，以及 Skill/Tool 权限和运行时契约校验。项目为个人本地项目，采用 `local` 标识，不执行 RDC 绑定、推送或飞书文档创建。

## 变更信息

- 变更名称：`add-code-context-foundation`
- 执行范围：TECH-00 / EXEC-01
- 开发模式：TDD
- OpenSpec 变更目录：`openspec/changes/add-code-context-foundation/`
- 本地报告目录：`docs/change/add-code-context-foundation/`
- 外部参考：`E:/AiDoc/project/other/CodeGraphContext`，仅用于机制参考，不作为运行时依赖

## TDD 测试统计

- 总任务数：14
- TDD 任务数：10
- 直接实现任务数：4
- 新增测试用例：11 个，包含 4 个子测试
- 测试通过率：100%

## 技术方案

| 决策 | 选择 | 理由 |
|------|------|------|
| 持久化 | 本地 SQLite | 满足 TECH-00 最小数据面与个人项目运行方式 |
| 发布模型 | staging → published 原子发布 | 保留 active snapshot，并在失败时避免切换活动指针 |
| 证据约束 | immutable evidence + stale replacement linkage | 保持证据可追溯，支持映射失效替换 |
| 运行时入口 | 本地 CLI `init` / `migrate` / `doctor` | 提供可验证的初始化和健康检查闭环 |
| 参考实现 | CodeGraphContext 仅作机制参考 | 避免引入无关运行时依赖 |

## 已实现内容

### 阶段 1：项目与迁移

- [x] 创建 Python 包、项目元数据和本地 CLI 入口
- [x] 增加 manifests、snapshots、nodes、edges、evidence、mappings、stale_events、update_operations、evaluation_runs、route_audit、tool_registry 表
- [x] 支持临时工作区 SQLite 初始化

### 阶段 2：存储基础

- [x] 实现 migration 执行与 schema 健康检查
- [x] 实现按版本绑定的 manifest、snapshot、node、edge、evidence、mapping 持久化
- [x] 实现 staging artifact 校验与原子快照发布
- [x] 实现 immutable evidence 与 stale mapping 替换证据关联

### 阶段 3：运行时契约

- [x] 实现 TECH-00 Skill-to-tool permission matrix
- [x] 实现 tool registry 持久化同步和缺失契约诊断
- [x] 实现 envelope、revision、snapshot-state 校验及稳定错误码
- [x] 实现 `init`、`migrate`、`doctor` 机器可读命令结果

## 修改文件清单

| 操作 | 路径 |
|------|------|
| 新增 | `pyproject.toml` |
| 新增 | `migrations/001_initial.sql` |
| 新增 | `src/code_context/` 下的存储、bootstrap、policy、tools、validator 模块 |
| 新增 | `tests/test_foundation.py` |
| 新增 | `openspec/changes/add-code-context-foundation/` 下的 proposal、design、tasks、specs |
| 新增 | `docs/change/add-code-context-foundation/` 下的执行报告与测试清单 |

## 验证结果

- `python -m pytest -q`：11 passed，4 subtests passed
- `python -m compileall -q src tests`：通过
- `python -m code_context.tools init --database .final-check.db`：initialized
- `python -m code_context.tools doctor --database .final-check.db`：healthy
- 临时数据库已清理

## 风险与待办

- 本次仅完成 TECH-00/EXEC-01；MCP stdio transport、真实源码解析、Bootstrap、Query、Sync、Mining、Evaluation、Knowledge 和 push 尚未实现。
- 当前仓库无远端推送；本次只创建本地 commit。

## Git 提交信息

建议提交信息：`feat: add code context foundation`
