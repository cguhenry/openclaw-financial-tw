#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="$ROOT/.venv/bin/python"
ANNOUNCEMENT_LIMIT="${TW_MORNING_ANNOUNCEMENT_LIMIT:-8}"
TIMEOUT_SECONDS="${TW_MORNING_TIMEOUT_SECONDS:-180}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "missing python runtime: $PYTHON_BIN" >&2
  exit 1
fi

cd "$ROOT"
exec timeout "${TIMEOUT_SECONDS}s" "$PYTHON_BIN" "$ROOT/scripts/tw_morning_briefing.py" \
  --announcement-limit "$ANNOUNCEMENT_LIMIT" \
  --deliver-from-env \
  --send
