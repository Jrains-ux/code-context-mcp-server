# Phase B 设计

## 组件

```text
BootstrapService
  -> ParserRegistry.detect(path)
  -> GraphParser.parse(file, project context)
  -> GraphArtifact(nodes, edges, diagnostics)
  -> SnapshotRepository
```

### GraphParser

每个 parser 接受相对路径、源码、source/snapshot/config revision 和项目解析上下文，返回统一 `GraphArtifact`。parser 必须声明 `parser_id`、`version`、支持语言和后缀集合。

### ParserRegistry

registry 负责后缀选择、parser 版本汇总和 unsupported-file diagnostics。选择规则必须确定：最长后缀优先，注册顺序不能影响结果；同一后缀重复注册应失败。

### Typed artifact

公共字段仍由 Phase A 的 immutable dataclass 承担；语言和设计要求的语义字段进入 payload，保持 additive 兼容。静态解析字段使用 `extraction_method=ast|heuristic`，未经证据支持的字段为空或显式标记，不伪造 AI 推断。

### 跨文件绑定

Bootstrap 先解析全部支持文件，再执行 parser 输出的 local symbol references 绑定。第一阶段只绑定同一项目、同一语言内可唯一确定的 module/package + qualified name；多候选和动态派发保留 unresolved/external 结果。

## 发布与失败策略

- 所有支持语言的 artifacts 进入同一 staging snapshot。
- 单个文件语法错误记录 diagnostics 并使本次 snapshot fail-closed；不发布半成品。
- 不支持的后缀不视为解析成功，coverage 报告必须列出。
- 已有 Phase A 的 revisions、evidence、CAS 和发布隔离行为保持不变。
