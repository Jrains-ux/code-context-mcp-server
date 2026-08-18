import unittest
from pathlib import Path
from types import MappingProxyType

from code_context.graph.parser import PythonGraphParser


class PythonGraphParserTest(unittest.TestCase):
    def test_emits_typed_nodes_with_stable_keys_locations_evidence_and_revision(self):
        source = "class Handler:\n    def run(self):\n        return 1\n"

        graph = PythonGraphParser().parse(
            Path("pkg/handler.py"), source, source_revision="src-1", snapshot_revision="snap-1", config_revision="cfg-1"
        )

        self.assertEqual(
            [node.kind for node in graph.nodes], ["module", "class", "function"]
        )
        self.assertEqual(graph.nodes[0].canonical_key, "module:pkg.handler")
        self.assertEqual(graph.nodes[1].canonical_key, "class:pkg.handler.Handler")
        self.assertEqual(graph.nodes[2].canonical_key, "function:pkg.handler.Handler.run")
        self.assertEqual(graph.nodes[2].location.start_line, 2)
        self.assertEqual(graph.nodes[2].location.end_line, 3)
        self.assertEqual(graph.nodes[2].snapshot_revision, "snap-1")
        self.assertEqual(graph.nodes[2].evidence.source_revision, "src-1")

        self.assertEqual(graph.source_revision, "src-1")
        self.assertEqual(graph.snapshot_revision, "snap-1")
        self.assertEqual(graph.nodes[2].evidence.config_revision, "cfg-1")
        self.assertEqual(graph.nodes[2].evidence.parser, "python-ast")
        self.assertEqual(graph.nodes[2].evidence.confidence, "high")
        self.assertIsInstance(graph.nodes[2].payload, MappingProxyType)

    def test_emits_contains_imports_and_static_calls_edges(self):
        source = (
            "import os\n"
            "from pkg.helpers import normalize as norm\n"
            "\n"
            "def helper(value):\n"
            "    return value\n"
            "\n"
            "def run(value):\n"
            "    helper(value)\n"
            "    norm(value)\n"
            "    os.path.join('a', 'b')\n"
        )

        graph = PythonGraphParser().parse(
            Path("pkg/service.py"), source, source_revision="src-1", snapshot_revision="snap-1"
        )

        edge_types = {(edge.edge_type, edge.source_key, edge.target_key) for edge in graph.edges}
        self.assertIn(
            ("contains", "module:pkg.service", "function:pkg.service.helper"), edge_types
        )
        self.assertIn(
            ("contains", "module:pkg.service", "function:pkg.service.run"), edge_types
        )
        self.assertIn(("imports", "module:pkg.service", "module:os"), edge_types)
        self.assertIn(
            ("imports", "module:pkg.service", "module:pkg.helpers"), edge_types
        )
        self.assertIn(
            ("calls", "function:pkg.service.run", "function:pkg.service.helper"), edge_types
        )
        self.assertIn(
            ("calls", "function:pkg.service.run", "import:pkg.helpers.normalize"), edge_types
        )
        calls = [edge for edge in graph.edges if edge.edge_type == "calls"]
        self.assertTrue(all(edge.evidence.source_revision == "src-1" for edge in calls))
        self.assertEqual({edge.location.start_line for edge in calls}, {8, 9})
        self.assertTrue(all(edge.snapshot_revision == "snap-1" for edge in graph.edges))

    def test_scopes_nested_calls_and_local_imports_to_their_lexical_function(self):
        source = (
            "def outer():\n"
            "    from outer_mod import run\n"
            "    def inner():\n"
            "        from inner_mod import run\n"
            "        run()\n"
            "    run()\n"
            "\n"
            "def sibling():\n"
            "    run()\n"
        )

        graph = PythonGraphParser().parse(
            Path("pkg/service.py"), source, source_revision="src-1", snapshot_revision="snap-1"
        )

        calls = {(edge.source_key, edge.target_key) for edge in graph.edges if edge.edge_type == "calls"}
        self.assertIn(("function:pkg.service.outer", "import:outer_mod.run"), calls)
        self.assertIn(("function:pkg.service.outer.inner", "import:inner_mod.run"), calls)
        self.assertNotIn(("function:pkg.service.outer", "import:inner_mod.run"), calls)
        self.assertNotIn(("function:pkg.service.sibling", "import:outer_mod.run"), calls)
        self.assertNotIn(("function:pkg.service.sibling", "import:inner_mod.run"), calls)

    def test_resolves_relative_from_import_targets(self):
        source = "from . import helper\nfrom .utils import normalize\n\ndef run(value):\n    helper(value)\n    normalize(value)\n"

        graph = PythonGraphParser().parse(
            Path("pkg/service.py"), source, source_revision="src-1", snapshot_revision="snap-1"
        )

        imports = {(edge.source_key, edge.target_key) for edge in graph.edges if edge.edge_type == "imports"}
        calls = {(edge.source_key, edge.target_key) for edge in graph.edges if edge.edge_type == "calls"}
        self.assertIn(("module:pkg.service", "module:pkg.helper"), imports)
        self.assertIn(("module:pkg.service", "module:pkg.utils"), imports)
        self.assertIn(("function:pkg.service.run", "import:pkg.helper"), calls)
        self.assertIn(("function:pkg.service.run", "import:pkg.utils.normalize"), calls)

    def test_function_local_import_does_not_leak_into_nested_function(self):
        source = "def outer():\n    from outer_mod import run\n    def inner():\n        run()\n    run()\n"

        graph = PythonGraphParser().parse(
            Path("pkg/service.py"), source, source_revision="src-1", snapshot_revision="snap-1"
        )

        calls = {(edge.source_key, edge.target_key) for edge in graph.edges if edge.edge_type == "calls"}
        self.assertIn(("function:pkg.service.outer", "import:outer_mod.run"), calls)
        self.assertNotIn(("function:pkg.service.outer.inner", "import:outer_mod.run"), calls)

    def test_control_flow_import_is_emitted_once_for_its_lexical_owner(self):
        source = (
            "def run(value):\n"
            "    if value:\n"
            "        from pkg.helpers import normalize\n"
            "        normalize(value)\n"
            "    try:\n"
            "        from pkg.helpers import normalize as norm\n"
            "        norm(value)\n"
            "    except ValueError:\n"
            "        pass\n"
        )

        graph = PythonGraphParser().parse(
            Path("pkg/service.py"), source, source_revision="src-1", snapshot_revision="snap-1"
        )

        imports = [
            edge for edge in graph.edges
            if edge.edge_type == "imports" and edge.target_key == "module:pkg.helpers"
        ]
        self.assertEqual(len(imports), 2)
        self.assertEqual({edge.source_key for edge in imports}, {"function:pkg.service.run"})

    def test_module_control_flow_import_is_emitted_once_for_module_owner(self):
        source = (
            "if True:\n"
            "    from pkg.helpers import normalize\n"
            "\n"
            "def run(value):\n"
            "    normalize(value)\n"
        )

        graph = PythonGraphParser().parse(
            Path("pkg/service.py"), source, source_revision="src-1", snapshot_revision="snap-1"
        )

        imports = [
            edge for edge in graph.edges
            if edge.edge_type == "imports" and edge.target_key == "module:pkg.helpers"
        ]
        self.assertEqual(len(imports), 1)
        self.assertEqual(imports[0].source_key, "module:pkg.service")

    def test_class_body_import_does_not_leak_into_method_calls(self):
        source = (
            "class Handler:\n"
            "    from class_mod import run\n"
            "\n"
            "    def handle(self, value):\n"
            "        run(value)\n"
        )

        graph = PythonGraphParser().parse(
            Path("pkg/handler.py"), source, source_revision="src-1", snapshot_revision="snap-1"
        )

        imports = [
            edge for edge in graph.edges
            if edge.edge_type == "imports" and edge.target_key == "module:class_mod"
        ]
        calls = [edge for edge in graph.edges if edge.edge_type == "calls"]
        self.assertEqual(len(imports), 1)
        self.assertEqual(imports[0].source_key, "class:pkg.handler.Handler")
        self.assertEqual(calls, [])

    def test_method_does_not_resolve_bare_call_to_class_definition(self):
        source = (
            "class Handler:\n"
            "    def helper(self, value):\n"
            "        return value\n"
            "\n"
            "    def handle(self, value):\n"
            "        helper(value)\n"
        )

        graph = PythonGraphParser().parse(
            Path("pkg/handler.py"), source, source_revision="src-1", snapshot_revision="snap-1"
        )

        calls = {(edge.source_key, edge.target_key) for edge in graph.edges if edge.edge_type == "calls"}
        self.assertNotIn(
            ("function:pkg.handler.Handler.handle", "function:pkg.handler.Handler.helper"), calls
        )

    def test_lambda_body_call_is_not_attributed_to_enclosing_function(self):
        source = (
            "def helper(value):\n"
            "    return value\n"
            "\n"
            "def run(value):\n"
            "    callback = lambda: helper(value)\n"
            "    return callback()\n"
        )

        graph = PythonGraphParser().parse(
            Path("pkg/service.py"), source, source_revision="src-1", snapshot_revision="snap-1"
        )

        calls = {(edge.source_key, edge.target_key) for edge in graph.edges if edge.edge_type == "calls"}
        self.assertNotIn(
            ("function:pkg.service.run", "function:pkg.service.helper"), calls
        )

    def test_does_not_claim_dynamic_dispatch_as_static_call(self):
        source = "def run(callback):\n    callback()\n"

        graph = PythonGraphParser().parse(
            Path("service.py"), source, source_revision="src-1", snapshot_revision="snap-1"
        )

        self.assertEqual([edge for edge in graph.edges if edge.edge_type == "calls"], [])


if __name__ == "__main__":
    unittest.main()
