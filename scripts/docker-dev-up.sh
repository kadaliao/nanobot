#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -n "${NANOBOT_CONFIG_DIR:-}" ]]; then
  cfg_dir="${NANOBOT_CONFIG_DIR}"
elif [[ -d "${HOME}/.nanobot" ]]; then
  cfg_dir="${HOME}/.nanobot"
else
  cfg_dir="${HOME}/.nanobot"
  mkdir -p "${cfg_dir}"
fi

export NANOBOT_CONFIG_DIR="${cfg_dir}"

echo "[dev] Reusing config dir: ${NANOBOT_CONFIG_DIR}"
exec docker compose -f "${PROJECT_ROOT}/docker-compose.dev.yml" up --build
