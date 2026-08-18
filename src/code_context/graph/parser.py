"""Python AST adapter for deterministic technical graph artifacts."""

import ast
import re
from pathlib import Path
from typing import Any, Protocol, Sequence, runtime_checkable

from .artifacts import EdgeArtifact, GraphArtifact, GraphDiagnostic, NodeArtifact, SourceEvidence, SourceLocation


@runtime_checkable
class GraphParser(Protocol):
    parser_id: str
    version: str
    language: str
    supported_extensions: frozenset[str]

    def parse(
        self,
        path: str | Path,
        source: str,
        *,
        source_revision: str,
        snapshot_revision: str,
        config_revision: str = "",
    ) -> GraphArtifact: ...


class ParserRegistry:
    """Deterministically select a parser by its longest supported suffix."""

    def __init__(self, parsers: Sequence[GraphParser] = ()):
        self._parsers: dict[str, GraphParser] = {}
        for parser in parsers:
            self.register(parser)

    def register(self, parser: GraphParser) -> None:
        normalized = [self._normalize_suffix(extension) for extension in parser.supported_extensions]
        conflicts = [suffix for suffix in normalized if suffix in self._parsers]
        if conflicts:
            raise ValueError(f"parser suffix already registered: {sorted(conflicts)[0]}")
        self._parsers.update({suffix: parser for suffix in normalized})

    def detect(self, path: str | Path) -> GraphParser | None:
        name = Path(path).name.lower()
        matches = [suffix for suffix in self._parsers if name.endswith(suffix)]
        if not matches:
            return None
        return self._parsers[max(matches, key=len)]

    def parse(
        self,
        path: str | Path,
        source: str,
        *,
        source_revision: str,
        snapshot_revision: str,
        config_revision: str = "",
    ) -> GraphArtifact:
        parser = self.detect(path)
        if parser is None:
            return GraphArtifact(
                (), (), source_revision, snapshot_revision,
                (GraphDiagnostic(
                    "UNSUPPORTED_FILE_SUFFIX",
                    str(path),
                    f"no parser registered for file suffix: {Path(path).suffix or '<none>'}",
                    {"suffix": Path(path).suffix.lower()},
                ),),
            )
        try:
            return parser.parse(
                path, source,
                source_revision=source_revision,
                snapshot_revision=snapshot_revision,
                config_revision=config_revision,
            )
        except SyntaxError as error:
            return GraphArtifact(
                (), (), source_revision, snapshot_revision,
                (GraphDiagnostic(
                    f"{parser.language.upper()}_SYNTAX_ERROR",
                    str(path),
                    str(error),
                    {"line": error.lineno, "column": error.offset},
                ),),
            )

    @staticmethod
    def _normalize_suffix(suffix: str) -> str:
        suffix = suffix.lower()
        return suffix if suffix.startswith(".") else f".{suffix}"


class PythonGraphParser:
    """Parse one Python source file without attempting dynamic dispatch resolution."""

    parser_id = "python-ast"
    version = "1"
    language = "python"
    supported_extensions = frozenset({".py"})

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
        evidence = SourceEvidence(
            source_revision, snapshot_revision, config_revision,
            parser=self.parser_id,
            metadata={"parser_id": self.parser_id, "parser_version": self.version, "language": self.language},
        )
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
            {
                "name": name,
                "qualified_name": qualified_name,
                "language": "python",
                "extraction_method": "ast",
                "evidence_level": "observed",
                "parse_quality": "complete",
                "sub_kind": kind,
                "roles": ("container",) if kind == "module" else (("type",) if kind == "class" else ("callable",)),
                "purpose": "source declaration",
            },
        )

    @staticmethod
    def _edge(edge_type: str, source: str, target: str, node: ast.AST, path: Path, evidence: SourceEvidence, snapshot: str, payload: dict[str, Any] | None = None) -> EdgeArtifact:
        return EdgeArtifact(
            edge_type, source, target, PythonGraphParser._location(node, path), evidence, snapshot,
            {
                "resolution": "static",
                "language": "python",
                "extraction_method": "ast",
                "evidence_level": "observed",
                "parse_quality": "complete",
                "sub_kind": edge_type,
                "roles": ("relation",),
                "purpose": "source relationship",
                **(payload or {}),
            },
        )

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


