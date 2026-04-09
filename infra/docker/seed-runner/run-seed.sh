#!/bin/sh
set -eu

ROOT_DIR="/workspace"
OPS_DERIVED_FIXTURE_PATH="${OPS_DERIVED_FIXTURE_PATH:-${ROOT_DIR}/fixtures/ops-derived-sample.json}"
ENABLE_OPS_DERIVED_FIXTURE_IMPORT="${ENABLE_OPS_DERIVED_FIXTURE_IMPORT:-0}"
OPS_FIXTURE_BOOTSTRAP_MODE="${OPS_FIXTURE_BOOTSTRAP_MODE:-0}"

wait_for_health() {
  service_name="$1"
  url="$2"
  attempts=60
  count=0

  echo "Waiting for ${service_name} health at ${url}..."
  while [ "$count" -lt "$attempts" ]; do
    if python - "$url" <<'PY'
import sys
from socket import timeout as SocketTimeout
from urllib.error import URLError
from urllib.request import urlopen

url = sys.argv[1]
try:
    with urlopen(url, timeout=2) as response:
        raise SystemExit(0 if response.status == 200 else 1)
except (URLError, TimeoutError, SocketTimeout):
    raise SystemExit(1)
PY
    then
      echo "${service_name} is healthy."
      return 0
    fi

    count=$((count + 1))
    sleep 2
  done

  echo "${service_name} did not become healthy in time." >&2
  exit 1
}

run_manage() {
  service_dir="$1"
  env_file="$2"
  shift 2

  (
    set -a
    . "${ROOT_DIR}/${env_file}"
    set +a
    cd "${ROOT_DIR}/${service_dir}"
    python manage.py "$@"
  )
}

maybe_migrate() {
  service_dir="$1"
  env_file="$2"

  if [ "$OPS_FIXTURE_BOOTSTRAP_MODE" = "1" ]; then
    return 0
  fi

  run_manage "$service_dir" "$env_file" migrate --noinput
}

wait_for_health "organization-master" "http://organization-master-api:8000/health/"
wait_for_health "driver-profile" "http://driver-profile-api:8000/health/"
wait_for_health "personnel-document-registry" "http://personnel-document-registry-api:8000/health/"
wait_for_health "delivery-record" "http://delivery-record-api:8000/health/"
wait_for_health "vehicle-asset" "http://vehicle-asset-api:8000/health/"
wait_for_health "dispatch-registry" "http://dispatch-registry-api:8000/health/"
wait_for_health "region-registry" "http://region-registry-api:8000/health/"
wait_for_health "region-analytics" "http://region-analytics-api:8000/health/"
wait_for_health "announcement-registry" "http://announcement-registry-api:8000/health/"
wait_for_health "support-registry" "http://support-registry-api:8000/health/"
wait_for_health "notification-hub" "http://notification-hub-api:8000/health/"
if [ "$OPS_FIXTURE_BOOTSTRAP_MODE" != "1" ]; then
  wait_for_health "terminal-registry" "http://terminal-registry-api:8000/health/"
  wait_for_health "telemetry-hub" "http://telemetry-hub-api:8000/health/"
fi
wait_for_health "settlement-payroll" "http://settlement-payroll-api:8000/health/"
wait_for_health "settlement-registry" "http://settlement-registry-api:8000/health/"
wait_for_health "account-auth" "http://account-auth-api:8000/health/"

maybe_migrate "services/organization-master" "infra/env/local/organization-master.env.example"
run_manage "services/organization-master" "infra/env/local/organization-master.env.example" seed_organization

maybe_migrate "services/settlement-registry" "infra/env/local/settlement-registry.env.example"
run_manage "services/settlement-registry" "infra/env/local/settlement-registry.env.example" seed_settlement_registry

maybe_migrate "services/driver-profile" "infra/env/local/driver-profile.env.example"
run_manage "services/driver-profile" "infra/env/local/driver-profile.env.example" seed_drivers

maybe_migrate "services/personnel-document-registry" "infra/env/local/personnel-document-registry.env.example"
run_manage "services/personnel-document-registry" "infra/env/local/personnel-document-registry.env.example" seed_personnel_documents

maybe_migrate "services/delivery-record" "infra/env/local/delivery-record.env.example"
run_manage "services/delivery-record" "infra/env/local/delivery-record.env.example" seed_delivery_records

