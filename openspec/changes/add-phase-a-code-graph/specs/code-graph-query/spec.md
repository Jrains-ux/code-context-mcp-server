## Purpose

在已发布且版本一致的代码图谱中召回节点、遍历关系并返回受范围和预算约束的可解释路径。

## ADDED Requirements

### Requirement: Published graph queries return explainable paths
The system SHALL query only the active published snapshot and SHALL return edges and reconstructed node paths for graph expansion.

#### Scenario: Call chain is expanded
- **WHEN** a caller expands a node through calls edges within depth and budget limits
- **THEN** the response contains the traversed edges and ordered node paths with the snapshot reference

### Requirement: Graph expansion enforces caller constraints
The system SHALL apply direction, edge type, node scope, node budget, and edge budget constraints without crossing snapshot boundaries.

#### Scenario: Expansion reaches a budget
- **WHEN** traversal needs more nodes or edges than the supplied budget
- **THEN** the response returns only in-budget results and sets truncated to true