class _HeuristicGraphParser:
    """Small, dependency-free declaration scanner shared by the basic parsers."""

    parser_id = "heuristic"
    version = "1"
    language = ""
    supported_extensions = frozenset()

    _declaration_patterns = ()

    def parse(self, path, source, *, source_revision, snapshot_revision, config_revision=""):
        file_path = Path(path)
        evidence = SourceEvidence(
            source_revision, snapshot_revision, config_revision,
            parser=self.parser_id,
            confidence="medium",
            metadata={"parser_id": self.parser_id, "parser_version": self.version, "language": self.language},
        )
        if not source.strip():
            return GraphArtifact((), (), source_revision, snapshot_revision)

        lines = source.splitlines()
        quality = "complete" if self._balanced(source) else "partial"
        root_kind, root_name = self._root(file_path, lines)
        root_key = f"{root_kind}:{root_name}"
        nodes = [self._node(root_kind, root_key, root_name, 1, file_path, evidence, snapshot_revision, quality)]
        edges = []
        symbols = {}
        declarations = []
        imports = []

        for line_number, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith(("//", "#", "/*", "*")):
                continue
            for kind, name, extra in self._declarations(stripped):
                key = f"{kind}:{root_name}.{name}"
                if key not in {node.canonical_key for node in nodes}:
                    nodes.append(self._node(kind, key, name, line_number, file_path, evidence, snapshot_revision, quality, extra))
                    edges.append(self._edge("contains", root_key, key, line_number, file_path, evidence, snapshot_revision, quality=quality))
                symbols[name] = key
                declarations.append((kind, name, key, extra, line_number))
            for imported in self._imports(stripped):
                imports.append((imported, line_number))

        for imported, line_number in imports:
            import_name = imported.rsplit(".", 1)[-1].split("/", 1)[-1]
            import_key = f"import:{root_name}.{import_name}"
            nodes.append(self._node("import", import_key, imported, line_number, file_path, evidence, snapshot_revision, quality, {"import": imported}))
            edges.append(self._edge("imports", root_key, import_key, line_number, file_path, evidence, snapshot_revision, {"import": imported, "resolution": "external"}, quality))

        for kind, name, key, extra, line_number in declarations:
            for relation in ("extends", "implements"):
                for target_name in extra.get(relation, ()):
                    target_key = symbols.get(target_name, f"external:{target_name}")
                    edges.append(self._edge(relation, key, target_key, line_number, file_path, evidence, snapshot_revision, {"symbol": target_name, "resolution": "static" if target_name in symbols else "external"}, quality))
            if kind in {"function", "method"}:
                body = self._body_after_declaration(lines, line_number)
                for called in self._calls(body):
                    target_key = symbols.get(called, f"external:{called}")
                    edges.append(self._edge("calls", key, target_key, line_number, file_path, evidence, snapshot_revision, {"symbol": called, "resolution": "static" if called in symbols else "external"}, quality))

        for kind, name, key, _extra, line_number in declarations:
            if self.language in {"javascript", "typescript"} and any(line.strip().startswith("export") and name in line for line in lines[line_number - 1:line_number]):
                export_key = f"export:{root_name}.{name}"
                nodes.append(self._node("export", export_key, name, line_number, file_path, evidence, snapshot_revision, quality))
                edges.append(self._edge("defines", export_key, key, line_number, file_path, evidence, snapshot_revision, quality=quality))

        diagnostics = ()
        if quality == "partial":
            diagnostics = (GraphDiagnostic(
                "HEURISTIC_PARSE_PARTIAL", str(file_path),
                "heuristic parser found unbalanced delimiters; extracted declarations are partial",
                {"language": self.language, "parse_quality": quality},
            ),)
        return GraphArtifact(tuple(nodes), tuple(edges), source_revision, snapshot_revision, diagnostics)

    def _declarations(self, line):
        result = []
        for pattern, kind in self._declaration_patterns:
            match = pattern.search(line)
            if not match:
                continue
            name = match.group("name")
            extra = {}
            for relation in ("extends", "implements"):
                value = match.groupdict().get(relation)
                if value:
                    extra[relation] = tuple(item.strip() for item in value.split(",") if item.strip())
            result.append((kind, name, extra))
            break
        return result

    @staticmethod
    def _balanced(source):
        pairs = {"{": "}", "(": ")", "[": "]"}
        stack = []
        for char in source:
            if char in pairs:
                stack.append(pairs[char])
            elif char in pairs.values():
                if not stack or stack.pop() != char:
                    return False
        return not stack

    @staticmethod
    def _body_after_declaration(lines, line_number):
        return "\n".join(lines[line_number - 1:line_number + 20])

    @staticmethod
    def _calls(text):
        ignored = {"if", "for", "while", "switch", "catch", "func", "function", "class", "interface", "new", "return"}
        constructors = re.findall(r"\bnew\s+([A-Za-z_$][\w$]*)\s*\(", text)
        calls = re.findall(r"\b([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*\(", text)
        return tuple(dict.fromkeys(name for name in (*constructors, *calls) if name not in ignored))

    def _imports(self, line):
        return ()

    def _root(self, path, lines):
        return "module", path.with_suffix("").as_posix().replace("/", ".")

    @staticmethod
    def _node(kind, key, name, line_number, path, evidence, snapshot, quality, extra=None):
        roles = {"module": ("container",), "package": ("container",), "import": ("dependency",), "export": ("api",), "class": ("type",), "interface": ("contract",), "struct": ("type",), "enum": ("type",), "function": ("callable",), "method": ("callable",)}.get(kind, ("code",))
        return NodeArtifact(
            kind, key, name, SourceLocation(str(path), line_number, 0), evidence, snapshot,
            {"name": name, "qualified_name": key.split(":", 1)[1], "language": evidence.metadata["language"],
             "extraction_method": "heuristic", "evidence_level": "static_analysis", "parse_quality": quality,
             "sub_kind": kind, "roles": roles, "purpose": "source declaration", **(extra or {})},
        )

    @staticmethod
    def _edge(edge_type, source, target, line_number, path, evidence, snapshot, extra=None, quality="complete"):
        return EdgeArtifact(
            edge_type, source, target, SourceLocation(str(path), line_number, 0), evidence, snapshot,
            {"language": evidence.metadata["language"], "extraction_method": "heuristic", "evidence_level": "static_analysis",
             "parse_quality": quality, "sub_kind": edge_type, "roles": ("relation",), "purpose": "source relationship",
             "resolution": "static", **(extra or {})},
        )


