import json
import sys

from code_context.tools.mcp_tools import run


PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class StdioDispatcher:
    """Line-oriented JSON-RPC dispatcher for the local command service."""

    _MCP_PROTOCOL_VERSION = "2025-03-26"
    _MCP_TOOLS = {
        "init": "Initialize the local code context database.",
        "migrate": "Apply database migrations.",
        "doctor": "Check service readiness and tool permissions.",
        "health": "Return service health information.",
        "bootstrap": "Build and publish a code graph snapshot.",
        "search": "Search published technical code nodes.",
        "expand": "Expand graph relations and reconstruct paths.",
        "sync": "Update a graph from a baseline snapshot.",
        "evaluate": "Evaluate technical query results against a golden set.",
        "knowledge-generate": "Generate a versioned knowledge artifact.",
        "knowledge-push": "Push a knowledge artifact to a configured target.",
        "confirm": "Confirm or reject a business mapping with evidence and CAS.",
    }

    _METHODS = {
        "initialize": {"protocolVersion", "capabilities", "clientInfo"},
        "tools/list": {"cursor"},
        "tools/call": {"name", "arguments"},
        "confirm": {"mapping_id", "expected_version", "decision", "evidence_refs", "reason", "review_mode", "updated_by", "database"},
        "search": {"query", "limit", "database"},
        "expand": {
            "node_ids", "depth", "node_budget", "edge_budget", "direction",
            "edge_types", "node_scope", "database",
        },
        "health": {"database"},
        "doctor": {"database"},
        "init": {"database", "manifest"},
        "migrate": {"database"},
        "bootstrap": {
            "database", "manifest", "source_root", "scope", "exclude",
            "expected_parent",
        },
    }

    def __init__(self, runner=None, default_database=".code-context/context.db"):
        self.runner = runner or run
        self.default_database = default_database

    def serve(self, stdin=None, stdout=None, stderr=None):
        stdin = stdin or sys.stdin
        stdout = stdout or sys.stdout
        stderr = stderr or sys.stderr
        for line in stdin:
            if not line.strip():
                continue
            response = self._handle_line(line, stderr)
            if response is not None:
                stdout.write(json.dumps(response, ensure_ascii=False, sort_keys=True) + "\n")
                stdout.flush()

    def _handle_line(self, line, stderr):
        try:
            request = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            return self._error(None, PARSE_ERROR, "Parse error")
        if not isinstance(request, dict):
            return self._error(None, INVALID_REQUEST, "Invalid Request")
        request_id = request.get("id")
        if request.get("jsonrpc") != "2.0" or "id" not in request or not isinstance(request.get("method"), str):
            return self._error(request_id, INVALID_REQUEST, "Invalid Request")
        method = request["method"]
        if method not in self._METHODS:
            return self._error(request_id, METHOD_NOT_FOUND, "Method not found")
        params = request.get("params", {})
        if not isinstance(params, dict) or not set(params) <= self._METHODS[method]:
            return self._error(request_id, INVALID_PARAMS, "Invalid params")
        try:
            if method == "initialize":
                return self._success(request_id, {
                    "protocolVersion": self._MCP_PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "code-context", "version": "0.1.0"},
                })
            if method == "tools/list":
                return self._success(request_id, {
                    "tools": [self._tool_schema(name, description) for name, description in self._MCP_TOOLS.items()]
                })
            if method == "tools/call":
                return self._handle_tool_call(request_id, params)
            kwargs = dict(params)
            database_path = kwargs.pop("database", self.default_database)
            self._validate_params(method, kwargs)
            result = self.runner(method, database_path, **kwargs)
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except ValueError as error:
            return self._error(request_id, INVALID_PARAMS, str(error) or "Invalid params")
        except Exception as error:  # protocol must survive one bad request
            if stderr is not None:
                stderr.write(f"stdio request failed: {error}\n")
                stderr.flush()
            return self._error(request_id, INTERNAL_ERROR, "Internal error")

    @staticmethod
    def _validate_params(method, params):
        if method == "search":
            if not isinstance(params.get("query"), str) or not params["query"]:
                raise ValueError("query must be a non-empty string")
            if "limit" in params and (not isinstance(params["limit"], int) or params["limit"] < 1):
                raise ValueError("limit must be a positive integer")
        elif method == "expand":
            if not isinstance(params.get("node_ids"), list) or not all(isinstance(value, int) for value in params["node_ids"]):
                raise ValueError("node_ids must be a list of integers")
            for key in ("depth", "node_budget", "edge_budget"):
                if key in params and (not isinstance(params[key], int) or params[key] < 0):
                    raise ValueError(f"{key} must be a non-negative integer")
            if "direction" in params and params["direction"] not in {"out", "in", "both"}:
                raise ValueError("direction must be out, in, or both")
            if "edge_types" in params and (not isinstance(params["edge_types"], list) or not all(isinstance(value, str) for value in params["edge_types"])):
                raise ValueError("edge_types must be a list of strings")
            if "node_scope" in params and not isinstance(params["node_scope"], dict):
                raise ValueError("node_scope must be an object")
        elif method == "bootstrap":
            if not isinstance(params.get("source_root"), str) or not params["source_root"]:
                raise ValueError("source_root must be a non-empty string")

    def _handle_tool_call(self, request_id, params):
        name = params.get("name")
        if name not in self._MCP_TOOLS:
            return self._error(request_id, INVALID_PARAMS, "Unknown tool")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            return self._error(request_id, INVALID_PARAMS, "arguments must be an object")
        kwargs = dict(arguments)
        database_path = kwargs.pop("database", self.default_database)
        self._validate_params(name, kwargs)
        result = self.runner(name, database_path, **kwargs)
        return self._success(request_id, {
            "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, sort_keys=True)}],
            "isError": result.get("ok") is False if isinstance(result, dict) else False,
        })

    @staticmethod
    def _tool_schema(name, description):
        return {
            "name": name,
            "description": description,
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": True},
        }

    @staticmethod
    def _success(request_id, result):
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(request_id, code, message):
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
