import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from code_context.bootstrap.first_build import BootstrapService
from code_context.bootstrap.staging import SnapshotPublisher
from code_context.graph.parser import PythonGraphParser
from code_context.storage.repository import SnapshotRepository
from code_context.storage.schema import Database
from code_context.validators.schema_validator import ValidationError


class GraphPersistencePhaseATest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "context.db")
        self.db.migrate()
        self.repository = SnapshotRepository(self.db.connection)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_bulk_graph_staging_persists_nodes_edges_evidence_and_fts_atomically(self):
        graph = PythonGraphParser().parse(
            Path("pkg/service.py"),
            "import pkg.helpers\n\ndef run(value):\n    return value\n",
            source_revision="src-1",
            snapshot_revision="snap-1",
            config_revision="cfg-1",
        )
        snapshot_id = self.repository.create_snapshot("src-1", "snap-1", "cfg-1", "staging")

        result = self.repository.persist_graph_artifacts(snapshot_id, graph)

        self.assertEqual(result["node_count"], 3)
        self.assertEqual(result["edge_count"], 2)
        self.assertEqual(self.db.connection.execute("SELECT count(*) FROM evidence").fetchone()[0], 5)
        self.assertEqual(self.db.connection.execute("SELECT count(*) FROM artifact_manifests").fetchone()[0], 3)
        self.assertEqual(self.db.connection.execute("SELECT count(*) FROM node_fts").fetchone()[0], 3)
        edges = self.db.connection.execute(
            "SELECT e.edge_type, n1.canonical_key, n2.canonical_key "
            "FROM edges e JOIN nodes n1 ON n1.node_id=e.from_node_id "
            "JOIN nodes n2 ON n2.node_id=e.to_node_id WHERE e.snapshot_id=?",
            (snapshot_id,),
        ).fetchall()
        self.assertIn(("imports", "module:pkg.service", "external:module:pkg.helpers"), [tuple(row) for row in edges])

    def test_staging_failure_rolls_back_graph_unit_and_does_not_change_active_snapshot(self):
        old_snapshot = self.repository.create_snapshot("old", "old-index", "cfg-1", "published")
        self.repository.set_active_snapshot(old_snapshot)
        graph = PythonGraphParser().parse(
            Path("pkg/service.py"),
            "def run():\n    return 1\n",
            source_revision="src-1",
            snapshot_revision="snap-1",
            config_revision="cfg-1",
        )
        snapshot_id = self.repository.create_snapshot("wrong", "snap-1", "cfg-1", "staging")
        with self.assertRaises(ValidationError) as error:
            self.repository.persist_graph_artifacts(snapshot_id, graph)
        self.assertEqual(error.exception.code, "REVISION_MISMATCH")
        self.assertEqual(self.repository.get_active_snapshot_id(), old_snapshot)
        self.assertEqual(self.db.connection.execute("SELECT count(*) FROM nodes WHERE snapshot_id=?", (snapshot_id,)).fetchone()[0], 0)

    def test_edge_revision_mismatch_rolls_back_the_entire_graph_unit(self):
        base_graph = PythonGraphParser().parse(
            Path("pkg/service.py"),
            "def helper():\n    return 1\n\ndef run():\n    helper()\n",
            source_revision="src-1",
            snapshot_revision="snap-1",
            config_revision="cfg-1",
        )
        mismatch_cases = (
            ("source", replace(base_graph.edges[1].evidence, source_revision="src-other")),
            ("index", replace(base_graph.edges[1].evidence, snapshot_revision="snap-other")),
            ("config", replace(base_graph.edges[1].evidence, config_revision="cfg-other")),
            ("empty-config", replace(base_graph.edges[1].evidence, config_revision="")),
        )

        for name, evidence in mismatch_cases:
            with self.subTest(name=name):
                snapshot_id = self.repository.create_snapshot("src-1", "snap-1", "cfg-1", "staging")
                graph = replace(base_graph, edges=(replace(base_graph.edges[0], evidence=evidence), base_graph.edges[1]))
                with self.assertRaises(ValidationError) as error:
                    self.repository.persist_graph_artifacts(snapshot_id, graph)
                self.assertEqual(error.exception.code, "REVISION_MISMATCH")
                for table in ("nodes", "edges", "evidence", "artifact_manifests"):
                    self.assertEqual(
                        self.db.connection.execute(
                            f"SELECT count(*) FROM {table} WHERE snapshot_id=?" if table != "evidence" else "SELECT count(*) FROM evidence",
                            (snapshot_id,) if table != "evidence" else (),
                        ).fetchone()[0],
                        0,
                    )
                self.assertEqual(
                    self.db.connection.execute("SELECT count(*) FROM node_fts WHERE snapshot_id=?", (str(snapshot_id),)).fetchone()[0],
                    0,
                )

    def test_publisher_validates_edges_and_parent_mismatch_keeps_active_snapshot(self):
        old_snapshot = self.repository.create_snapshot("old", "old-index", "cfg-1", "published")
        self.repository.set_active_snapshot(old_snapshot)
        snapshot_id = self.repository.create_snapshot("src-1", "snap-1", "cfg-1", "staging")
        self.repository.add_node(snapshot_id, "Behavior", "function", "src-1", "snap-1", "cfg-1", {"canonical_key": "function:run", "name": "run"})
        with self.assertRaises(ValidationError):
            SnapshotPublisher(self.repository).publish(snapshot_id, expected_parent=999)
        self.assertEqual(self.repository.get_active_snapshot_id(), old_snapshot)
        self.assertEqual(self.repository.get_snapshot(snapshot_id)["status"], "staging")

    def test_expected_parent_publish_is_compare_and_swap(self):
        old_snapshot = self.repository.create_snapshot("old", "old-index", "cfg-1", "published")
        self.repository.set_active_snapshot(old_snapshot)
        first_snapshot = self.repository.create_snapshot("src-1", "idx-1", "cfg-1", "staging")
        second_snapshot = self.repository.create_snapshot("src-2", "idx-2", "cfg-1", "staging")
        for snapshot_id, revision in ((first_snapshot, "src-1"), (second_snapshot, "src-2")):
            node_id = self.repository.add_node(
                snapshot_id,
                "Graph",
                "function",
                revision,
                f"idx-{revision[-1]}",
                "cfg-1",
                {"canonical_key": f"function:{revision}", "name": revision},
            )
            self.db.connection.execute(
                "UPDATE nodes SET canonical_key=? WHERE node_id=?",
                (f"function:{revision}", node_id),
            )
        self.db.connection.commit()

        class StaleParentRepository(SnapshotRepository):
            def get_active_snapshot_id(self):
                return old_snapshot

        first_publisher = SnapshotPublisher(StaleParentRepository(self.db.connection))
        second_publisher = SnapshotPublisher(StaleParentRepository(self.db.connection))

        first_publisher.publish(first_snapshot, expected_parent=old_snapshot)
        with self.assertRaises(ValidationError) as error:
            second_publisher.publish(second_snapshot, expected_parent=old_snapshot)

        self.assertEqual(error.exception.code, "PUBLISH_PARENT_MISMATCH")
        self.assertEqual(self.repository.get_active_snapshot_id(), first_snapshot)
        self.assertEqual(self.repository.get_snapshot(first_snapshot)["status"], "published")
        self.assertEqual(self.repository.get_snapshot(second_snapshot)["status"], "staging")

    def test_bootstrap_indexes_qualified_name_for_fts_search(self):
        source_root = Path(self.tmp.name) / "source"
        source_root.mkdir()
        (source_root / "service.py").write_text(
            "def run(value):\n    return value\n",
            encoding="utf-8",
        )

        result = BootstrapService(self.repository).build(
            source_root, "src-qualified", "cfg-1", scope=(".",), expected_parent=None
        )
        self.assertTrue(result["ok"])

        from code_context.query import TechnicalQueryService

        search = TechnicalQueryService(self.db.connection).search('"service.run"', limit=10)

        self.assertTrue(any(node["canonical_key"] == "function:service.run" for node in search["nodes"]))

    def test_bootstrap_parse_failure_keeps_active_snapshot_unchanged(self):
        old_snapshot = self.repository.create_snapshot("old", "old-index", "cfg-1", "published")
        self.repository.set_active_snapshot(old_snapshot)
        source_root = Path(self.tmp.name) / "source"
        source_root.mkdir()
        (source_root / "broken.py").write_text("def broken(:\n    pass\n", encoding="utf-8")

        result = BootstrapService(self.repository).build(
            source_root, "src-1", "cfg-1", scope=(".",), expected_parent=old_snapshot
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "PARSE_FAILED")
        self.assertEqual(self.repository.get_active_snapshot_id(), old_snapshot)

    def test_bootstrap_publishes_graph_edges_and_index(self):
        source_root = Path(self.tmp.name) / "source"
        source_root.mkdir()
        (source_root / "service.py").write_text(
            "from helpers import normalize\n\ndef run(value):\n    normalize(value)\n",
            encoding="utf-8",
        )
        result = BootstrapService(self.repository).build(
            source_root, "src-1", "cfg-1", scope=(".",), expected_parent=None
        )
        self.assertTrue(result["ok"])
        self.assertGreater(result["edge_count"], 0)
        self.assertEqual(self.db.connection.execute("SELECT count(*) FROM node_fts WHERE snapshot_id=?", (str(result["snapshot_id"]),)).fetchone()[0], result["node_count"])


if __name__ == "__main__":
    unittest.main()
