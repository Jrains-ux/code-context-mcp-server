import ast
from dataclasses import replace
import json
import posixpath
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
        diagnostics = {"total": 0, "unsupported": 0, "parse_errors": 0, "details": []}
        supported_diagnostics = []
        try:
            for file_path in files:
                relative = file_path.relative_to(source_root).as_posix()
                parser = self.parser_registry.detect(relative)
                source = file_path.read_text(encoding="utf-8")
                if parser is not None:
                    coverage["supported_files"] += 1
                graph = self.parser_registry.parse(
                    relative, source, source_revision=source_revision,
                    snapshot_revision=index_revision, config_revision=config_version,
                )
                artifact_languages = self._artifact_languages(graph)
                if not artifact_languages and parser is not None:
                    artifact_languages = {self._language_for_path(relative, parser)}
                for language in artifact_languages:
                    coverage["languages"][language] = coverage["languages"].get(language, 0) + 1
                parser_versions = self._artifact_parser_versions(graph, parser)
                for parser_name in parser_versions:
                    coverage["parsers"][parser_name] = coverage["parsers"].get(parser_name, 0) + 1
                if parser is not None and self._language_for_path(relative, parser) == "python" and not graph.diagnostics:
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
                diagnostics["details"].extend(self._diagnostic_dict(item) for item in graph.diagnostics)
        except (UnicodeDecodeError, OSError) as error:
            detail = {"code": "PARSE_FAILED", "path": relative if "relative" in locals() else "", "message": str(error), "detail": {}}
            diagnostics["total"] += 1
            diagnostics["parse_errors"] += 1
            diagnostics["details"].append(detail)
            return self._reject(snapshot_id, "PARSE_FAILED", {"message": str(error), "diagnostics": [detail], "diagnostic_counts": diagnostics})
        if not graphs or coverage["supported_files"] == 0:
            return self._reject(snapshot_id, "COVERAGE_GATE_FAILED", {"scope": list(scope), "coverage": coverage, "diagnostics": diagnostics["details"], "diagnostic_counts": diagnostics})
        if supported_diagnostics:
            return self._reject(snapshot_id, "PARSE_FAILED", {
                "diagnostics": [self._diagnostic_dict(item) for item in supported_diagnostics],
                "diagnostic_counts": diagnostics,
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
            "parser_versions": self._parser_versions(graphs), "coverage": coverage, "diagnostics": diagnostics,
        }

    @staticmethod
    def _artifact_languages(graph):
        languages = set()
        for artifact in (*graph.nodes, *graph.edges):
            language = artifact.payload.get("language") or artifact.evidence.metadata.get("language")
            if language:
                languages.add(language)
        return languages

    @classmethod
    def _artifact_parser_versions(cls, graph, parser):
        versions = set()
        for artifact in (*graph.nodes, *graph.edges):
            metadata = artifact.evidence.metadata
            parser_id = metadata.get("parser_id") or artifact.evidence.parser
            version = metadata.get("parser_version")
            if parser_id and version:
                versions.add(f"{parser_id}-{version}")
        if not versions and parser is not None:
            versions.add(f"{parser.parser_id}-{parser.version}")
        return versions

    @staticmethod
    def _language_for_path(relative, parser):
        if parser.parser_id == "javascript-heuristic":
            return "typescript" if Path(relative).suffix.lower() in {".ts", ".tsx"} else "javascript"
        return {
            "python-ast": "python",
            "java-heuristic": "java",
            "go-heuristic": "go",
        }.get(parser.parser_id, parser.parser_id.split("-", 1)[0])

    @classmethod
    def _parser_versions(cls, graphs):
        result = {}
        for graph in graphs:
            for artifact in (*graph.nodes, *graph.edges):
                metadata = artifact.evidence.metadata
                language = artifact.payload.get("language") or metadata.get("language")
                parser_id = metadata.get("parser_id") or artifact.evidence.parser
                version = metadata.get("parser_version")
                if language and parser_id and version:
                    result[language] = f"{parser_id}-{version}"
        return result

    @staticmethod
    def _diagnostic_dict(diagnostic):
        return {"code": diagnostic.code, "path": diagnostic.path, "message": diagnostic.message, "detail": dict(diagnostic.detail)}

    def _bind_cross_file_edges(self, edges, nodes):
        symbols = {}
        for node in nodes:
            language = node.payload.get("language")
            name = node.payload.get("name")
            if language and name and node.kind in {"class", "interface", "struct", "function", "method"}:
                symbols.setdefault((language, name), []).append(node)
        by_key = {node.canonical_key: node for node in nodes}
        imports_by_source = {}
        for edge in edges:
            if edge.edge_type == "imports":
                imports_by_source.setdefault(edge.source_key, []).append(edge)
        bound = []
        for edge in edges:
            symbol = edge.payload.get("symbol")
            language = edge.payload.get("language")
            candidates = symbols.get((language, symbol), ())
            source = by_key.get(edge.source_key)
            source_module = source.payload.get("module_identity") if source else None
            source_package = source.payload.get("package_identity") if source else None
            visible_imports = list(imports_by_source.get(edge.source_key, ()))
            if source_module:
                visible_imports.extend(imports_by_source.get(f"module:{source_module}", ()))

            def is_visible(candidate):
                candidate_module = candidate.payload.get("module_identity")
                candidate_package = candidate.payload.get("package_identity")
                relative_import = any(
                    item.payload.get("language") in {"javascript", "typescript"}
                    and (item.payload.get("import_source") or item.payload.get("source") or "").startswith(".")
                    and item.payload.get("imported_symbol")
                    and (item.payload.get("alias") or item.payload.get("imported_symbol")) == symbol
                    for item in visible_imports
                )
                if relative_import and candidate.kind != "function":
                    return False
                same_context = source_package and candidate_package and source_package == candidate_package
                imported = any(
                    self._javascript_import_matches(item, candidate, source, symbol)
                    or item.payload.get("module") == candidate_module
                    or item.payload.get("import") == candidate_module
                    or item.payload.get("target_key", "").endswith(candidate_module or "")
                    or self._import_names_candidate(item, candidate)
                    for item in visible_imports
                )
                return same_context or imported

            visible = [candidate for candidate in candidates if is_visible(candidate)]
            can_rebind_import = edge.payload.get("resolution") == "static" and edge.target_key.startswith("import:")
            if len(visible) == 1 and (edge.payload.get("resolution") in {"external", "unresolved"} or can_rebind_import):
                payload = {**edge.payload, "resolution": "static", "bound": True}
                bound.append(replace(edge, target_key=visible[0].canonical_key, payload=payload))
            else:
                bound.append(edge)
        return tuple(bound)

    @staticmethod
    def _javascript_import_matches(import_edge, candidate, source, symbol):
        if import_edge.payload.get("language") not in {"javascript", "typescript"}:
            return False
        if candidate.kind != "function":
            return False
        if candidate.payload.get("language") != import_edge.payload.get("language"):
            return False
        import_source = import_edge.payload.get("import_source") or import_edge.payload.get("source")
        imported_symbol = import_edge.payload.get("imported_symbol")
        alias = import_edge.payload.get("alias") or imported_symbol
        if not import_source or not imported_symbol or alias != symbol:
            return False
        if not import_source.startswith("."):
            return False
        source_path = Path(source.location.path).as_posix()
        candidate_path = Path(candidate.location.path).as_posix()
        base = posixpath.dirname(source_path)
        requested = posixpath.normpath(posixpath.join(base, import_source))
        suffix = posixpath.splitext(requested)[1].lower()
        candidates = {requested} if suffix in {".js", ".jsx", ".ts", ".tsx"} else {
            requested + extension for extension in (".js", ".jsx", ".ts", ".tsx")
        } | {
            posixpath.join(requested, "index" + extension)
            for extension in (".js", ".jsx", ".ts", ".tsx")
        }
        return candidate_path in candidates and candidate.payload.get("name") == imported_symbol

    @staticmethod
    def _import_names_candidate(import_edge, candidate):
        imported = import_edge.payload.get("module") or import_edge.payload.get("import")
        package = candidate.payload.get("package_identity")
        name = candidate.payload.get("name")
        if not imported or not package or not name:
            return False
        imported = imported.removeprefix("module:").removeprefix("import:")
        return imported.endswith(f".{name}") and imported.rsplit(".", 1)[0] == package

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
            for call in BootstrapService._iter_current_function_body(node.body):
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

    @staticmethod
    def _iter_current_function_body(body):
        def walk(node):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                return
            yield node
            for child in ast.iter_child_nodes(node):
                yield from walk(child)

        for statement in body:
            yield from walk(statement)

    def _reject(self, snapshot_id, code, detail):
        self.repository.add_conflict(snapshot_id, code, detail)
        self.repository.fail_tasks(snapshot_id)
        return {
            "ok": False, "status": "staging", "code": code, "snapshot_id": snapshot_id,
            "diagnostics": detail.get("diagnostics", []),
            "diagnostic_counts": detail.get("diagnostic_counts", {}),
            **({"coverage": detail["coverage"]} if "coverage" in detail else {}),
        }

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
