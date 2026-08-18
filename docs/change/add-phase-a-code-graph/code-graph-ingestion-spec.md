## Purpose

从限定的本地源码范围生成版本化节点、关系边和不可变证据，并仅在完整校验后发布为可消费快照。

## ADDED Requirements

### Requirement: Python source produces typed graph artifacts
The system SHALL parse scoped Python files into module, class, and function nodes and SHALL create contains, imports, and statically resolvable calls edges with source evidence and snapshot revisions.

#### Scenario: Python file contains import and call
- **WHEN** a scoped Python file imports a module and a function calls a resolvable symbol
- **THEN** the staged graph contains the structural nodes and corresponding contains, imports, and calls edges

### Requirement: Graph publication is snapshot-consistent
The system SHALL publish nodes, edges, evidence, and the technical search index only after validation of source revision, configuration revision, canonical keys, and expected parent snapshot.

#### Scenario: Graph validation fails
- **WHEN** a staged graph has an artifact conflict, parse failure, or parent mismatch
- **THEN** the active published snapshot remains unchanged and the staged result records the failure
