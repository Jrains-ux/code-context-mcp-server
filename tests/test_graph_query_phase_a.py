import tempfile
import unittest
from pathlib import Path

from code_context.bootstrap.staging import SnapshotPublisher
from code_context.query import TechnicalQueryService
from code_context.storage.repository import SnapshotRepository
from code_context.storage.schema import Database
from code_context.validators.schema_validator import ValidationError


class GraphQueryPhaseATest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "context.db")
        self.db.migrate()
        self.repository = SnapshotRepository(self.db.connection)
        self.snapshot_id = self.repository.create_snapshot("src-1", "idx-1", "cfg-1", "staging")
        self.nodes = {}
        for name, file_path in (("root", "pkg/root.py"), ("middle", "pkg/middle.py"), ("leaf", "pkg/leaf.py"), ("other", "other.py")):
            self.nodes[name] = self.repository.add_node(
                self.snapshot_id,
                "Graph",
                "function",
                "src-1",
                "idx-1",
                "cfg-1",
                {"canonical_key": f"function:{name}", "name": name, "file_path": file_path},
            )
            self.db.connection.execute(
                "UPDATE nodes SET canonical_key=? WHERE node_id=?",
                (f"function:{name}", self.nodes[name]),
            )
        self.db.connection.commit()
        self.repository.add_edge(self.snapshot_id, self.nodes["root"], self.nodes["middle"], "calls", "src-1", "idx-1", "cfg-1", {})
        self.repository.add_edge(self.snapshot_id, self.nodes["middle"], self.nodes["leaf"], "contains", "src-1", "idx-1", "cfg-1", {})
        self.repository.add_edge(self.snapshot_id, self.nodes["root"], self.nodes["other"], "imports", "src-1", "idx-1", "cfg-1", {})
        SnapshotPublisher(self.repository).publish(self.snapshot_id)
        self.other_snapshot = self.repository.create_snapshot("src-2", "idx-2", "cfg-1", "published")
        foreign_id = self.repository.add_node(self.other_snapshot, "Graph", "function", "src-2", "idx-2", "cfg-1", {"canonical_key": "function:foreign", "name": "foreign", "file_path": "foreign.py"})
        self.db.connection.execute("UPDATE nodes SET canonical_key=? WHERE node_id=?", ("function:foreign", foreign_id))
        self.db.connection.commit()
        self.service = TechnicalQueryService(self.db.connection)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_expand_reconstructs_ordered_paths_and_filters_edge_types(self):
        result = self.service.expand(
            [self.nodes["root"]], depth=2, node_budget=4, edge_budget=4,
            direction="out", edge_types=("calls",),
        )

        self.assertTrue(result["ok"])
        self.assertEqual([edge["edge_type"] for edge in result["edges"]], ["calls"])
        self.assertEqual(result["paths"], [[self.nodes["root"], self.nodes["middle"]]])
        self.assertEqual(result["snapshot_ref"]["index_revision"], "idx-1")
        self.assertFalse(result["truncated"])

    def test_expand_supports_in_and_both_directions(self):
        incoming = self.service.expand([self.nodes["leaf"]], depth=2, node_budget=4, edge_budget=4, direction="in")
        self.assertEqual(incoming["paths"], [[self.nodes["leaf"], self.nodes["middle"]], [self.nodes["leaf"], self.nodes["middle"], self.nodes["root"]]])

        both = self.service.expand([self.nodes["middle"]], depth=1, node_budget=4, edge_budget=4, direction="both")
        self.assertEqual(both["paths"], [[self.nodes["middle"], self.nodes["root"]], [self.nodes["middle"], self.nodes["leaf"]]])

    def test_expand_applies_node_scope_by_canonical_key_and_file_path(self):
        result = self.service.expand(
            [self.nodes["root"]], depth=2, node_budget=4, edge_budget=4,
            node_scope={"canonical_keys": ["function:middle"], "file_paths": ["pkg/middle.py"]},
        )
        self.assertEqual(result["paths"], [[self.nodes["root"], self.nodes["middle"]]])
        self.assertEqual({edge["to_node_id"] for edge in result["edges"]}, {self.nodes["middle"]})

    def test_expand_returns_in_budget_results_and_truncated_when_budget_is_exceeded(self):
        result = self.service.expand([self.nodes["root"]], depth=2, node_budget=2, edge_budget=10)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["coverage"], {"nodes": 2, "edges": 1})
        self.assertEqual(result["paths"], [[self.nodes["root"], self.nodes["middle"]]])

        edge_limited = self.service.expand([self.nodes["root"]], depth=1, node_budget=4, edge_budget=1)
        self.assertTrue(edge_limited["truncated"])
        self.assertEqual(len(edge_limited["edges"]), 1)

    def test_expand_uses_only_active_published_snapshot_and_rejects_invalid_direction(self):
        result = self.service.expand([self.nodes["root"]], depth=1, node_budget=4, edge_budget=4)
        self.assertTrue(all(edge["snapshot_id"] == self.snapshot_id for edge in result["edges"]))
        self.assertNotIn(self.other_snapshot, {edge["snapshot_id"] for edge in result["edges"]})

        with self.assertRaises(ValidationError) as error:
            self.service.expand([self.nodes["root"]], depth=1, node_budget=4, edge_budget=4, direction="sideways")
        self.assertEqual(error.exception.code, "INVALID_DIRECTION")


if __name__ == "__main__":
    unittest.main()
