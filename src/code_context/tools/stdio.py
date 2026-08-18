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

    _METHODS = {
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

    @staticmethod
    def _error(request_id, code, message):
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
