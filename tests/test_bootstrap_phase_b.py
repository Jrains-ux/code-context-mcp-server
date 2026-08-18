import json
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
        self.assertEqual(result["coverage"]["languages"]["typescript"], 1)
        self.assertNotIn("javascript", result["coverage"]["languages"])
        self.assertTrue(any(item["code"] == "UNSUPPORTED_FILE_SUFFIX" for item in result["diagnostics"]["details"]))
        manifest = self.db.connection.execute("SELECT parser_version FROM manifests").fetchone()
        self.assertIn("java-heuristic-1", manifest[0])

    def test_bootstrap_counts_js_and_ts_by_artifact_language_and_parser_versions(self):
        (self.source / "app.js").write_text("export function start() {}\n", encoding="utf-8")
        (self.source / "app.ts").write_text("export function start() {}\n", encoding="utf-8")

        result = self.service.build(self.source, "rev-js-ts", "cfg", ["."])

        self.assertTrue(result["ok"])
        self.assertEqual(result["coverage"]["languages"], {"javascript": 1, "typescript": 1})
        self.assertEqual(result["coverage"]["parsers"], {"javascript-heuristic-1": 2})
        self.assertEqual(result["parser_versions"]["javascript"], "javascript-heuristic-1")
        self.assertEqual(result["parser_versions"]["typescript"], "javascript-heuristic-1")

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
        (self.source / "caller.py").write_text("from helper import helper\ndef caller():\n    helper()\n", encoding="utf-8")

        result = self.service.build(self.source, "rev-bind", "cfg", ["."])

        self.assertTrue(result["ok"])
        rows = self.db.connection.execute(
            "SELECT e.payload_json FROM edges e WHERE e.snapshot_id=? AND e.edge_type='calls'",
            (result["snapshot_id"],),
        ).fetchall()
        self.assertTrue(rows)
        self.assertTrue(any('"resolution": "static"' in row[0] for row in rows))

    def test_javascript_relative_import_binds_call_to_imported_function_artifact(self):
        (self.source / "helper.js").write_text("export function helper() {}\n", encoding="utf-8")
        (self.source / "caller.js").write_text(
            "import { helper } from './helper';\n"
            "export function caller() { helper(); }\n",
            encoding="utf-8",
        )

        result = self.service.build(self.source, "rev-js-import", "cfg", ["."])

        self.assertTrue(result["ok"])
        rows = self.db.connection.execute(
            "SELECT json_extract(e.payload_json, '$.source_key'), "
            "json_extract(e.payload_json, '$.target_key'), e.payload_json "
            "FROM edges e WHERE e.snapshot_id=? AND e.edge_type='calls'",
            (result["snapshot_id"],),
        ).fetchall()
        caller_calls = [row for row in rows if row[0] == "function:caller@caller.js.caller"]
        self.assertEqual(len(caller_calls), 1)
        self.assertEqual(caller_calls[0][1], "function:helper@helper.js.helper")
        self.assertIn('"resolution": "static"', caller_calls[0][2])
        self.assertIn('"bound": true', caller_calls[0][2])

    def test_typescript_relative_import_resolves_index_module(self):
        (self.source / "pkg").mkdir()
        (self.source / "pkg" / "index.ts").write_text("export function helper() {}\n", encoding="utf-8")
        (self.source / "caller.ts").write_text(
            "import { helper } from './pkg';\n"
            "export function caller() { helper(); }\n",
            encoding="utf-8",
        )

        result = self.service.build(self.source, "rev-ts-index", "cfg", ["."])

        self.assertTrue(result["ok"])
        row = self.db.connection.execute(
            "SELECT json_extract(payload_json, '$.target_key'), payload_json "
            "FROM edges WHERE snapshot_id=? AND edge_type='calls' "
            "AND json_extract(payload_json, '$.source_key')=?",
            (result["snapshot_id"], "function:caller@caller.ts.caller"),
        ).fetchone()
        self.assertEqual(row[0], "function:pkg.index@pkg/index.ts.helper")
        self.assertIn('"bound": true', row[1])

    def test_typescript_relative_import_ambiguity_stays_external(self):
        (self.source / "helper.ts").write_text("export function helper() {}\n", encoding="utf-8")
        (self.source / "helper.tsx").write_text("export function helper() {}\n", encoding="utf-8")
        (self.source / "caller.ts").write_text(
            "import { helper } from './helper';\n"
            "export function caller() { helper(); }\n",
            encoding="utf-8",
        )

        result = self.service.build(self.source, "rev-ts-ambiguous", "cfg", ["."])

        self.assertTrue(result["ok"])
        row = self.db.connection.execute(
            "SELECT json_extract(payload_json, '$.target_key'), payload_json "
            "FROM edges WHERE snapshot_id=? AND edge_type='calls' "
            "AND json_extract(payload_json, '$.source_key')=?",
            (result["snapshot_id"], "function:caller@caller.ts.caller"),
        ).fetchone()
        self.assertEqual(row[0], "external:helper")
        self.assertNotIn('"bound": true', row[1])

    def test_javascript_relative_import_without_matching_module_stays_external(self):
        (self.source / "caller.js").write_text(
            "import { helper } from './missing';\n"
            "export function caller() { helper(); }\n",
            encoding="utf-8",
        )

        result = self.service.build(self.source, "rev-js-missing", "cfg", ["."])

        self.assertTrue(result["ok"])
        row = self.db.connection.execute(
            "SELECT json_extract(payload_json, '$.target_key'), payload_json "
            "FROM edges WHERE snapshot_id=? AND edge_type='calls' "
            "AND json_extract(payload_json, '$.source_key')=?",
            (result["snapshot_id"], "function:caller@caller.js.caller"),
        ).fetchone()
        self.assertEqual(row[0], "external:helper")
        self.assertNotIn('"bound": true', row[1])

    def test_same_named_helpers_in_different_packages_require_import_context(self):
        for package in ("one", "two"):
            (self.source / package).mkdir()
            (self.source / package / "__init__.py").write_text("", encoding="utf-8")
            (self.source / package / "helper.py").write_text("def helper():\n    pass\n", encoding="utf-8")
        (self.source / "caller.py").write_text("def caller():\n    helper()\n", encoding="utf-8")
        (self.source / "imported.py").write_text("from one.helper import helper\ndef caller():\n    helper()\n", encoding="utf-8")

        result = self.service.build(self.source, "rev-packages", "cfg", ["."])

        self.assertTrue(result["ok"])
        rows = self.db.connection.execute(
            "SELECT json_extract(e.payload_json, '$.source_key'), json_extract(e.payload_json, '$.target_key'), e.payload_json FROM edges e WHERE e.snapshot_id=? AND e.edge_type='calls'",
            (result["snapshot_id"],),
        ).fetchall()
        unqualified = [row for row in rows if row[0] == "function:caller.caller"]
        qualified = [row for row in rows if row[0] == "function:imported.caller"]
        self.assertTrue(any(row[2].find('"resolution": "unresolved"') >= 0 for row in unqualified))
        self.assertTrue(any(row[1] == "function:one.helper.helper" and '"resolution": "static"' in row[2] for row in qualified))

    def test_bootstrap_returns_diagnostic_details_for_supported_parse_failure(self):
        (self.source / "broken.ts").write_text("function broken( {\n", encoding="utf-8")

        result = self.service.build(self.source, "rev-diagnostic", "cfg", ["."])

        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "PARSE_FAILED")
        self.assertTrue(result["diagnostics"])
        item = result["diagnostics"][0]
        self.assertEqual(set(item), {"code", "path", "message", "detail"})
        self.assertEqual(item["path"], "broken.ts")

    def test_python_external_calls_stay_in_their_lexical_function_scope(self):
        (self.source / "scope.py").write_text(
            "def outer():\n"
            "    outer_call()\n"
            "    def inner():\n"
            "        inner_call()\n"
            "    return inner\n",
            encoding="utf-8",
        )

        result = self.service.build(self.source, "rev-scope", "cfg", ["."])

        self.assertTrue(result["ok"])
        rows = self.db.connection.execute(
            "SELECT json_extract(payload_json, '$.source_key'), payload_json FROM edges WHERE snapshot_id=? AND edge_type='calls'",
            (result["snapshot_id"],),
        ).fetchall()
        by_source = {}
        for source_key, payload in rows:
            by_source.setdefault(source_key, set()).add(json.loads(payload)["symbol"])
        self.assertEqual(by_source["function:scope.outer"], {"outer_call"})
        self.assertEqual(by_source["function:scope.outer.inner"], {"inner_call"})


if __name__ == "__main__":
    unittest.main()
