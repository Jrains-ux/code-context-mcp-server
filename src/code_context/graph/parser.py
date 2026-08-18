"""Python AST adapter for deterministic technical graph artifacts."""

import ast
from pathlib import Path
from typing import Any

from .artifacts import EdgeArtifact, GraphArtifact, NodeArtifact, SourceEvidence, SourceLocation


class PythonGraphParser:
    """Parse one Python source file without attempting dynamic dispatch resolution."""

    def parse(
        self,
        path: str | Path,
        source: str,
        *,
        source_revision: str,
        snapshot_revision: str,
        config_revision: str = "",
    ) -> GraphArtifact:
        file_path = Path(path)
        module_name = self._module_name(file_path)
        tree = ast.parse(source, filename=str(file_path))
        evidence = SourceEvidence(source_revision, snapshot_revision, config_revision)
        nodes: list[NodeArtifact] = []
        edges: list[EdgeArtifact] = []
        module_key = f"module:{module_name}"
        nodes.append(
            self._node("module", module_key, module_name, tree, file_path, evidence, snapshot_revision)
        )

        definitions: dict[str, str] = {}
        aliases: dict[str, str] = {}

        def visit_body(body: list[ast.stmt], parent_key: str, qualified_prefix: str, inherited_definitions: dict[str, str], inherited_aliases: dict[str, str], collect_imports: bool = True) -> None:
            scope_definitions = dict(inherited_definitions)
            self._collect_definition_keys(body, qualified_prefix, scope_definitions)
            scope_aliases = dict(inherited_aliases)
            if collect_imports:
                self._collect_imports_in_scope(body, module_name, parent_key, file_path, evidence, snapshot_revision, edges, scope_aliases)
            for statement in body:
                if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    kind = "class" if isinstance(statement, ast.ClassDef) else "function"
                    qualified = f"{qualified_prefix}.{statement.name}"
                    key = f"{kind}:{qualified}"
                    nodes.append(self._node(kind, key, statement.name, statement, file_path, evidence, snapshot_revision))
                    edges.append(self._edge("contains", parent_key, key, statement, file_path, evidence, snapshot_revision))
                    if isinstance(statement, ast.ClassDef):
                        visit_body(statement.body, key, qualified, scope_definitions, scope_aliases)
                    else:
                        # Methods may resolve module-level definitions, but a bare
                        # name must not resolve to another definition in the class
                        # body. Ordinary functions keep their current scope.
                        available_definitions = (
                            inherited_definitions if parent_key.startswith("class:") else scope_definitions
                        )
                        local_definitions = dict(available_definitions)
                        self._collect_definition_keys(statement.body, qualified, local_definitions)
                        # Function bodies inherit the current module-level aliases,
                        # but never aliases declared in a class body or enclosing
                        # function. A class body's inherited_aliases is the module
                        # scope; for ordinary scopes scope_aliases is already limited
                        # to the non-local aliases passed into that scope.
                        available_aliases = (
                            inherited_aliases if parent_key.startswith("class:") else scope_aliases
                        )
                        local_aliases = dict(available_aliases)
                        self._collect_imports_in_scope(statement.body, module_name, key, file_path, evidence, snapshot_revision, edges, local_aliases)
                        self._collect_calls(statement, key, local_definitions, local_aliases, file_path, evidence, snapshot_revision, edges)
                        # A nested function is a separate lexical scope. Its symbol table
                        # starts from the enclosing module/class scope, not the enclosing
                        # function's local imports or definitions.
                        visit_body(statement.body, key, qualified, inherited_definitions, inherited_aliases, collect_imports=False)
                elif isinstance(statement, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try)):
                    for nested in self._statement_bodies(statement):
                        visit_body(
                            nested,
                            parent_key,
                            qualified_prefix,
                            scope_definitions,
                            scope_aliases,
                            collect_imports=False,
                        )

        visit_body(tree.body, module_key, module_name, definitions, aliases)
        return GraphArtifact(tuple(nodes), tuple(edges), source_revision, snapshot_revision)

    def _collect_definition_keys(self, body: list[ast.stmt], qualified_prefix: str, definitions: dict[str, str]) -> None:
        for statement in body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(statement, ast.ClassDef) else "function"
                qualified = f"{qualified_prefix}.{statement.name}"
                definitions.setdefault(statement.name, f"{kind}:{qualified}")
            elif isinstance(statement, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try)):
                for nested in self._statement_bodies(statement):
                    self._collect_definition_keys(nested, qualified_prefix, definitions)

    @staticmethod
    def _module_name(path: Path) -> str:
        name = path.with_suffix("").as_posix().strip("/")
        if name.endswith("/__init__"):
            name = name[: -len("/__init__")]
        return name.replace("/", ".")

    @staticmethod
    def _node(kind: str, key: str, name: str, node: ast.AST, path: Path, evidence: SourceEvidence, snapshot: str) -> NodeArtifact:
        qualified_name = key.split(":", 1)[1]
        return NodeArtifact(
            kind,
            key,
            name,
            PythonGraphParser._location(node, path),
            evidence,
            snapshot,
            {"name": name, "qualified_name": qualified_name},
        )

    @staticmethod
    def _edge(edge_type: str, source: str, target: str, node: ast.AST, path: Path, evidence: SourceEvidence, snapshot: str, payload: dict[str, Any] | None = None) -> EdgeArtifact:
        return EdgeArtifact(edge_type, source, target, PythonGraphParser._location(node, path), evidence, snapshot, payload or {"resolution": "static"})

    @staticmethod
    def _location(node: ast.AST, path: Path) -> SourceLocation:
        return SourceLocation(str(path), getattr(node, "lineno", 1), getattr(node, "col_offset", 0), getattr(node, "end_lineno", None), getattr(node, "end_col_offset", None))

    def _collect_imports_in_scope(self, body, module_name, owner_key, path, evidence, snapshot, edges, aliases):
        for node in self._iter_scope_nodes(body):
            if isinstance(node, ast.Import):
                for item in node.names:
                    imported = item.name
                    alias = item.asname or imported.split(".")[0]
                    aliases[alias] = f"module:{imported}"
                    edges.append(self._edge("imports", owner_key, f"module:{imported}", node, path, evidence, snapshot, {"import": imported, "alias": alias}))
            elif isinstance(node, ast.ImportFrom):
                base = self._resolve_import_base(module_name, node.level, node.module)
                for item in node.names:
                    if item.name == "*":
                        continue
                    target_module = f"{base}.{item.name}" if node.module is None else base
                    aliases[item.asname or item.name] = f"import:{target_module}.{item.name}" if node.module else f"import:{target_module}"
                    edges.append(self._edge("imports", owner_key, f"module:{target_module}", node, path, evidence, snapshot, {"module": target_module, "symbol": item.name}))

    @staticmethod
    def _resolve_import_base(module_name: str, level: int, imported_module: str | None) -> str:
        if level == 0:
            return imported_module or ""
        package = module_name.split(".")[:-1]
        parent_count = max(0, len(package) - (level - 1))
        prefix = package[:parent_count]
        if imported_module:
            prefix.append(imported_module)
        return ".".join(prefix)

    def _iter_scope_nodes(self, body):
        def walk(node):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                return
            yield node
            for child in ast.iter_child_nodes(node):
                yield from walk(child)

        for statement in body:
            yield from walk(statement)

    def _collect_calls(self, function, source_key, definitions, aliases, path, evidence, snapshot, edges):
        for node in self._iter_scope_nodes(function.body):
            if not isinstance(node, ast.Call):
                continue
            target = None
            if isinstance(node.func, ast.Name):
                target = definitions.get(node.func.id) or aliases.get(node.func.id)
            if target:
                edges.append(self._edge("calls", source_key, target, node, path, evidence, snapshot, {"resolution": "static", "symbol": ast.unparse(node.func)}))

    @staticmethod
    def _statement_bodies(statement):
        for attr in ("body", "orelse", "finalbody"):
            value = getattr(statement, attr, None)
            if value:
                yield value
        for handler in getattr(statement, "handlers", []):
            if handler.body:
                yield handler.body
