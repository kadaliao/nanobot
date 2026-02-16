#!/usr/bin/env bash
set -euo pipefail

cd /app

if ! command -v watchmedo >/dev/null 2>&1; then
  echo "[dev] Installing watchdog..."
  uv pip install --system --no-cache watchdog
fi

echo "[dev] Installing nanobot in editable mode..."
uv pip install --system --no-cache -e /app

PORT="${NANOBOT_PORT:-18790}"
echo "[dev] Auto-reload enabled. Watching /app/nanobot for *.py changes (port ${PORT})."

exec watchmedo auto-restart \
  --directory=/app/nanobot \
  --pattern="*.py" \
  --recursive \
  -- nanobot gateway --verbose --port "${PORT}"
