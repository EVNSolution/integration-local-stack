# integration-local-stack

이 repo는 `clever-msa-platform`의 로컬 통합 실행 셸이다.

현재 역할:
- 여러 독립 service/front/gateway repo를 로컬에서 한 번에 띄우는 compose 진입점
- `.env.example`, seed orchestration, smoke 실행 기준 제공

현재 source 연결 상태:
- 현재 compose는 sibling target repo만 build context로 참조한다
- active runtime source는 모두 `../` 아래의 target repo들에 있다
- `MSA-Server`는 더 이상 runtime build context가 아니다
- `service-terminal-registry`는 active runtime repo로 compose에 편입됐다
- `service-dispatch-registry`는 active runtime repo로 compose에 편입됐다
- `service-dispatch-operations-view`는 active runtime repo로 compose에 편입됐다
- `service-driver-operations-view`는 driver ops read runtime으로 compose에 편입됐다
- `service-settlement-payroll`는 settlement write owner runtime으로 compose에 편입됐다
- `service-settlement-operations-view`는 settlement read fan-out runtime으로 compose에 편입됐다
- `service-telemetry-hub`는 active runtime repo로 compose에 편입됐다
- `service-telemetry-listener`는 active runtime repo로 compose에 편입됐다
- `service-telemetry-dead-letter`는 active runtime repo로 compose에 편입됐다
- `mqtt-broker`는 local-only deterministic telemetry ingress source로 compose에 편입됐다

포함:
- `docker-compose.account-driver-settlement.yml`
- `infra/env/local/`
- `infra/env/deploy/`
- `infra/mqtt/`
- `infra/docker/seed-runner/`
- `scripts/`
- `compose/README.md`
- 이후 local smoke/bootstrap 스크립트

포함하지 않음:
- 도메인 모델 정본
- 서비스 내부 비즈니스 로직
- gateway 서비스 소스
- front 서비스 소스

## Env Template Rule

- 로컬 통합 검증용 compose와 seed-runner는 `infra/env/local/` 템플릿만 사용한다.
- 배포 runtime compose는 `infra/env/deploy/` 템플릿만 사용한다.
- 로컬 편의 설정과 deploy runtime 설정을 같은 env 파일에서 관리하지 않는다.

현재 local stack에는 `dispatch-ops-api`가 포함된다.
- `service-dispatch-registry`, `service-vehicle-assignment`, `service-vehicle-registry`, `service-driver-profile`를 fan-out read 하는 read-model runtime이다.
- sqlite-only runtime이며 dedicated Postgres container를 추가하지 않는다.

현재 local stack의 settlement는 `settlement-payroll-api`와 `settlement-ops-api`로 분리된다.
- `/api/settlements/`는 write owner `settlement-payroll-api`로 연결된다.
- `/api/settlement-ops/`는 read-only fan-out `settlement-ops-api`로 연결된다.
- read consumer env는 `SETTLEMENT_OPS_BASE_URL`를 사용한다.
- settlement Postgres는 `settlement-payroll-api`만 사용하고 `settlement-ops-api`는 sqlite-only runtime이다.

실행 문서:
- compose 시뮬레이션 설명은 [compose/README.md](./compose/README.md)
- 플랫폼 전체 경계는 [../../docs/](../../docs/README.md)
- current MSA API 문서 entry는 [compose/api-docs/README.md](./compose/api-docs/README.md)
- current MSA API 문서 재생성 helper는 `./scripts/refresh_api_docs.py`
- current MSA API 문서 preview helper는 `./scripts/preview_api_docs.py`
- root repo GitHub Actions entry는 `../../.github/workflows/refresh-api-docs.yml`

## Local Telemetry Smoke

`service-telemetry-listener`의 deterministic smoke publish는 다음 조합을 사용한다.

- sample payload: [`../service-telemetry-listener/tests/fixtures/sample_payload.json`](../service-telemetry-listener/tests/fixtures/sample_payload.json)
- helper: [`./scripts/publish_sample_telemetry.sh`](./scripts/publish_sample_telemetry.sh)
- topic: `telemetry/vehicles/50000000-0000-0000-0000-000000000001/location-update`

helper는 baseline sample payload를 읽고 publish 시점마다 `captured_at`과 diagnostic timestamp를 새로 주입한다. 주입값은 현재 UTC 기준 하루 뒤로 잡혀서 seeded snapshot보다 항상 새롭다.

helper는 로컬 브로커의 local demo MQTT credentials only 를 사용한다.
- username: `telemetry-listener`
- password: `local-mqtt-password`

## Deterministic Failure Smoke

`service-telemetry-listener`의 dead-letter smoke는 malformed JSON fixture를 사용해 listener-side `parse_error`를 반복 재현한다.

- malformed payload: [`../service-telemetry-listener/tests/fixtures/malformed_payload.txt`](../service-telemetry-listener/tests/fixtures/malformed_payload.txt)
- helper: [`./scripts/publish_malformed_telemetry.sh`](./scripts/publish_malformed_telemetry.sh)
- topic: `telemetry/vehicles/50000000-0000-0000-0000-000000000001/location-update`

helper는 payload를 가공하지 않고 그대로 publish한다. 이 경로는 manual payload crafting 없이 local smoke에서 최소 1개의 dead-letter row를 생성하는 목적이다.

listener는 gateway 경로가 아니라 telemetry-hub 내부 경로 `/ingest/raw/` 를 사용한다.
dead-letter write도 gateway를 거치지 않고 dead-letter service 내부 경로 `/ingest/` 를 사용한다.

phase 1 dead-letter producer key는 service-specific env만 채운다.
- listener source_service: `service-telemetry-listener`
- listener producer key env: `TELEMETRY_DEAD_LETTER_KEY_SERVICE_TELEMETRY_LISTENER`

브로커 컨테이너 이미지에 `mosquitto_pub`가 있어야 한다. 없다면 helper는 명시적으로 실패한다.

## Dead-Letter Gateway Route Smoke

dead-letter gateway 노출 규칙은 다음 helper로 자동 검증할 수 있다.

- helper: [`./scripts/verify_dead_letter_gateway_routes.py`](./scripts/verify_dead_letter_gateway_routes.py)

기본 검증 범위:
- `/api/telemetry-dead-letters/health/` 는 `200`
- `/api/telemetry-dead-letters/` 와 detail route 는 gateway에 노출되지만 unauthenticated 기준 `401`
- `/api/telemetry-dead-letters/ingest` 와 `/api/telemetry-dead-letters/ingest/` 는 gateway 기준 `404`
- no-slash canonical redirect 는 `301`

실행 예시:

```bash
python3 ./development/integration-local-stack/scripts/verify_dead_letter_gateway_routes.py
```
