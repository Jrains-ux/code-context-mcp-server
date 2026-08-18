"""Immutable value objects exchanged between parsers and storage."""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True)
class SourceLocation:
    path: str
    start_line: int
    start_column: int = 0
    end_line: int | None = None
    end_column: int | None = None


@dataclass(frozen=True)
class SourceEvidence:
    source_revision: str
    snapshot_revision: str
    config_revision: str = ""
    parser: str = "python-ast"
    confidence: str = "high"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class NodeArtifact:
    kind: str
    canonical_key: str
    name: str
    location: SourceLocation
    evidence: SourceEvidence
    snapshot_revision: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


@dataclass(frozen=True)
class EdgeArtifact:
    edge_type: str
    source_key: str
    target_key: str
    location: SourceLocation
    evidence: SourceEvidence
    snapshot_revision: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


@dataclass(frozen=True)
class GraphArtifact:
    nodes: tuple[NodeArtifact, ...]
    edges: tuple[EdgeArtifact, ...]
    source_revision: str
    snapshot_revision: str
