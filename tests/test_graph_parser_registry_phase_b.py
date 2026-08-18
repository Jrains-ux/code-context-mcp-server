import unittest
from pathlib import Path

from code_context.graph import GraphParser, ParserRegistry, PythonGraphParser
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


if __name__ == "__main__":
    unittest.main()
