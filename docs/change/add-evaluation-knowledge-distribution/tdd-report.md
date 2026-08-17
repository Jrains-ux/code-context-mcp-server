# TECH-06 TDD 执行报告

## 执行范围

- OpenSpec 变更：`add-evaluation-knowledge-distribution`
- 技术方案：`TECH-06-评测知识生成与分发.md`
- 实现范围：版本绑定评测、知识文档与 manifest、受控本地分发、CLI 入口。

## RED → GREEN 记录

| 场景 | RED 证据 | GREEN 证据 |
|---|---|---|
| TECH-06 消费服务 | `ModuleNotFoundError: code_context.consumer` | 4 个消费服务测试通过 |
| CLI 消费命令 | `TypeError: run() got an unexpected keyword argument 'dataset_id'` | CLI `run` 集成测试通过 |
| 可重复迁移 | 第二次命令调用暴露 `duplicate column name: snapshot_id`；首轮修正又暴露 `no such table: schema_migrations` | 幂等 migration 门禁修正后，所有测试通过 |

## 新增行为

- 评测不足样本返回 `EVALUATION_INSUFFICIENT`，不落入虚构指标。
- 评测运行保存 dataset、golden set、tool、source/index/config 版本、指标与 failure case。
- 技术文档写入 snapshot、evidence refs、generator/template 版本和 SHA-256 内容校验。
- 业务文档仅消费 active snapshot 中 `confirmed` mapping；未确认 mapping 返回 `CONFIRMED_MAPPING_REQUIRED`。
- `local` 是唯一成功分发目标；其他目标落库为 `DISTRIBUTION_TARGET_UNSUPPORTED`、可重试失败，且不访问网络。

## 验证

```text
python -m pytest -q -p no:cacheprovider
30 passed, 4 subtests passed in 3.29s

openspec.cmd validate add-evaluation-knowledge-distribution --strict
Change 'add-evaluation-knowledge-distribution' is valid
```

## 边界与遗留项

- 当前 evaluator 是确定性技术查询 golden-suite；歧义业务路由和路径扩展的黑盒样本契约可在后续有 fixture 后扩展。
- 未实现 GitLab、飞书 Wiki、RAGFlow 等外部适配器，以遵守本次本地、不推送、不创建飞书文档的边界。