class JavaGraphParser(_HeuristicGraphParser):
    parser_id = "java-heuristic"
    language = "java"
    supported_extensions = frozenset({".java"})
    _declaration_patterns = (
        (re.compile(r"\binterface\s+(?P<name>[A-Za-z_$][\w$]*)"), "interface"),
        (re.compile(r"\benum\s+(?P<name>[A-Za-z_$][\w$]*)"), "enum"),
        (re.compile(r"\bclass\s+(?P<name>[A-Za-z_$][\w$]*)(?:\s+extends\s+(?P<extends>[\w$]+))?(?:\s+implements\s+(?P<implements>[\w$,. ]+))?"), "class"),
        (re.compile(r"\b(?!(?:new|return)\b)(?:public|private|protected|static|final|abstract|synchronized|native\s+)*[\w$<>\[\],.?]+\s+(?P<name>[A-Za-z_$][\w$]*)\s*\([^;]*\)"), "method"),
    )

    def _imports(self, line):
        match = re.search(r"\bimport\s+(?:static\s+)?([\w$.]+)", line)
        return (match.group(1),) if match else ()

    def _root(self, path, lines):
        match = next((re.search(r"\bpackage\s+([\w.]+)", line) for line in lines if re.search(r"\bpackage\s+([\w.]+)", line)), None)
        return "package", match.group(1) if match else path.with_suffix("").as_posix().replace("/", ".")


class GoGraphParser(_HeuristicGraphParser):
    parser_id = "go-heuristic"
    language = "go"
    supported_extensions = frozenset({".go"})
    _declaration_patterns = (
        (re.compile(r"\btype\s+(?P<name>\w+)\s+struct\b"), "struct"),
        (re.compile(r"\btype\s+(?P<name>\w+)\s+interface\b"), "interface"),
        (re.compile(r"\bfunc\s*\([^)]*\)\s*(?P<name>\w+)\s*\("), "method"),
        (re.compile(r"\bfunc\s+(?P<name>\w+)\s*\("), "function"),
    )

    def _imports(self, line):
        return tuple(re.findall(r"\bimport\s+(?:\w+\s+)?\"([^\"]+)\"", line))

    def _root(self, path, lines):
        match = next((re.search(r"\bpackage\s+(\w+)", line) for line in lines if re.search(r"\bpackage\s+(\w+)", line)), None)
        return "package", match.group(1) if match else path.stem


class JavaScriptGraphParser(_HeuristicGraphParser):
    parser_id = "javascript-heuristic"
    language = "javascript"
    supported_extensions = frozenset({".js", ".jsx", ".ts", ".tsx"})
    _declaration_patterns = (
        (re.compile(r"\binterface\s+(?P<name>[A-Za-z_$][\w$]*)"), "interface"),
        (re.compile(r"\bclass\s+(?P<name>[A-Za-z_$][\w$]*)(?:\s+extends\s+(?P<extends>[\w$]+))?(?:\s+implements\s+(?P<implements>[\w$,. ]+))?"), "class"),
        (re.compile(r"\bfunction\s+(?P<name>[A-Za-z_$][\w$]*)\s*\("), "function"),
        (re.compile(r"^\s*(?:public|private|protected|static|async|get|set)?\s*(?P<name>[A-Za-z_$][\w$]*)\s*\([^;]*\)\s*[{:]"), "method"),
    )

    def parse(self, path, source, *, source_revision, snapshot_revision, config_revision=""):
        self.language = "typescript" if Path(path).suffix.lower() in {".ts", ".tsx"} else "javascript"
        return super().parse(path, source, source_revision=source_revision, snapshot_revision=snapshot_revision, config_revision=config_revision)

    def _imports(self, line):
        match = re.search(r"\bimport\s+(?:.+?\s+from\s+)?[\'\"]([^\'\"]+)[\'\"]", line)
        return (match.group(1),) if match else ()

    def _root(self, path, lines):
        return "module", path.with_suffix("").as_posix().replace("/", ".")
