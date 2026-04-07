#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
integration_root="$(cd "${script_dir}/.." && pwd)"
listener_root="$(cd "${integration_root}/../service-telemetry-listener" && pwd)"
compose_file="${COMPOSE_FILE:-${integration_root}/docker-compose.account-driver-settlement.yml}"
topic="${1:-telemetry/vehicles/50000000-0000-0000-0000-000000000001/location-update}"
payload_file="${2:-${listener_root}/tests/fixtures/sample_payload.json}"

if [[ ! -f "${payload_file}" ]]; then
  echo "sample payload not found: ${payload_file}" >&2
  exit 1
fi

if ! docker compose -f "${compose_file}" exec -T mqtt-broker sh -lc 'command -v mosquitto_pub >/dev/null 2>&1' >/dev/null 2>&1; then
  cat >&2 <<'EOF'
mosquitto_pub is not available in the mqtt-broker container image.
Use a local demo broker image that includes the client utility, or publish from a container that provides it.
EOF
  exit 2
fi

published_at="$(python3 - <<'PY'
from datetime import datetime, timedelta, timezone
print((datetime.now(timezone.utc) + timedelta(days=1)).isoformat(timespec="microseconds").replace("+00:00", "Z"))
PY
)"

payload_body="$(python3 - <<'PY' "${payload_file}" "${published_at}"
import json
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])
published_at = sys.argv[2]
payload = json.loads(payload_path.read_text())
payload["captured_at"] = published_at
payload["diagnostics"] = [
    {**diagnostic, "captured_at": published_at}
    for diagnostic in payload.get("diagnostics", [])
]
print(json.dumps(payload, separators=(",", ":"), sort_keys=True))
PY
)"

echo "Publishing ${payload_file} to ${topic}"

docker compose -f "${compose_file}" exec -T \
  -e MQTT_USERNAME="${TELEMETRY_LISTENER_MQTT_USERNAME:-telemetry-listener}" \
  -e MQTT_PASSWORD="${TELEMETRY_LISTENER_MQTT_PASSWORD:-local-mqtt-password}" \
  -e MQTT_TOPIC="${topic}" \
  mqtt-broker \
  sh -lc 'mosquitto_pub -h 127.0.0.1 -p 1883 -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" -t "$MQTT_TOPIC" -s' \
  <<< "${payload_body}"
