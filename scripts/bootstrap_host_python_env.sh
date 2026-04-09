#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  cat >&2 <<'EOF'
usage: ./scripts/bootstrap_host_python_env.sh <service-repo-path> [venv-path]

example:
  ./scripts/bootstrap_host_python_env.sh ../service-driver-profile
  ./scripts/bootstrap_host_python_env.sh ../service-driver-profile /private/tmp/service-driver-profile-venv
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
venv_path="${2:-${service_root}/.venv}"

requirements_file="${service_root}/requirements.txt"
if [[ ! -f "${requirements_file}" ]]; then
  echo "requirements.txt not found under: ${service_root}" >&2
  exit 2
fi

python_bin="${PYTHON_BIN:-}"
if [[ -z "${python_bin}" ]]; then
  for candidate in python3.12 python3 python; do
    if command -v "${candidate}" >/dev/null 2>&1; then
      candidate_path="$(command -v "${candidate}")"
      if "${candidate_path}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
        python_bin="${candidate_path}"
        break
      fi
    fi
  done
fi

if [[ -z "${python_bin}" ]]; then
  echo "python 3.10+ interpreter not found. Set PYTHON_BIN explicitly." >&2
  exit 3
fi

if [[ ! -d "${venv_path}" ]]; then
  "${python_bin}" -m venv "${venv_path}"
fi

if ! "${venv_path}/bin/python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "venv python is below 3.10: ${venv_path}/bin/python" >&2
  echo "remove the venv and retry with PYTHON_BIN=/path/to/python3.12" >&2
  exit 4
fi

"${venv_path}/bin/python" -m pip install --upgrade pip
"${venv_path}/bin/python" -m pip install -r "${requirements_file}"

cat <<EOF
python venv ready:
  service: ${service_root}
  venv: ${venv_path}
  python: ${venv_path}/bin/python
  source-python: ${python_bin}
EOF
