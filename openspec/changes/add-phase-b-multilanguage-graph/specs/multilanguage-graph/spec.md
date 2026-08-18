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

### Requirement: Context-bound static symbol resolution

Bootstrap MUST resolve a cross-file symbol only with the same language, module or package identity, and qualified name. A static binding MUST also be supported by an import or relative-module relationship, or by a shared module/package context. Same-named symbols from different packages without such context MUST remain external or unresolved.

#### Scenario: Same-named helpers in different packages

- **WHEN** two packages define the same helper name and a caller has no import or shared package context
- **THEN** the caller relationship MUST remain external or unresolved and MUST NOT be statically bound to either helper

#### Scenario: Imported helper

- **WHEN** a caller imports a uniquely identified helper from another module
- **THEN** Bootstrap MUST bind the relationship to that helper's qualified artifact key

### Requirement: Artifact-derived language coverage

Bootstrap MUST derive language coverage and parser version records from each parsed artifact's payload or evidence metadata. `.ts` and `.tsx` artifacts MUST count as `typescript`; `.js` and `.jsx` artifacts MUST count as `javascript`. A mutable parser language field MUST NOT override artifact language identity.

#### Scenario: JavaScript and TypeScript coverage

- **WHEN** Bootstrap parses one JavaScript file and one TypeScript file with a shared parser implementation
- **THEN** coverage MUST report one `javascript` file and one `typescript` file, with parser versions recorded consistently for both languages

### Requirement: Detailed Bootstrap diagnostics

Bootstrap MUST return a complete diagnostics list in addition to existing diagnostic counts. Each diagnostic entry MUST include at least `code`, `path`, `message`, and `detail`. Unsupported files and supported parser failures MUST both contribute detailed entries, while a failed build MUST remain fail-closed and leave the active snapshot unchanged.

#### Scenario: Supported parser failure

- **WHEN** a supported source file fails parsing
- **THEN** the result and retained staging conflict MUST identify the file with a complete diagnostic entry

### Requirement: Bounded heuristic call extraction

Heuristic call extraction MUST inspect only the current function or method body. It MUST NOT treat the declaration signature, the containing declaration, or a different function body as calls belonging to the current function. Dynamic calls such as `obj[method]()` MUST be emitted as unresolved or external, or reported through a diagnostic, and MUST NOT be marked static.

#### Scenario: Sequential function bodies

- **WHEN** two functions occur in one source file and each has a different call
- **THEN** each function MUST receive only the call found in its own body

#### Scenario: Dynamic dispatch

- **WHEN** a function invokes a computed member such as `obj[method]()`
- **THEN** the resulting relationship MUST have an unresolved or external resolution, never static resolution

#### Scenario: Nested Python functions

- **WHEN** an outer Python function and a nested inner function each contain a missing call
- **THEN** each function MUST receive only the missing call from its own lexical body

### Requirement: Fail-closed parsing and coverage reporting

Bootstrap MUST scan all source suffixes supported by the registry, report parser and language coverage in its manifest or result, preserve unsupported-file diagnostics, and keep the active snapshot unchanged when parsing or publication validation fails.

#### Scenario: Unbalanced heuristic source

- **WHEN** a heuristic parser receives a source file with unbalanced delimiters
- **THEN** it MUST retain partial parse quality in its artifacts and return a diagnostic identifying the partial result

#### Scenario: Publication failure

- **WHEN** parsing or publication validation fails for a snapshot
- **THEN** the active snapshot MUST remain unchanged and partial staging data MUST NOT be published
