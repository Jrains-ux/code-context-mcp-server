## Purpose

通过 JSON-RPC 2.0 stdio 将本地代码图谱操作暴露给 MCP 兼容调用方，同时复用统一的命令和错误语义。

## ADDED Requirements

### Requirement: Stdio dispatches supported graph operations
The system SHALL accept line-delimited JSON-RPC 2.0 requests for supported graph operations and SHALL return one correlated JSON-RPC result or error response per request.

#### Scenario: Search request is dispatched
- **WHEN** a valid JSON-RPC search request arrives on standard input
- **THEN** the system invokes the graph search operation and writes a response with the same request id

### Requirement: Stdio rejects invalid requests safely
The system SHALL return a JSON-RPC error for malformed requests, unsupported methods, or invalid parameters and SHALL continue processing later input lines.

#### Scenario: Unsupported method arrives
- **WHEN** a request names an unsupported method
- **THEN** the system returns an error response without changing graph state
