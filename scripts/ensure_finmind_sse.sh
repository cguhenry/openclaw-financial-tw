#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME_DIR="$ROOT/run"
PID_FILE="$RUNTIME_DIR/finmind_sse.pid"
LOG_FILE="$RUNTIME_DIR/finmind_sse.log"
HOST="${MCP_HOST:-127.0.0.1}"
PORT="${MCP_PORT:-9123}"
SSE_PATH="${MCP_SSE_PATH:-/sse}"
SSE_URL="http://${HOST}:${PORT}${SSE_PATH}"

mkdir -p "$RUNTIME_DIR"

healthcheck() {
  FINMIND_MCP_SSE_URL="$SSE_URL" "$ROOT/.venv/bin/python" "$ROOT/scripts/verify_mcp_sse.py" >/dev/null 2>&1
}

if healthcheck; then
  echo "finmind-sse healthy: $SSE_URL"
  exit 0
fi

if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    sleep 1
  fi
  rm -f "$PID_FILE"
fi

nohup "$ROOT/scripts/run_finmind_sse.sh" >>"$LOG_FILE" 2>&1 &
pid=$!
echo "$pid" > "$PID_FILE"

for _ in 1 2 3 4 5; do
  if healthcheck; then
    echo "finmind-sse started: pid=$pid url=$SSE_URL"
    exit 0
  fi
  sleep 2
done

echo "finmind-sse failed to become healthy; see $LOG_FILE" >&2
exit 1
