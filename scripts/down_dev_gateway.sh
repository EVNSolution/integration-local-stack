#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
integration_root="$(cd "${script_dir}/.." && pwd)"
compose_file="${COMPOSE_FILE:-${integration_root}/docker-compose.dev-gateway.yml}"

cd "${integration_root}"
docker compose -f "${compose_file}" down

