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
from code_context.business import BusinessMiningService, BusinessRouter
from code_context.consumer import DistributionService
from code_context.consumer import EvaluationService
from code_context.consumer import KnowledgeService
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

    def test_cli_bootstrap_builds_and_publishes_scoped_python_fixture(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        source_root = root / "source"
        package = source_root / "pkg"
        package.mkdir(parents=True)
        (package / "sample.py").write_text(
            "class Handler:\n    def run(self):\n        return 'ok'\n",
            encoding="utf-8",
        )
        run("init", root / "context.db")
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "code_context.tools",
                "bootstrap",
                "--database",
                str(root / "context.db"),
                "--source-root",
                str(source_root),
                "--source-revision",
                "rev-1",
                "--scope",
                "pkg",
            ],
            capture_output=True,
            text=True,
            env=environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "published")
        self.assertGreater(payload["node_count"], 0)

    def test_bootstrap_rejects_missing_source_revision(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        run("init", root / "context.db")
        result = run(
            "bootstrap",
            root / "context.db",
            manifest={"source_revision": "", "config_version": "1"},
            source_root=root,
            scope=["."],
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "SOURCE_REVISION_REQUIRED")

    def test_bootstrap_retains_staging_snapshot_when_coverage_is_empty(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "source").mkdir()
        run("init", root / "context.db")
        result = run(
            "bootstrap",
            root / "context.db",
            manifest={"source_revision": "rev-empty", "config_version": "1"},
            source_root=root / "source",
            scope=["missing"],
        )
        self.assertEqual(result["code"], "COVERAGE_GATE_FAILED")
        db = Database(root / "context.db")
        self.addCleanup(db.close)
        snapshot = db.connection.execute(
            "SELECT status FROM snapshots WHERE snapshot_id=?", (result["snapshot_id"],)
        ).fetchone()
        self.assertEqual(snapshot[0], "staging")
        self.assertIsNone(SnapshotRepository(db.connection).get_active_snapshot_id())

    def test_bootstrap_rejects_parent_mismatch_and_preserves_active_snapshot(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        source = root / "source"
        source.mkdir()
        (source / "sample.py").write_text("def run():\n    return 1\n", encoding="utf-8")
        database_path = root / "context.db"
        run("init", database_path)
        db = Database(database_path)
        self.addCleanup(db.close)
        repository = SnapshotRepository(db.connection)
        active_id = repository.create_snapshot("old", "old-index", "1", "published")
        repository.set_active_snapshot(active_id)
        result = run(
            "bootstrap",
            database_path,
            manifest={"source_revision": "rev-next", "config_version": "1"},
            source_root=source,
            scope=["."],
            expected_parent=None,
        )
        self.assertEqual(result["code"], "PUBLISH_PARENT_MISMATCH")
        self.assertEqual(repository.get_active_snapshot_id(), active_id)

    def test_bootstrap_reports_duplicate_canonical_artifacts(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        source = root / "source"
        source.mkdir()
        (source / "duplicate.py").write_text(
            "def run():\n    return 1\n\ndef run():\n    return 2\n",
            encoding="utf-8",
        )
        database_path = root / "context.db"
        run("init", database_path)
        result = run(
            "bootstrap",
            database_path,
            manifest={"source_revision": "rev-duplicate", "config_version": "1"},
            source_root=source,
            scope=["."],
        )
        self.assertEqual(result["code"], "ARTIFACT_CONFLICT")
        db = Database(database_path)
        self.addCleanup(db.close)
        report = db.connection.execute(
            "SELECT code FROM conflict_reports WHERE snapshot_id=?", (result["snapshot_id"],)
        ).fetchone()
        self.assertEqual(report[0], "ARTIFACT_CONFLICT")

    def test_cli_search_returns_published_technical_node(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        source = root / "source"
        source.mkdir()
        (source / "sample.py").write_text("def lookup_order():\n    return 1\n", encoding="utf-8")
        database_path = root / "context.db"
        run("init", database_path)
        run("bootstrap", database_path, manifest={"source_revision": "query-1", "config_version": "1"}, source_root=source, scope=["."])
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
        result = subprocess.run(
            [sys.executable, "-m", "code_context.tools", "search", "--database", str(database_path), "--query", "lookup_order", "--limit", "5"],
            capture_output=True, text=True, env=environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["nodes"][0]["payload"]["name"], "lookup_order")

    def test_search_rejects_missing_published_snapshot(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        database_path = Path(tmp.name) / "context.db"
        run("init", database_path)
        result = run("search", database_path, query="anything", limit=1)
        self.assertEqual(result["code"], "SNAPSHOT_NOT_PUBLISHED")

    def test_business_router_requires_selection_and_confirm_uses_evidence_cas(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Database(Path(tmp.name) / "context.db")
        self.addCleanup(db.close)
        db.migrate()
        repository = SnapshotRepository(db.connection)
        snapshot_id = repository.create_snapshot("src", "idx", "1", "published")
        repository.set_active_snapshot(snapshot_id)
        router = BusinessRouter(db.connection)
        router.add_candidate("refund", "orders.refund", "normal", "normal refund", [1], snapshot_id)
        router.add_candidate("refund", "orders.refund", "fast", "fast refund", [2], snapshot_id)
        resolved = router.resolve("refund")
        self.assertEqual(resolved["status"], "needs_user_selection")
        self.assertEqual(router.select(resolved["route_token"], "fast")["node_scope"], [2])
        evidence_id = repository.add_evidence("src", "idx", "1", "a.py", 1, 1, "hash")
        mapping_id = repository.add_mapping("orders.refund", snapshot_id, "candidate", evidence_id)
        db.connection.execute("UPDATE mappings SET expected_version=1 WHERE mapping_id=?", (mapping_id,))
        db.connection.commit()
        self.assertEqual(router.confirm(mapping_id, 1, "confirmed", [evidence_id], "review")["status"], "confirmed")

    def test_business_mapping_preserves_anchor_evidence_and_review_metadata(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Database(Path(tmp.name) / "context.db")
        self.addCleanup(db.close)
        db.migrate()
        repository = SnapshotRepository(db.connection)
        snapshot_id = repository.create_snapshot("src", "idx", "1", "published")
        anchor_id = repository.add_business_node(
            snapshot_id, "requirement", "refund.request", {"title": "退款申请"}, "candidate"
        )
        first_evidence = repository.add_evidence("src", "idx", "1", "refund.py", 10, 12, "hash-1")
        second_evidence = repository.add_evidence("src", "idx", "1", "refund.py", 20, 24, "hash-2")

        mapping_id = repository.add_mapping(
            "orders.refund", snapshot_id, "candidate", first_evidence,
            requirement_id="REQ-1", anchor_node_ids=[anchor_id],
            evidence_refs=[first_evidence, second_evidence], review_required=True,
            review_mode="manual_review_required", risk_level="high",
            confidence=0.6, review_batch_id="batch-1", updated_by="miner",
        )

        mapping = repository.get_mapping(mapping_id)
        self.assertEqual(mapping["requirement_id"], "REQ-1")
        self.assertEqual(mapping["anchor_node_ids"], [anchor_id])
        self.assertEqual(mapping["evidence_refs"], [first_evidence, second_evidence])
        self.assertEqual(mapping["review_mode"], "manual_review_required")
        self.assertEqual(mapping["risk_level"], "high")
        self.assertEqual(mapping["confidence"], 0.6)
        self.assertEqual(repository.get_mapping_evidence(mapping_id), [first_evidence, second_evidence])

    def test_confirmation_audits_all_mapping_evidence_with_review_metadata(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Database(Path(tmp.name) / "context.db")
        self.addCleanup(db.close)
        db.migrate()
        repository = SnapshotRepository(db.connection)
        snapshot_id = repository.create_snapshot("src", "idx", "1", "published")
        repository.set_active_snapshot(snapshot_id)
        first_evidence = repository.add_evidence("src", "idx", "1", "refund.py", 10, 12, "hash-1")
        second_evidence = repository.add_evidence("src", "idx", "1", "refund.py", 20, 24, "hash-2")
        mapping_id = repository.add_mapping(
            "orders.refund", snapshot_id, "candidate", first_evidence,
            evidence_refs=[first_evidence, second_evidence], review_mode="manual_review_required",
        )
        db.connection.execute("UPDATE mappings SET expected_version=1 WHERE mapping_id=?", (mapping_id,))
        db.connection.commit()

        result = BusinessRouter(db.connection).confirm(
            mapping_id, 1, "confirmed", [first_evidence, second_evidence], "review",
            review_mode="manual_review_required", updated_by="reviewer",
        )

        self.assertEqual(result["status"], "confirmed")
        rows = db.connection.execute(
            "SELECT evidence_refs_json,review_mode,updated_by FROM confirmation_audit WHERE mapping_id=?",
            (mapping_id,),
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(json.loads(rows[0][0]), [first_evidence, second_evidence])
        self.assertEqual(rows[0][1:], ("manual_review_required", "reviewer"))

    def test_mining_initial_persists_candidate_mapping_and_route(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Database(Path(tmp.name) / "context.db")
        self.addCleanup(db.close)
        db.migrate()
        repository = SnapshotRepository(db.connection)
        snapshot_id = repository.create_snapshot("src", "idx", "1", "published")
        repository.set_active_snapshot(snapshot_id)
        evidence_id = repository.add_evidence("src", "idx", "1", "refund.py", 10, 12, "hash-1")

        result = BusinessMiningService(db.connection).mine("initial", snapshot_id, [{
            "biz_id": "orders.refund",
            "term": "退款",
            "context_id": "normal",
            "summary": "普通退款",
            "node_scope": {"canonical_keys": ["py:refund.request"]},
            "node_type": "requirement",
            "canonical_key": "requirement:orders.refund",
            "payload": {"title": "退款申请"},
            "evidence_refs": [evidence_id],
            "review_mode": "manual_review_required",
        }])

        self.assertEqual(result["mode"], "initial")
        self.assertEqual(result["candidate_count"], 1)
        resolved = BusinessRouter(db.connection).resolve("退款")
        self.assertEqual(resolved["status"], "selected")
        self.assertEqual(resolved["candidates"][0]["context_id"], "normal")
        mapping = db.connection.execute(
            "SELECT status,review_mode FROM mappings WHERE biz_id=?", ("orders.refund",)
        ).fetchone()
        self.assertEqual(tuple(mapping), ("candidate", "manual_review_required"))

    def test_cli_run_exposes_mining_and_business_context_tools(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        database_path = Path(tmp.name) / "context.db"
        db = Database(database_path)
        self.addCleanup(db.close)
        db.migrate()
        repository = SnapshotRepository(db.connection)
        snapshot_id = repository.create_snapshot("src", "idx", "1", "published")
        repository.set_active_snapshot(snapshot_id)
        evidence_id = repository.add_evidence("src", "idx", "1", "refund.py", 1, 1, "hash")

        mined = run("mine", database_path, mining_mode="initial", snapshot_id=snapshot_id, candidates=[{
            "biz_id": "orders.refund", "term": "退款", "context_id": "normal",
            "summary": "普通退款", "node_scope": {"canonical_keys": ["py:refund"]},
            "node_type": "requirement", "canonical_key": "requirement:refund",
            "payload": {"title": "退款"}, "evidence_refs": [evidence_id],
        }])
        resolved = run("resolve_business_context", database_path, query_text="退款")
        selected = run(
            "select_business_context", database_path,
            route_token=resolved["route_token"], context_id="normal",
        )

        self.assertEqual(mined["status"], "candidate")
        self.assertEqual(resolved["status"], "selected")
        self.assertEqual(selected["node_scope"], {"canonical_keys": ["py:refund"]})

    def test_sync_rejects_missing_baseline_snapshot(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        database_path = Path(tmp.name) / "context.db"
        run("init", database_path)
        result = run("sync", database_path)
        self.assertEqual(result["code"], "BASELINE_REF_NOT_FOUND")

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

    def test_evaluation_rejects_insufficient_samples_without_persisting_metrics(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Database(Path(tmp.name) / "context.db")
        self.addCleanup(db.close)
        db.migrate()
        repository = SnapshotRepository(db.connection)
        snapshot_id = repository.create_snapshot("src", "idx", "1", "staging")
        repository.add_node(snapshot_id, "Behavior", "fixture", "src", "idx", "1", {"name": "lookup_order"})
        SnapshotPublisher(repository).publish(snapshot_id)
        repository.rebuild_node_index(snapshot_id)
        with self.assertRaises(ValidationError) as error:
            EvaluationService(db.connection).evaluate(
                "dataset-1", "gold-1", [{"query": "lookup_order", "expected_node_ids": [1]}], minimum_samples=2,
            )
        self.assertEqual(error.exception.code, "EVALUATION_INSUFFICIENT")
        self.assertEqual(db.connection.execute("SELECT count(*) FROM evaluation_runs").fetchone()[0], 0)

    def test_evaluation_persists_version_bound_metrics_and_failure_cases(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Database(Path(tmp.name) / "context.db")
        self.addCleanup(db.close)
        db.migrate()
        repository = SnapshotRepository(db.connection)
        snapshot_id = repository.create_snapshot("src", "idx", "1", "staging")
        node_id = repository.add_node(snapshot_id, "Behavior", "fixture", "src", "idx", "1", {"name": "lookup_order"})
        SnapshotPublisher(repository).publish(snapshot_id)
        repository.rebuild_node_index(snapshot_id)
        result = EvaluationService(db.connection).evaluate(
            "dataset-1", "gold-1",
            [{"query": "lookup_order", "expected_node_ids": [node_id]}, {"query": "lookup_order", "expected_node_ids": [999]}],
            tool_versions={"search": "1"}, minimum_samples=2,
        )
        self.assertEqual(result["metrics"]["total"], 2)
        self.assertEqual(result["metrics"]["passed"], 1)
        row = db.connection.execute("SELECT source_revision, index_revision FROM evaluation_runs WHERE run_id=?", (result["run_id"],)).fetchone()
        self.assertEqual(tuple(row), ("src", "idx"))
        self.assertEqual(db.connection.execute("SELECT count(*) FROM failure_cases WHERE run_id=?", (result["run_id"],)).fetchone()[0], 1)

    def test_knowledge_generation_uses_published_snapshot_and_confirmed_mapping_only(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Database(Path(tmp.name) / "context.db")
        self.addCleanup(db.close)
        db.migrate()
        repository = SnapshotRepository(db.connection)
        snapshot_id = repository.create_snapshot("src", "idx", "1", "staging")
        evidence_id = repository.add_evidence("src", "idx", "1", "fixture.py", 1, 1, "evidence")
        repository.add_node(snapshot_id, "Behavior", "fixture", "src", "idx", "1", {"name": "lookup_order", "evidence_id": evidence_id})
        SnapshotPublisher(repository).publish(snapshot_id)
        candidate_mapping = repository.add_mapping("orders.refund", snapshot_id, "candidate", evidence_id)
        technical = KnowledgeService(db.connection).generate("technical", "all", "template-1", "generator-1")
        self.assertEqual(technical["snapshot_ref"]["index_revision"], "idx")
        manifest = db.connection.execute("SELECT content_hash, evidence_refs_json FROM document_manifests WHERE manifest_id=?", (technical["manifest_id"],)).fetchone()
        self.assertEqual(manifest[0], technical["content_hash"])
        self.assertIn(str(evidence_id), manifest[1])
        with self.assertRaises(ValidationError) as error:
            KnowledgeService(db.connection).generate("business", str(candidate_mapping), "template-1", "generator-1")
        self.assertEqual(error.exception.code, "CONFIRMED_MAPPING_REQUIRED")

    def test_distribution_is_idempotent_and_unsupported_target_is_retryable_without_graph_mutation(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Database(Path(tmp.name) / "context.db")
        self.addCleanup(db.close)
        db.migrate()
        repository = SnapshotRepository(db.connection)
        snapshot_id = repository.create_snapshot("src", "idx", "1", "staging")
        repository.add_node(snapshot_id, "Behavior", "fixture", "src", "idx", "1", {"name": "lookup_order"})
        SnapshotPublisher(repository).publish(snapshot_id)
        document = KnowledgeService(db.connection).generate("technical", "all", "template-1", "generator-1")
        counts_before = tuple(db.connection.execute("SELECT (SELECT count(*) FROM nodes), (SELECT count(*) FROM mappings), (SELECT count(*) FROM snapshots)").fetchone())
        distribution = DistributionService(db.connection)
        first = distribution.push(document["manifest_id"], "local", "push-1")
        repeated = distribution.push(document["manifest_id"], "local", "push-1")
        failed = distribution.push(document["manifest_id"], "feishu-wiki", "push-2")
        self.assertEqual(first, repeated)
        self.assertEqual(first["status"], "pushed")
        self.assertEqual(failed["code"], "DISTRIBUTION_TARGET_UNSUPPORTED")
        self.assertTrue(failed["retryable"])
        self.assertEqual(tuple(db.connection.execute("SELECT (SELECT count(*) FROM nodes), (SELECT count(*) FROM mappings), (SELECT count(*) FROM snapshots)").fetchone()), counts_before)

    def test_cli_run_exposes_evaluation_knowledge_and_controlled_push(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        database_path = Path(tmp.name) / "context.db"
        run("init", database_path)
        db = Database(database_path)
        self.addCleanup(db.close)
        repository = SnapshotRepository(db.connection)
        snapshot_id = repository.create_snapshot("src", "idx", "1", "staging")
        node_id = repository.add_node(snapshot_id, "Behavior", "fixture", "src", "idx", "1", {"name": "lookup_order"})
        SnapshotPublisher(repository).publish(snapshot_id)
        repository.rebuild_node_index(snapshot_id)
        evaluation = run("evaluate", database_path, dataset_id="dataset-1", golden_set_version="gold-1", samples=[{"query": "lookup_order", "expected_node_ids": [node_id]}], minimum_samples=1)
        document = run("knowledge-generate", database_path, document_kind="technical", document_scope="all", template_version="template-1", generator_version="generator-1")
        pushed = run("knowledge-push", database_path, manifest_id=document["manifest_id"], target="local", idempotency_key="push-1")
        self.assertTrue(evaluation["ok"])
        self.assertTrue(document["ok"])
        self.assertEqual(pushed["status"], "pushed")


if __name__ == "__main__":
    unittest.main()
