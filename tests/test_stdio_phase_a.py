import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class StdioDispatcherTests(unittest.TestCase):
    def test_initialize_returns_mcp_protocol_and_capabilities(self):
        from code_context.tools.stdio import StdioDispatcher

        output = io.StringIO()
        request = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26", "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1"},
            },
        }
        StdioDispatcher().serve(io.StringIO(json.dumps(request) + "\n"), output)

        response = json.loads(output.getvalue())
        self.assertEqual(response["result"]["protocolVersion"], "2025-03-26")
        self.assertEqual(response["result"]["capabilities"]["tools"], {})
        self.assertEqual(response["result"]["serverInfo"]["name"], "code-context")

    def test_tools_list_returns_callable_tool_schemas(self):
        from code_context.tools.stdio import StdioDispatcher

        output = io.StringIO()
        request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        StdioDispatcher().serve(io.StringIO(json.dumps(request) + "\n"), output)

        response = json.loads(output.getvalue())
        tools = {tool["name"]: tool for tool in response["result"]["tools"]}
        for name in ("search", "expand", "bootstrap", "sync", "evaluate", "knowledge-generate", "knowledge-push"):
            self.assertIn(name, tools)
            self.assertEqual(tools[name]["inputSchema"]["type"], "object")

    def test_tools_call_dispatches_to_existing_runner(self):
        from code_context.tools.stdio import StdioDispatcher

        output = io.StringIO()
        request = {
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {
                "name": "search",
                "arguments": {"database": "test.db", "query": "Handler", "limit": 3},
            },
        }
        with patch("code_context.tools.stdio.run", return_value={"ok": True, "nodes": []}) as runner:
            StdioDispatcher().serve(io.StringIO(json.dumps(request) + "\n"), output)

        response = json.loads(output.getvalue())
        self.assertEqual(response["result"]["isError"], False)
        self.assertEqual(json.loads(response["result"]["content"][0]["text"]), {"ok": True, "nodes": []})
        runner.assert_called_once_with("search", "test.db", query="Handler", limit=3)

    def test_search_request_returns_correlated_result(self):
        from code_context.tools.stdio import StdioDispatcher

        calls = []

        def runner(command, database_path, **kwargs):
            calls.append((command, database_path, kwargs))
            return {"ok": True, "nodes": []}

        stdin = io.StringIO(json.dumps({
            "jsonrpc": "2.0", "id": 7, "method": "search",
            "params": {"database": "test.db", "query": "Handler", "limit": 3},
        }) + "\n")
        stdout = io.StringIO()
        StdioDispatcher(runner).serve(stdin, stdout)

        response = json.loads(stdout.getvalue())
        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["id"], 7)
        self.assertEqual(response["result"]["ok"], True)
        self.assertEqual(calls[0][0:2], ("search", "test.db"))
        self.assertEqual(calls[0][2], {"query": "Handler", "limit": 3})

    def test_expand透传_graph_filters(self):
        from code_context.tools.stdio import StdioDispatcher

        with patch("code_context.tools.stdio.run", return_value={"ok": True}) as runner:
            request = {
                "jsonrpc": "2.0", "id": "expand-1", "method": "expand",
                "params": {
                    "database": "test.db", "node_ids": [1], "depth": 2,
                    "node_budget": 5, "edge_budget": 6, "direction": "in",
                    "edge_types": ["calls"],
                    "node_scope": {"file_paths": ["src/a.py"]},
                },
            }
            StdioDispatcher().serve(
                io.StringIO(json.dumps(request) + "\n"), io.StringIO()
            )
            runner.assert_called_once_with(
                "expand", "test.db", node_ids=[1], depth=2, node_budget=5,
                edge_budget=6, direction="in", edge_types=["calls"],
                node_scope={"file_paths": ["src/a.py"]},
            )

    def test_invalid_unknown_and_parse_errors_do_not_stop_following_lines(self):
        from code_context.tools.stdio import StdioDispatcher

        output = io.StringIO()
        lines = [
            "not-json",
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "unknown", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "health", "params": {}}),
        ]
        with patch("code_context.tools.stdio.run", return_value={"ok": True}) as runner:
            StdioDispatcher().serve(io.StringIO("\n".join(lines) + "\n"), output)

        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(responses[0]["error"]["code"], -32700)
        self.assertEqual(responses[1]["error"]["code"], -32601)
        self.assertEqual(responses[2]["result"], {"ok": True})
        runner.assert_called_once_with("health", ".code-context/context.db")

    def test_invalid_params_returns_json_rpc_error(self):
        from code_context.tools.stdio import StdioDispatcher

        output = io.StringIO()
        request = {"jsonrpc": "2.0", "id": 4, "method": "expand", "params": {"node_ids": "bad"}}
        with patch("code_context.tools.stdio.run") as runner:
            StdioDispatcher().serve(io.StringIO(json.dumps(request) + "\n"), output)

        response = json.loads(output.getvalue())
        self.assertEqual(response["error"]["code"], -32602)
        runner.assert_not_called()


class StdioCliTests(unittest.TestCase):
    def test_stdio_cli_processes_multiple_requests(self):
        command = [sys.executable, "-m", "code_context.tools.mcp_tools", "stdio", "--database", ":memory:"]
        payload = "\n".join([
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "migrate", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "bad", "params": {}}),
        ]) + "\n"
        completed = subprocess.run(
            command, cwd=ROOT, input=payload, text=True, capture_output=True,
            env={"PYTHONPATH": str(ROOT / "src")}, check=False,
        )
        responses = [json.loads(line) for line in completed.stdout.splitlines()]
        self.assertEqual(len(responses), 2)
        self.assertEqual(responses[0]["id"], 1)
        self.assertEqual(responses[0]["result"]["status"], "migrated")
        self.assertEqual(responses[1]["error"]["code"], -32601)
        self.assertEqual(completed.stderr, "")

    def test_stdio_cli_uses_database_argument_as_default_request_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "requested.db"
            command = [
                sys.executable, "-m", "code_context.tools.mcp_tools", "stdio",
                "--database", str(database_path),
            ]
            payload = json.dumps({
                "jsonrpc": "2.0", "id": 3, "method": "migrate", "params": {},
            }) + "\n"
            completed = subprocess.run(
                command, cwd=ROOT, input=payload, text=True, capture_output=True,
                env={"PYTHONPATH": str(ROOT / "src")}, check=False,
            )

            responses = [json.loads(line) for line in completed.stdout.splitlines()]
            self.assertEqual(responses[0]["result"]["status"], "migrated")
            self.assertTrue(database_path.exists())
            self.assertEqual(completed.stderr, "")


if __name__ == "__main__":
    unittest.main()
