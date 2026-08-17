import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from code_context.bootstrap.staging import SnapshotPublisher
from code_context.policies.permission import PermissionMatrix
from code_context.storage.repository import SnapshotRepository
from code_context.storage.schema import Database
from code_context.tools.registry import ToolRegistry
from code_context.tools.mcp_tools import main, run
from code_context.validators.schema_validator import ValidationError


class FoundationTest(unittest.TestCase):
    def test_migrate_creates_core_tables(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)

        with self.subTest("database"):
            db = Database(Path(tmp.name) / "context.db")
            self.addCleanup(db.close)
            db.migrate()
            tables = {
                row[0]
                for row in db.connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            self.assertTrue({"manifests", "snapshots", "nodes", "edges", "evidence"} <= tables)

    def test_versioned_node_round_trip(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with self.subTest("database"):
            db = Database(Path(tmp.name) / "context.db")
            self.addCleanup(db.close)
            db.migrate()
            repo = SnapshotRepository(db.connection)
            snapshot_id = repo.create_snapshot("src-1", "idx-1", "cfg-1", "staging")
            node_id = repo.add_node(snapshot_id, "Behavior", "Thing", "src-1", "idx-1", "cfg-1", {"name": "run"})
            node = repo.get_node(node_id)
            self.assertEqual(node["payload"]["name"], "run")
            self.assertEqual(node["source_revision"], "src-1")

    def test_manifest_edge_and_mapping_round_trip(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Database(Path(tmp.name) / "context.db")
        self.addCleanup(db.close)
        db.migrate()
        repo = SnapshotRepository(db.connection)
        manifest_id = repo.add_manifest("repo", "src-1", {"include": ["src"]}, {"exclude": []}, "parser-1", "cfg-1")
        snapshot_id = repo.create_snapshot("src-1", "idx-1", "cfg-1", "staging")
        left_id = repo.add_node(snapshot_id, "Behavior", "Thing", "src-1", "idx-1", "cfg-1", {"name": "left"})
        right_id = repo.add_node(snapshot_id, "Behavior", "Thing", "src-1", "idx-1", "cfg-1", {"name": "right"})
        edge_id = repo.add_edge(snapshot_id, left_id, right_id, "calls", "src-1", "idx-1", "cfg-1", {})
        mapping_id = repo.add_mapping("orders.refund", snapshot_id, "candidate", None)
        self.assertTrue(manifest_id)
        self.assertTrue(edge_id)
        self.assertEqual(repo.get_mapping(mapping_id)["biz_id"], "orders.refund")

    def test_stale_mapping_accepts_replacement_evidence(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Database(Path(tmp.name) / "context.db")
        self.addCleanup(db.close)
        db.migrate()
        repo = SnapshotRepository(db.connection)
        snapshot_id = repo.create_snapshot("src-1", "idx-1", "cfg-1", "staging")
        mapping_id = repo.add_mapping("orders.refund", snapshot_id, "stale", None)
        evidence_id = repo.add_evidence("src-2", "idx-2", "cfg-1", "a.py", 3, 4, "hash-2")
        repo.replace_mapping_evidence(mapping_id, evidence_id)
        self.assertEqual(repo.get_mapping(mapping_id)["replacement_evidence_id"], evidence_id)

    def test_publish_rejects_mixed_revisions_and_preserves_active_snapshot(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with self.subTest("database"):
            db = Database(Path(tmp.name) / "context.db")
            self.addCleanup(db.close)
            db.migrate()
            repo = SnapshotRepository(db.connection)
            publisher = SnapshotPublisher(repo)
            old_id = repo.create_snapshot("src-old", "idx-old", "cfg-1", "published")
            repo.set_active_snapshot(old_id)
            staging_id = repo.create_snapshot("src-new", "idx-new", "cfg-1", "staging")
            repo.add_node(staging_id, "Behavior", "Thing", "src-other", "idx-new", "cfg-1", {})
            with self.assertRaises(ValidationError) as error:
                publisher.publish(staging_id)
            self.assertEqual(error.exception.code, "REVISION_MISMATCH")
            self.assertEqual(repo.get_active_snapshot_id(), old_id)

    def test_evidence_is_immutable(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with self.subTest("database"):
            db = Database(Path(tmp.name) / "context.db")
            self.addCleanup(db.close)
            db.migrate()
            repo = SnapshotRepository(db.connection)
            evidence_id = repo.add_evidence("src-1", "idx-1", "cfg-1", "a.py", 1, 2, "hash-1")
            with self.assertRaises(sqlite3.IntegrityError):
                repo.update_evidence(evidence_id, "hash-2")

    def test_permission_matrix_filters_tools(self):
        matrix = PermissionMatrix()
        self.assertIn("lexical_search", matrix.allowed("Query"))
        self.assertNotIn("publish", matrix.allowed("Query"))

    def test_registry_reports_missing_required_tool(self):
        registry = ToolRegistry()
        result = registry.diagnose("Query", registry.matrix.allowed("Query"))
        self.assertTrue(result["ok"])
        result = registry.diagnose("Query", set())
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "TOOL_CONTRACT_MISSING")

    def test_init_creates_database_and_registry(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        database_path = Path(tmp.name) / "context.db"
        result = run("init", database_path)
        self.assertTrue(result["ok"])
        doctor = run("doctor", database_path)
        self.assertEqual(doctor["status"], "not_ready")
        self.assertEqual(doctor["code"], "SERVICE_NOT_READY")

    def test_init_persists_default_local_manifest(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        result = run("init", Path(tmp.name) / "context.db")
        self.assertIn("manifest", result)
        self.assertEqual(result["manifest"]["project"], "local")
        self.assertEqual(result["manifest"]["source_revision"], "unversioned")

    def test_health_fails_closed_before_a_snapshot_is_published(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        database_path = Path(tmp.name) / "context.db"
        run("init", database_path)
        result = run("health", database_path)
        self.assertEqual(result["code"], "SERVICE_NOT_READY")

    def test_health_is_ready_after_initialized_fixture_is_published(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        database_path = Path(tmp.name) / "context.db"
        run("init", database_path)
        db = Database(database_path)
        self.addCleanup(db.close)
        repository = SnapshotRepository(db.connection)
        snapshot_id = repository.create_snapshot("src-1", "idx-1", "cfg-1", "staging")
        repository.add_node(snapshot_id, "Behavior", "fixture", "src-1", "idx-1", "cfg-1", {})
        SnapshotPublisher(repository).publish(snapshot_id)
        result = run("health", database_path)
        self.assertTrue(result["ok"])
        self.assertTrue(result["runtime_ready"])
        self.assertEqual(repository.get_active_snapshot_id(), snapshot_id)

    def test_cli_init_accepts_explicit_manifest_values(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        database_path = Path(tmp.name) / "context.db"
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "code_context.tools",
                "init",
                "--database",
                str(database_path),
                "--project",
                "demo",
                "--workspace",
                "C:/workspace/demo",
                "--source-revision",
                "abc123",
                "--config-version",
                "2",
            ],
            capture_output=True,
            text=True,
            env=environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["manifest"]["project"], "demo")

    def test_cli_init_rejects_blank_project_manifest_value(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        database_path = Path(tmp.name) / "context.db"
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "code_context.tools",
                "init",
                "--database",
                str(database_path),
                "--project",
                "",
            ],
            capture_output=True,
            text=True,
            env=environment,
        )
        self.assertEqual(result.returncode, 1)

    def test_doctor_reports_missing_registry_contract(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        database_path = Path(tmp.name) / "context.db"
        run("init", database_path)
        db = Database(database_path)
        self.addCleanup(db.close)
        db.connection.execute("DELETE FROM tool_registry")
        db.connection.commit()
        result = run("doctor", database_path)
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "TOOL_PERMISSION_MISMATCH")

    def test_cli_main_returns_success_for_init(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        exit_code = main(["init", "--database", str(Path(tmp.name) / "context.db")])
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
