#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
integration_root="$(cd "${script_dir}/.." && pwd)"
listener_root="$(cd "${integration_root}/../service-telemetry-listener" && pwd)"
compose_file="${COMPOSE_FILE:-${integration_root}/docker-compose.account-driver-settlement.yml}"
topic="${1:-telemetry/vehicles/50000000-0000-0000-0000-000000000001/location-update}"
payload_file="${2:-${listener_root}/tests/fixtures/malformed_payload.txt}"

if [[ ! -f "${payload_file}" ]]; then
  echo "malformed payload not found: ${payload_file}" >&2
  exit 1
fi

if ! docker compose -f "${compose_file}" exec -T mqtt-broker sh -lc 'command -v mosquitto_pub >/dev/null 2>&1' >/dev/null 2>&1; then
  cat >&2 <<'EOF'
mosquitto_pub is not available in the mqtt-broker container image.
Use a local demo broker image that includes the client utility, or publish from a container that provides it.
EOF
  exit 2
fi

echo "Publishing ${payload_file} to ${topic}"
echo "Expected listener failure path: parse_error"

docker compose -f "${compose_file}" exec -T \
  -e MQTT_USERNAME="${TELEMETRY_LISTENER_MQTT_USERNAME:-telemetry-listener}" \
  -e MQTT_PASSWORD="${TELEMETRY_LISTENER_MQTT_PASSWORD:-local-mqtt-password}" \
  -e MQTT_TOPIC="${topic}" \
  mqtt-broker \
  sh -lc 'mosquitto_pub -h 127.0.0.1 -p 1883 -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" -t "$MQTT_TOPIC" -s' \
  < "${payload_file}"
