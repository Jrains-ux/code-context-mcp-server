# Phase B：统一多语言图谱底座

## Why

Phase A 已建立 Python AST 技术图谱、快照发布、路径遍历和 stdio JSON-RPC 底座，但 Bootstrap 仍固定扫描 Python，解析器接口也没有统一的语言注册机制。原 design 要求代码节点带有语言、角色/用途、解析质量和 evidence，并允许后续接入 Java、Go、JavaScript/TypeScript 以及业务节点。

## What Changes

- 增加统一 `GraphParser` / `ParserRegistry` 协议，按语言和文件后缀选择 parser。
- 将现有 Python parser 接入 registry，并保持现有 Python 图谱行为兼容。
- 增加无第三方依赖的 Java、Go、JavaScript/TypeScript 基础 parser，抽取可解释的 module/class/interface/function/method/endpoint/data/external 节点和 contains/imports/defines/implements/extends/calls 等基础边；无法静态解析的调用不冒充确定调用。
- 扩展 artifact payload，明确 `language`、`sub_kind`、`roles`、`purpose`、`extraction_method`、`evidence_level`、`parse_quality` 等字段。
- Bootstrap 根据 registry 扫描支持的源码文件，manifest 记录 parser 版本和语言覆盖；不支持的文件进入 diagnostics，不阻断已支持语言的构建。
- 增加跨文件静态符号绑定的最小实现：同一 snapshot 内按语言、module/package 和限定名解析本地定义；未解析引用生成 `external:*` 节点或保留 unresolved diagnostics。

## Non-Goals

- 本阶段不实现需求/工单/赔付规则 mapping、Mining、BusinessRouter 闭环。
- 本阶段不实现 Git diff 增量、向量检索和真实项目规模性能门禁。
- 不使用网络下载或第三方 parser 依赖；复杂语法采用可解释降级，并在 evidence/diagnostics 中标记。
