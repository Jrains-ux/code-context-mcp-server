import ast
from dataclasses import replace
import json
from pathlib import Path

from code_context.bootstrap.staging import SnapshotPublisher
from code_context.graph.artifacts import EdgeArtifact, GraphArtifact, SourceLocation
from code_context.graph.parser import ParserRegistry
from code_context.validators.schema_validator import ValidationError


class BootstrapService:
    def __init__(self, repository, parser_registry=None):
        self.repository = repository
        self.parser_registry = parser_registry or ParserRegistry.default()

    def build(self, source_root, source_revision, config_version, scope, exclude=(), expected_parent=None):
        if not source_revision:
            raise ValidationError("SOURCE_REVISION_REQUIRED", "source revision is required")
        if not scope:
            raise ValidationError("SOURCE_SCOPE_REQUIRED", "source scope is required")
        source_root = Path(source_root)
        files = self._scoped_files(source_root, scope, exclude)
        manifest_id = self.repository.add_manifest(
            str(source_root), source_revision, {"include": list(scope)},
            {"exclude": list(exclude)}, json.dumps(self.parser_registry.summary(), sort_keys=True), config_version,
        )
        index_revision = f"bootstrap-{source_revision}"
        snapshot_id = self.repository.create_snapshot(source_revision, index_revision, config_version, "staging")
        for file_path in files:
            self.repository.add_task_run(
                f"{snapshot_id}:{file_path.relative_to(source_root).as_posix()}", snapshot_id,
                file_path.relative_to(source_root).as_posix(), source_revision, "running",
            )
        graphs = []
        coverage = {"files": len(files), "supported_files": 0, "unsupported_files": 0, "parsed_files": 0, "languages": {}, "parsers": {}}
        diagnostics = {"total": 0, "unsupported": 0, "parse_errors": 0}
        supported_diagnostics = []
        try:
            for file_path in files:
                relative = file_path.relative_to(source_root).as_posix()
                parser = self.parser_registry.detect(relative)
                source = file_path.read_text(encoding="utf-8")
                if parser is not None:
                    coverage["supported_files"] += 1
                    coverage["languages"][parser.language] = coverage["languages"].get(parser.language, 0) + 1
                    parser_name = f"{parser.parser_id}-{parser.version}"
                    coverage["parsers"][parser_name] = coverage["parsers"].get(parser_name, 0) + 1
                graph = self.parser_registry.parse(
                    relative, source, source_revision=source_revision,
                    snapshot_revision=index_revision, config_revision=config_version,
                )
                if parser is not None and parser.language == "python" and not graph.diagnostics:
                    graph = self._add_python_external_calls(graph, source, relative)
                graphs.append(graph)
                if parser is None:
                    coverage["unsupported_files"] += 1
                    diagnostics["unsupported"] += len(graph.diagnostics)
                else:
                    coverage["parsed_files"] += 1
                    diagnostics["parse_errors"] += len(graph.diagnostics)
                    supported_diagnostics.extend(graph.diagnostics)
                diagnostics["total"] += len(graph.diagnostics)
        except (UnicodeDecodeError, OSError) as error:
            return self._reject(snapshot_id, "PARSE_FAILED", {"message": str(error)})
        if not graphs or coverage["supported_files"] == 0:
            return self._reject(snapshot_id, "COVERAGE_GATE_FAILED", {"scope": list(scope), "coverage": coverage})
        if supported_diagnostics:
            return self._reject(snapshot_id, "PARSE_FAILED", {
                "diagnostics": [self._diagnostic_dict(item) for item in supported_diagnostics],
                "coverage": coverage,
            })
        nodes = tuple(node for graph in graphs for node in graph.nodes)
        edges = self._bind_cross_file_edges(tuple(edge for graph in graphs for edge in graph.edges), nodes)
        graph = GraphArtifact(nodes, edges, source_revision, index_revision, tuple(d for item in graphs for d in item.diagnostics))
        try:
            persisted = self.repository.persist_graph_artifacts(snapshot_id, graph)
        except ValidationError as error:
            return self._reject(snapshot_id, error.code, {"message": str(error)})
        try:
            SnapshotPublisher(self.repository).publish(snapshot_id, expected_parent=expected_parent)
        except ValidationError as error:
            return self._reject(snapshot_id, error.code, {"expected_parent": expected_parent, "active_snapshot": self.repository.get_active_snapshot_id()})
        self.repository.complete_tasks(snapshot_id)
        return {
            "ok": True, "status": "published", "snapshot_id": snapshot_id, "manifest_id": manifest_id,
            "node_count": persisted["node_count"], "edge_count": persisted["edge_count"],
            "parser_versions": self.parser_registry.summary(), "coverage": coverage, "diagnostics": diagnostics,
        }

    @staticmethod
    def _diagnostic_dict(diagnostic):
        return {"code": diagnostic.code, "path": diagnostic.path, "message": diagnostic.message, "detail": dict(diagnostic.detail)}

    def _bind_cross_file_edges(self, edges, nodes):
        symbols = {}
        for node in nodes:
            language = node.payload.get("language")
            name = node.payload.get("name")
            if language and name and node.kind in {"class", "interface", "struct", "function", "method"}:
                symbols.setdefault((language, name), []).append(node.canonical_key)
        bound = []
        for edge in edges:
            symbol = edge.payload.get("symbol")
            language = edge.payload.get("language")
            candidates = symbols.get((language, symbol), ())
            if len(candidates) == 1 and edge.payload.get("resolution") in {"external", "unresolved"}:
                payload = {**edge.payload, "resolution": "static", "bound": True}
                bound.append(replace(edge, target_key=candidates[0], payload=payload))
            else:
                bound.append(edge)
        return tuple(bound)

    @staticmethod
    def _add_python_external_calls(graph, source, relative):
        tree = ast.parse(source, filename=relative)
        existing = {(edge.source_key, edge.payload.get("symbol")) for edge in graph.edges if edge.edge_type == "calls"}
        additions = []
        functions = {node.location.start_line: node for node in graph.nodes if node.kind == "function"}
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            owner = functions.get(node.lineno)
            if owner is None:
                continue
            for call in ast.walk(node):
                if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
                    continue
                symbol = call.func.id
                if (owner.canonical_key, symbol) in existing:
                    continue
                additions.append(EdgeArtifact(
                    "calls", owner.canonical_key, f"unresolved:{symbol}",
                    SourceLocation(relative, getattr(call, "lineno", node.lineno), getattr(call, "col_offset", 0)),
                    owner.evidence, graph.snapshot_revision,
                    {"resolution": "unresolved", "language": "python", "extraction_method": "ast", "evidence_level": "observed", "parse_quality": "complete", "sub_kind": "calls", "roles": ("relation",), "purpose": "source relationship", "symbol": symbol},
                ))
        return GraphArtifact(graph.nodes, graph.edges + tuple(additions), graph.source_revision, graph.snapshot_revision, graph.diagnostics)

    def _reject(self, snapshot_id, code, detail):
        self.repository.add_conflict(snapshot_id, code, detail)
        return {"ok": False, "status": "staging", "code": code, "snapshot_id": snapshot_id, **({"coverage": detail["coverage"]} if "coverage" in detail else {})}

    def _scoped_files(self, source_root, scope, exclude):
        if not source_root.is_dir():
            return []
        include = tuple("" if Path(item).as_posix() == "." else Path(item).as_posix().strip("/") for item in scope)
        excluded = tuple(Path(item).as_posix().strip("/") for item in exclude)
        files = []
        for file_path in source_root.rglob("*"):
            if not file_path.is_file():
                continue
            relative = file_path.relative_to(source_root).as_posix()
            if not any(not item or relative == item or relative.startswith(f"{item}/") for item in include):
                continue
            if any(relative == item or relative.startswith(f"{item}/") for item in excluded):
                continue
            files.append(file_path)
        return sorted(files)
