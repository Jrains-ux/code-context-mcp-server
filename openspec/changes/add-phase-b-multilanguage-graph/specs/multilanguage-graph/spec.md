## Purpose

Define the Phase B parser registry and the common multilingual graph artifact contract for Java, Go, JavaScript, and TypeScript source files.

## ADDED Requirements

### Requirement: Deterministic parser registry

The system MUST select a parser by file suffix using the longest matching suffix, reject duplicate suffix registration, and return a diagnostic for unsupported suffixes.

#### Scenario: Select the most specific parser

- **WHEN** multiple registered suffixes match a path
- **THEN** the registry MUST select the parser with the longest matching suffix independently of registration order

#### Scenario: Unsupported source file

- **WHEN** a source path has no registered suffix
- **THEN** the registry MUST return an unsupported-file diagnostic without producing graph artifacts

### Requirement: Common typed graph artifacts

Every parser MUST return the common `NodeArtifact`, `EdgeArtifact`, and diagnostic structures while preserving source location, source revision, snapshot revision, config revision, parser metadata, and evidence. Code artifacts MUST include `language`, `extraction_method`, and `evidence_level` in their payload.

#### Scenario: Parse a supported multilingual file

- **WHEN** a registered parser extracts a source declaration or relationship
- **THEN** the artifact MUST contain the common location, revision, parser, evidence, and semantic payload fields

#### Scenario: Heuristic extraction

- **WHEN** a declaration or relationship is extracted by a dependency-free heuristic parser
- **THEN** its payload MUST identify heuristic extraction and MUST NOT claim unsupported dynamic dispatch as a static call

### Requirement: Multilingual source coverage

The registry MUST support Python, Java, Go, JavaScript, and TypeScript files. The heuristic parsers MUST extract the supported basic module or package, class, interface, struct, function, method, import, export, and relationship artifacts where the source syntax permits.

#### Scenario: Go grouped imports

- **WHEN** a Go file contains an `import (...)` block
- **THEN** each imported path in the block MUST be represented as an import artifact

#### Scenario: Multiple declarations on one line

- **WHEN** a supported source line contains a class and a method declaration such as `class Demo { void run() {} }`
- **THEN** the parser MUST extract both declarations and their containment relationship

### Requirement: Stable cross-file identity

Package, module, and import identities MUST remain unique and stable for the file dimension used by parsing, so artifacts from different files in the same Java or Go package cannot share a canonical key.

#### Scenario: Same package across multiple files

- **WHEN** two Java or Go files declare the same package and same symbol name
- **THEN** their per-file package and declaration artifacts MUST have distinct canonical keys

### Requirement: Bounded heuristic call extraction

Heuristic call extraction MUST inspect only the current function or method body. It MUST NOT treat the declaration signature, the containing declaration, or a different function body as calls belonging to the current function. Dynamic calls such as `obj[method]()` MUST be emitted as unresolved or external, or reported through a diagnostic, and MUST NOT be marked static.

#### Scenario: Sequential function bodies

- **WHEN** two functions occur in one source file and each has a different call
- **THEN** each function MUST receive only the call found in its own body

#### Scenario: Dynamic dispatch

- **WHEN** a function invokes a computed member such as `obj[method]()`
- **THEN** the resulting relationship MUST have an unresolved or external resolution, never static resolution

### Requirement: Fail-closed parsing and coverage reporting

Bootstrap MUST scan all source suffixes supported by the registry, report parser and language coverage in its manifest or result, preserve unsupported-file diagnostics, and keep the active snapshot unchanged when parsing or publication validation fails.

#### Scenario: Unbalanced heuristic source

- **WHEN** a heuristic parser receives a source file with unbalanced delimiters
- **THEN** it MUST retain partial parse quality in its artifacts and return a diagnostic identifying the partial result

#### Scenario: Publication failure

- **WHEN** parsing or publication validation fails for a snapshot
- **THEN** the active snapshot MUST remain unchanged and partial staging data MUST NOT be published
