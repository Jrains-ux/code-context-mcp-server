## TECH-06 执行总结

### 结果

已完成 TECH-06 的评测、知识生成和受控分发原型。能力全部位于已发布快照的消费侧，不参与 Bootstrap 或 Sync 事务，也不会修改 graph 或 mapping。

### 关键实现

- 新增 migration 007：evaluation run、failure case、document artifact、document manifest、distribution attempt。
- 新增 `EvaluationService`，通过既有技术查询能力执行固定样本，记录准确率、freshness、latency、token cost 和失败样本。
- 新增 `KnowledgeService`，技术文档绑定 active published snapshot；业务文档仅使用 confirmed mapping；两者都记录证据、版本和 SHA-256 校验。
- 新增 `DistributionService`，`local` 分发支持 idempotency key；非本地目标记录可重试失败，不调用外部平台。
- CLI 新增 `evaluate`、`knowledge-generate`、`knowledge-push`。

### 验证结果

```text
30 passed, 4 subtests passed
OpenSpec strict validation passed
```

### 风险与边界

- 没有实现外部推送适配器，符合“仅本地提交、不推送、不开飞书文档”的约束。
- 当前黑盒评测覆盖确定性技术检索；业务歧义路由、选择续查和路径扩展评测可在明确 fixture 后补齐。
