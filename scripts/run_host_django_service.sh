#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  cat >&2 <<'EOF'
usage: ./scripts/run_host_django_service.sh <service-repo-path> <env-file-path>

example:
  ./scripts/run_host_django_service.sh ../service-driver-profile ./infra/env/host/driver-profile.env.example
EOF
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
integration_root="$(cd "${script_dir}/.." && pwd)"
service_root="$(cd "${integration_root}/${1}" && pwd)"
env_file="$(cd "${integration_root}" && realpath "${2}")"

if [[ ! -f "${env_file}" ]]; then
  echo "env file not found: ${env_file}" >&2
  exit 2
fi

if [[ ! -f "${service_root}/manage.py" ]]; then
  echo "manage.py not found under: ${service_root}" >&2
  exit 3
fi

set -a
source "${env_file}"
set +a

cd "${service_root}"
python_bin="python3"
if [[ -x "${service_root}/.venv/bin/python" ]]; then
  python_bin="${service_root}/.venv/bin/python"
fi

"${python_bin}" manage.py runserver "0.0.0.0:${API_PORT:-8000}"
