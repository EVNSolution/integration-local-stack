#!/bin/sh
set -eu

ROOT_DIR="/workspace"

wait_for_health() {
  service_name="$1"
  url="$2"
  attempts=60
  count=0

  echo "Waiting for ${service_name} health at ${url}..."
  while [ "$count" -lt "$attempts" ]; do
    if python - "$url" <<'PY'
import sys
from urllib.error import URLError
from urllib.request import urlopen

url = sys.argv[1]
try:
    with urlopen(url, timeout=2) as response:
        raise SystemExit(0 if response.status == 200 else 1)
except URLError:
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
wait_for_health "terminal-registry" "http://terminal-registry-api:8000/health/"
wait_for_health "telemetry-hub" "http://telemetry-hub-api:8000/health/"
wait_for_health "settlement-payroll" "http://settlement-payroll-api:8000/health/"
wait_for_health "settlement-registry" "http://settlement-registry-api:8000/health/"
wait_for_health "account-auth" "http://account-auth-api:8000/health/"

run_manage "services/organization-master" "infra/env/organization-master.env.example" migrate --noinput
run_manage "services/organization-master" "infra/env/organization-master.env.example" seed_organization

run_manage "services/settlement-registry" "infra/env/settlement-registry.env.example" migrate --noinput
run_manage "services/settlement-registry" "infra/env/settlement-registry.env.example" seed_settlement_registry

run_manage "services/driver-profile" "infra/env/driver-profile.env.example" migrate --noinput
run_manage "services/driver-profile" "infra/env/driver-profile.env.example" seed_drivers

run_manage "services/personnel-document-registry" "infra/env/personnel-document-registry.env.example" migrate --noinput
run_manage "services/personnel-document-registry" "infra/env/personnel-document-registry.env.example" seed_personnel_documents

run_manage "services/delivery-record" "infra/env/delivery-record.env.example" migrate --noinput
run_manage "services/delivery-record" "infra/env/delivery-record.env.example" seed_delivery_records

run_manage "services/vehicle-asset" "infra/env/vehicle-asset.env.example" migrate --noinput
run_manage "services/vehicle-asset" "infra/env/vehicle-asset.env.example" seed_vehicles

run_manage "services/dispatch-registry" "infra/env/dispatch-registry.env.example" migrate --noinput
run_manage "services/dispatch-registry" "infra/env/dispatch-registry.env.example" seed_dispatch

run_manage "services/region-registry" "infra/env/region-registry.env.example" migrate --noinput
run_manage "services/region-registry" "infra/env/region-registry.env.example" seed_regions

run_manage "services/region-analytics" "infra/env/region-analytics.env.example" migrate --noinput
run_manage "services/region-analytics" "infra/env/region-analytics.env.example" seed_region_analytics

run_manage "services/announcement-registry" "infra/env/announcement-registry.env.example" migrate --noinput
run_manage "services/announcement-registry" "infra/env/announcement-registry.env.example" seed_announcements

run_manage "services/support-registry" "infra/env/support-registry.env.example" migrate --noinput
run_manage "services/support-registry" "infra/env/support-registry.env.example" seed_support

run_manage "services/notification-hub" "infra/env/notification-hub.env.example" migrate --noinput
run_manage "services/notification-hub" "infra/env/notification-hub.env.example" seed_notifications

run_manage "services/terminal-registry" "infra/env/terminal-registry.env.example" migrate --noinput
run_manage "services/terminal-registry" "infra/env/terminal-registry.env.example" seed_terminals

run_manage "services/telemetry-hub" "infra/env/telemetry-hub.env.example" migrate --noinput
run_manage "services/telemetry-hub" "infra/env/telemetry-hub.env.example" seed_telemetry

run_manage "services/driver-vehicle-assignment" "infra/env/driver-vehicle-assignment.env.example" migrate --noinput
run_manage "services/driver-vehicle-assignment" "infra/env/driver-vehicle-assignment.env.example" seed_assignments

run_manage "services/settlement-payroll" "infra/env/settlement-payroll.env.example" migrate --noinput
run_manage "services/settlement-payroll" "infra/env/settlement-payroll.env.example" seed_settlements

run_manage "services/account-auth" "infra/env/account-auth.env.example" migrate --noinput
run_manage "services/account-auth" "infra/env/account-auth.env.example" seed_accounts

echo "Seed runner completed successfully."
