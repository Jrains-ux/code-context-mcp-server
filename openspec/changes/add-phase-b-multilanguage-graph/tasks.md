# Phase B 任务清单

## 1. 规格与协议

- [ ] 1.1 定义 `GraphParser`、`ParserRegistry`、解析上下文和 diagnostics 协议。
- [ ] 1.2 扩展 Node/Edge artifact payload 的 typed 字段及 parser metadata。
- [ ] 1.3 增加 OpenSpec 场景和兼容性约束。

## 2. TDD：Parser registry 与 Python 兼容

- [ ] 2.1 RED：registry 按后缀确定性选择 parser，重复注册失败，不支持后缀产生 diagnostics。
- [ ] 2.2 GREEN：接入现有 Python parser，保持 Phase A 测试全部通过。
- [ ] 2.3 RED/GREEN：typed payload 和 parser evidence 字段。

## 3. TDD：多语言基础 parser

- [ ] 3.1 RED/GREEN：Java package/class/interface/method/import/extends/implements 基础节点边。
- [ ] 3.2 RED/GREEN：Go package/struct/function/method/import 基础节点边。
- [ ] 3.3 RED/GREEN：JavaScript/TypeScript module/class/interface/function/import/export 基础节点边。
- [ ] 3.4 RED/GREEN：语法降级、unresolved/external 节点和 diagnostics。

## 4. TDD：Bootstrap 集成和跨文件绑定

- [x] 4.1 RED/GREEN：按 registry 扫描多语言文件，manifest 记录 parser coverage。
- [x] 4.2 RED/GREEN：同语言跨文件唯一符号绑定和 external fallback。
- [x] 4.3 RED/GREEN：混合语言 snapshot 原子发布，失败保持 active snapshot 不变。

## 5. 审查与验证

- [ ] 5.1 规格审查：逐项核对 design 与 OpenSpec。
- [ ] 5.2 代码质量审查：边界、错误处理、兼容性和测试质量。
- [ ] 5.3 全量测试、compile、diff check 和 OpenSpec strict validation。
