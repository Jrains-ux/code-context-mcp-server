import tempfile
import unittest
from pathlib import Path

from code_context.bootstrap.first_build import BootstrapService
from code_context.storage.repository import SnapshotRepository
from code_context.storage.schema import Database


class BootstrapPhaseBTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.db = Database(self.root / "context.db")
        self.addCleanup(self.db.close)
        self.db.migrate()
        self.repository = SnapshotRepository(self.db.connection)
        self.service = BootstrapService(self.repository)

    def test_bootstrap_scans_mixed_languages_and_reports_coverage_and_parser_diagnostics(self):
        (self.source / "app.py").write_text("def run():\n    pass\n", encoding="utf-8")
        (self.source / "App.java").write_text("class App { void run() {} }", encoding="utf-8")
        (self.source / "main.go").write_text("package main\nfunc main() {}\n", encoding="utf-8")
        (self.source / "app.ts").write_text("export function start() {}\n", encoding="utf-8")
        (self.source / "README.md").write_text("docs", encoding="utf-8")

        result = self.service.build(self.source, "rev-mixed", "cfg", ["."])

        self.assertTrue(result["ok"])
        self.assertEqual(result["coverage"]["supported_files"], 4)
        self.assertEqual(result["coverage"]["unsupported_files"], 1)
        self.assertEqual(result["diagnostics"]["unsupported"], 1)
        manifest = self.db.connection.execute("SELECT parser_version FROM manifests").fetchone()
        self.assertIn("java-heuristic-1", manifest[0])

    def test_parse_failure_is_fail_closed_and_active_snapshot_is_unchanged(self):
        (self.source / "good.py").write_text("def old():\n    pass\n", encoding="utf-8")
        first = self.service.build(self.source, "rev-good", "cfg", ["."])
        active = self.repository.get_active_snapshot_id()
        self.assertTrue(first["ok"])
        (self.source / "broken.py").write_text("def broken(:\n", encoding="utf-8")

        result = self.service.build(self.source, "rev-broken", "cfg", ["."])

        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "PARSE_FAILED")
        self.assertEqual(self.repository.get_active_snapshot_id(), active)

    def test_unique_same_language_cross_file_call_is_bound_without_fabricating_ambiguous_target(self):
        (self.source / "helper.py").write_text("def helper():\n    pass\n", encoding="utf-8")
        (self.source / "caller.py").write_text("def caller():\n    helper()\n", encoding="utf-8")

        result = self.service.build(self.source, "rev-bind", "cfg", ["."])

        self.assertTrue(result["ok"])
        rows = self.db.connection.execute(
            "SELECT e.payload_json FROM edges e WHERE e.snapshot_id=? AND e.edge_type='calls'",
            (result["snapshot_id"],),
        ).fetchall()
        self.assertTrue(rows)
        self.assertTrue(any('"resolution": "static"' in row[0] for row in rows))


if __name__ == "__main__":
    unittest.main()
