import unittest
from pathlib import Path

from code_context.graph import (
    GoGraphParser,
    GraphParser,
    JavaGraphParser,
    JavaScriptGraphParser,
    ParserRegistry,
    PythonGraphParser,
)
from code_context.graph.artifacts import GraphArtifact


class _ParserStub:
    def __init__(self, parser_id, extensions):
        self.parser_id = parser_id
        self.version = "1"
        self.language = parser_id
        self.supported_extensions = frozenset(extensions)

    def parse(self, path, source, *, source_revision, snapshot_revision, config_revision=""):
        return GraphArtifact((), (), source_revision, snapshot_revision)


class ParserRegistryPhaseBTest(unittest.TestCase):
    def test_graph_parser_protocol_exposes_parser_metadata_and_parse(self):
        parser = _ParserStub("stub", {".stub"})

        self.assertIsInstance(parser, GraphParser)
        self.assertEqual(parser.parser_id, "stub")
        self.assertEqual(parser.supported_extensions, {".stub"})
        self.assertIsInstance(parser.parse(
            Path("sample.stub"), "", source_revision="src", snapshot_revision="snap"
        ), GraphArtifact)

    def test_registry_selects_longest_matching_suffix_independent_of_registration_order(self):
        generic = _ParserStub("generic", {".tar"})
        specific = _ParserStub("specific", {".tar.gz"})

        first = ParserRegistry([generic, specific])
        second = ParserRegistry([specific, generic])

        self.assertIs(first.detect("bundle.tar.gz"), specific)
        self.assertIs(second.detect("bundle.tar.gz"), specific)

    def test_registry_rejects_duplicate_suffix_registration(self):
        registry = ParserRegistry()
        registry.register(_ParserStub("first", {".dup"}))

        with self.assertRaises(ValueError):
            registry.register(_ParserStub("second", {".dup"}))

    def test_registry_does_not_leave_partial_registration_after_multi_suffix_conflict(self):
        registry = ParserRegistry([_ParserStub("existing", {".conflict"})])

        with self.assertRaises(ValueError):
            registry.register(_ParserStub("multi", {".new", ".conflict"}))

        self.assertIsNone(registry.detect("sample.new"))
        self.assertIsNotNone(registry.detect("sample.conflict"))

    def test_registry_returns_unknown_suffix_diagnostic(self):
        result = ParserRegistry().parse(
            Path("sample.unknown"), "", source_revision="src", snapshot_revision="snap"
        )

        self.assertEqual(result.nodes, ())
        self.assertEqual(result.edges, ())
        self.assertEqual(len(result.diagnostics), 1)
        self.assertEqual(result.diagnostics[0].code, "UNSUPPORTED_FILE_SUFFIX")
        self.assertEqual(result.diagnostics[0].path, "sample.unknown")

    def test_python_parser_is_registered_and_emits_typed_metadata(self):
        parser = PythonGraphParser()
        registry = ParserRegistry([parser])
        result = registry.parse(
            Path("pkg/handler.py"), "class Handler:\n    pass\n",
            source_revision="src", snapshot_revision="snap", config_revision="cfg",
        )

        self.assertIs(registry.detect("pkg/handler.py"), parser)
        self.assertEqual(result.diagnostics, ())
        for artifact in (*result.nodes, *result.edges):
            self.assertEqual(artifact.payload["language"], "python")
            self.assertEqual(artifact.payload["extraction_method"], "ast")
            self.assertEqual(artifact.payload["evidence_level"], "observed")
            self.assertEqual(artifact.payload["parse_quality"], "complete")
            self.assertEqual(artifact.evidence.metadata["parser_id"], "python-ast")
            self.assertEqual(artifact.evidence.metadata["parser_version"], "1")
            self.assertEqual(artifact.evidence.metadata["language"], "python")

    def test_registry_converts_python_syntax_error_to_diagnostic(self):
        result = ParserRegistry([PythonGraphParser()]).parse(
            Path("broken.py"), "def broken(:\n    pass\n",
            source_revision="src", snapshot_revision="snap",
        )

        self.assertEqual(result.nodes, ())
        self.assertEqual(result.edges, ())
        self.assertEqual(len(result.diagnostics), 1)
        self.assertEqual(result.diagnostics[0].code, "PYTHON_SYNTAX_ERROR")
        self.assertEqual(result.diagnostics[0].path, "broken.py")

    def test_java_parser_extracts_basic_nodes_edges_and_metadata(self):
        source = """package demo;
import java.util.List;
interface Greeter { void greet(); }
class Base {}
class Hello extends Base implements Greeter {
    public void greet() { Helper.run(); new Worker(); }
}
"""
        result = JavaGraphParser().parse("src/Hello.java", source, source_revision="src", snapshot_revision="snap")
        kinds = {node.kind for node in result.nodes}
        edge_types = {edge.edge_type for edge in result.edges}
        self.assertTrue({"package", "class", "interface", "method", "import"} <= kinds)
        self.assertTrue({"contains", "imports", "extends", "implements", "calls"} <= edge_types)
        self.assertTrue(all(node.location.start_line > 0 for node in result.nodes))
        self.assertTrue(all(node.payload["language"] == "java" for node in result.nodes))
        self.assertTrue(all(node.payload["extraction_method"] == "heuristic" for node in result.nodes))
        self.assertTrue(all(node.evidence.metadata["parser_version"] == JavaGraphParser.version for node in result.nodes))

    def test_java_parser_preserves_static_and_constructor_call_symbols_as_external_when_unbound(self):
        result = JavaGraphParser().parse(
            "Demo.java", "class Demo {\n    void run() { Helper.execute(); new Worker(); }\n}",
            source_revision="src", snapshot_revision="snap",
        )
        targets = {edge.target_key for edge in result.edges if edge.edge_type == "calls"}
        external = {edge.target_key for edge in result.edges if edge.edge_type == "calls" and edge.payload["resolution"] == "external"}

        self.assertIn("external:Helper.execute", targets)
        self.assertIn("external:Worker", external)

    def test_heuristic_calls_are_limited_to_the_current_function_body(self):
        result = JavaGraphParser().parse(
            "Demo.java",
            "class Demo { void run() { helper(); } void other() { otherOnly(); } }",
            source_revision="src", snapshot_revision="snap",
        )

        run_key = next(node.canonical_key for node in result.nodes if node.kind == "method" and node.name == "run")
        run_calls = [edge for edge in result.edges if edge.edge_type == "calls" and edge.source_key == run_key]
        self.assertEqual({edge.target_key for edge in run_calls}, {"external:helper"})

    def test_dynamic_bracket_calls_are_not_reported_as_static(self):
        result = JavaScriptGraphParser().parse(
            "demo.js", "function run() { obj[method](); }",
            source_revision="src", snapshot_revision="snap",
        )

        calls = [edge for edge in result.edges if edge.edge_type == "calls"]
        self.assertTrue(calls)
        self.assertTrue(all(edge.payload["resolution"] != "static" for edge in calls))
        self.assertTrue(any(edge.payload["resolution"] in {"unresolved", "external"} for edge in calls))

    def test_java_and_go_file_identities_prevent_same_package_key_collisions(self):
        java_source = "package demo; class Shared {}"
        go_source = "package demo\ntype Shared struct {}"
        java_a = JavaGraphParser().parse("src/A.java", java_source, source_revision="src", snapshot_revision="snap")
        java_b = JavaGraphParser().parse("src/B.java", java_source, source_revision="src", snapshot_revision="snap")
        go_a = GoGraphParser().parse("src/a.go", go_source, source_revision="src", snapshot_revision="snap")
        go_b = GoGraphParser().parse("src/b.go", go_source, source_revision="src", snapshot_revision="snap")

        self.assertNotEqual(java_a.nodes[0].canonical_key, java_b.nodes[0].canonical_key)
        self.assertNotEqual(go_a.nodes[0].canonical_key, go_b.nodes[0].canonical_key)
        self.assertEqual(len({node.canonical_key for node in (*java_a.nodes, *java_b.nodes)}), len(java_a.nodes) + len(java_b.nodes))
        self.assertEqual(len({node.canonical_key for node in (*go_a.nodes, *go_b.nodes)}), len(go_a.nodes) + len(go_b.nodes))

    def test_go_parser_extracts_basic_nodes_edges_and_metadata(self):
        source = """package main
import \"fmt\"
type User struct { Name string }
type Runner interface { Run() }
func main() { fmt.Println(\"hi\") }
func (u User) Run() { main() }
"""
        result = GoGraphParser().parse("cmd/main.go", source, source_revision="src", snapshot_revision="snap")
        kinds = {node.kind for node in result.nodes}
        edge_types = {edge.edge_type for edge in result.edges}
        self.assertTrue({"package", "struct", "interface", "function", "method", "import"} <= kinds)
        self.assertTrue({"contains", "imports", "calls"} <= edge_types)
        self.assertTrue(all(node.payload["language"] == "go" for node in result.nodes))
        self.assertTrue(all(node.payload["extraction_method"] == "heuristic" for node in result.nodes))

    def test_go_parser_extracts_grouped_imports(self):
        result = GoGraphParser().parse(
            "cmd/main.go",
            'package main\nimport (\n    "fmt"\n    alias "net/http"\n)\nfunc main() {}\n',
            source_revision="src", snapshot_revision="snap",
        )

        imports = [node for node in result.nodes if node.kind == "import"]
        self.assertEqual({node.payload["import"] for node in imports}, {"fmt", "net/http"})

    def test_java_parser_extracts_method_from_one_line_class_declaration(self):
        result = JavaGraphParser().parse(
            "Demo.java", "class Demo { void run() {} }",
            source_revision="src", snapshot_revision="snap",
        )

        self.assertTrue(any(node.kind == "method" and node.name == "run" for node in result.nodes))

    def test_javascript_parser_extracts_js_and_typescript_basics(self):
        source = """import { helper } from './helper';
export interface Service { run(): void }
export class App implements Service {
    run() { helper(); }
}
export function start() { new App().run(); }
"""
        result = JavaScriptGraphParser().parse("src/app.ts", source, source_revision="src", snapshot_revision="snap")
        kinds = {node.kind for node in result.nodes}
        edge_types = {edge.edge_type for edge in result.edges}
        self.assertTrue({"module", "interface", "class", "method", "function", "import", "export"} <= kinds)
        self.assertTrue({"contains", "imports", "defines", "implements", "calls"} <= edge_types)
        self.assertTrue(all(node.payload["language"] == "typescript" for node in result.nodes))
        self.assertTrue(all(node.payload["extraction_method"] == "heuristic" for node in result.nodes))

    def test_javascript_parser_keeps_language_local_to_each_path(self):
        parser = JavaScriptGraphParser()
        typescript = parser.parse("src/app.ts", "interface App {}", source_revision="src", snapshot_revision="snap")
        self.assertEqual(parser.language, "javascript")
        javascript = parser.parse("src/app.js", "class App {}", source_revision="src", snapshot_revision="snap")

        self.assertEqual({node.payload["language"] for node in typescript.nodes}, {"typescript"})
        self.assertEqual({node.payload["language"] for node in javascript.nodes}, {"javascript"})
        self.assertEqual(parser.language, "javascript")

    def test_heuristic_parsers_degrade_empty_and_unbalanced_sources(self):
        for parser, path in ((JavaGraphParser(), "Empty.java"), (GoGraphParser(), "empty.go"), (JavaScriptGraphParser(), "empty.ts")):
            empty = parser.parse(path, "", source_revision="src", snapshot_revision="snap")
            self.assertEqual(empty.nodes, ())
            self.assertEqual(empty.edges, ())
            self.assertEqual(empty.diagnostics, ())

            degraded = parser.parse(path, "class Broken {", source_revision="src", snapshot_revision="snap")
            self.assertTrue(degraded.diagnostics)
            self.assertTrue(any(node.payload["parse_quality"] == "partial" for node in degraded.nodes))

    def test_heuristic_nodes_and_edges_include_the_required_semantic_payload(self):
        result = JavaGraphParser().parse(
            "Demo.java", "class Demo { void run() { helper(); } }",
            source_revision="src", snapshot_revision="snap",
        )
        required = {"language", "extraction_method", "evidence_level", "parse_quality", "sub_kind", "roles", "purpose"}

        for artifact in (*result.nodes, *result.edges):
            self.assertTrue(required <= set(artifact.payload))

    def test_python_artifacts_keep_the_additive_semantic_payload_contract(self):
        result = PythonGraphParser().parse(
            "demo.py", "def helper():\n    pass\ndef run():\n    helper()\n",
            source_revision="src", snapshot_revision="snap",
        )
        required = {"language", "extraction_method", "evidence_level", "parse_quality", "sub_kind", "roles", "purpose"}

        for artifact in (*result.nodes, *result.edges):
            self.assertTrue(required <= set(artifact.payload))


if __name__ == "__main__":
    unittest.main()
