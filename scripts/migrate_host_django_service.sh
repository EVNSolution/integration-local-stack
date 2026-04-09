#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  cat >&2 <<'EOF'
usage: ./scripts/migrate_host_django_service.sh <service-repo-path> <env-file-path>

example:
  ./scripts/migrate_host_django_service.sh ../service-dispatch-registry ./infra/env/host/dispatch-registry.env.example
EOF
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
integration_root="$(cd "${script_dir}/.." && pwd)"
service_arg="${1}"
if [[ "${service_arg}" = /* ]]; then
  service_root="$(cd "${service_arg}" && pwd)"
else
  service_root="$(cd "${integration_root}/${service_arg}" && pwd)"
fi
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

"${python_bin}" manage.py migrate