maybe_migrate "services/vehicle-asset" "infra/env/local/vehicle-asset.env.example"
run_manage "services/vehicle-asset" "infra/env/local/vehicle-asset.env.example" seed_vehicles

maybe_migrate "services/dispatch-registry" "infra/env/local/dispatch-registry.env.example"
run_manage "services/dispatch-registry" "infra/env/local/dispatch-registry.env.example" seed_dispatch

maybe_migrate "services/region-registry" "infra/env/local/region-registry.env.example"
run_manage "services/region-registry" "infra/env/local/region-registry.env.example" seed_regions

maybe_migrate "services/region-analytics" "infra/env/local/region-analytics.env.example"
run_manage "services/region-analytics" "infra/env/local/region-analytics.env.example" seed_region_analytics

maybe_migrate "services/announcement-registry" "infra/env/local/announcement-registry.env.example"
run_manage "services/announcement-registry" "infra/env/local/announcement-registry.env.example" seed_announcements

maybe_migrate "services/support-registry" "infra/env/local/support-registry.env.example"
run_manage "services/support-registry" "infra/env/local/support-registry.env.example" seed_support

maybe_migrate "services/notification-hub" "infra/env/local/notification-hub.env.example"
run_manage "services/notification-hub" "infra/env/local/notification-hub.env.example" seed_notifications

if [ "$OPS_FIXTURE_BOOTSTRAP_MODE" != "1" ]; then
  maybe_migrate "services/terminal-registry" "infra/env/local/terminal-registry.env.example"
  run_manage "services/terminal-registry" "infra/env/local/terminal-registry.env.example" seed_terminals

  maybe_migrate "services/telemetry-hub" "infra/env/local/telemetry-hub.env.example"
  run_manage "services/telemetry-hub" "infra/env/local/telemetry-hub.env.example" seed_telemetry
fi

maybe_migrate "services/driver-vehicle-assignment" "infra/env/local/driver-vehicle-assignment.env.example"
run_manage "services/driver-vehicle-assignment" "infra/env/local/driver-vehicle-assignment.env.example" seed_assignments

maybe_migrate "services/settlement-payroll" "infra/env/local/settlement-payroll.env.example"
run_manage "services/settlement-payroll" "infra/env/local/settlement-payroll.env.example" seed_settlements

maybe_migrate "services/account-auth" "infra/env/local/account-auth.env.example"
run_manage "services/account-auth" "infra/env/local/account-auth.env.example" seed_accounts

if [ "$ENABLE_OPS_DERIVED_FIXTURE_IMPORT" = "1" ]; then
  echo "Importing ops-derived local fixture from ${OPS_DERIVED_FIXTURE_PATH}..."
  run_manage "services/organization-master" "infra/env/local/organization-master.env.example" import_ops_fixture --fixture "${OPS_DERIVED_FIXTURE_PATH}"
  run_manage "services/driver-profile" "infra/env/local/driver-profile.env.example" import_ops_fixture --fixture "${OPS_DERIVED_FIXTURE_PATH}"
  run_manage "services/vehicle-asset" "infra/env/local/vehicle-asset.env.example" import_ops_fixture --fixture "${OPS_DERIVED_FIXTURE_PATH}"
  run_manage "services/driver-vehicle-assignment" "infra/env/local/driver-vehicle-assignment.env.example" import_ops_fixture --fixture "${OPS_DERIVED_FIXTURE_PATH}"
  run_manage "services/dispatch-registry" "infra/env/local/dispatch-registry.env.example" import_ops_fixture --fixture "${OPS_DERIVED_FIXTURE_PATH}"
  run_manage "services/delivery-record" "infra/env/local/delivery-record.env.example" import_ops_fixture --fixture "${OPS_DERIVED_FIXTURE_PATH}"
  run_manage "services/settlement-payroll" "infra/env/local/settlement-payroll.env.example" import_ops_fixture --fixture "${OPS_DERIVED_FIXTURE_PATH}"
  run_manage "services/region-registry" "infra/env/local/region-registry.env.example" import_ops_fixture --fixture "${OPS_DERIVED_FIXTURE_PATH}"
  run_manage "services/region-analytics" "infra/env/local/region-analytics.env.example" import_ops_fixture --fixture "${OPS_DERIVED_FIXTURE_PATH}"
  run_manage "services/personnel-document-registry" "infra/env/local/personnel-document-registry.env.example" import_ops_fixture --fixture "${OPS_DERIVED_FIXTURE_PATH}"
fi

echo "Seed runner completed successfully."
