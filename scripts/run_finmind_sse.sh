#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

export MCP_TRANSPORT="${MCP_TRANSPORT:-sse}"
export MCP_HOST="${MCP_HOST:-127.0.0.1}"
export MCP_PORT="${MCP_PORT:-9123}"
export MCP_SSE_PATH="${MCP_SSE_PATH:-/sse}"
export MCP_MESSAGE_PATH="${MCP_MESSAGE_PATH:-/messages/}"
export MCP_STREAMABLE_HTTP_PATH="${MCP_STREAMABLE_HTTP_PATH:-/mcp}"

exec "$ROOT/.venv/bin/python" "$ROOT/mcp/finmind_server.py"
