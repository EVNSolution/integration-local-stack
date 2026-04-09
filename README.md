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
- `docker-compose.dev-infra.yml`
- `docker-compose.dev-gateway.yml`
- `infra/env/local/`
- `infra/env/host/`
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

## Frontend Local Development Rule

프런트 수정 중에는 `web-console` 이미지를 수정마다 다시 빌드하지 않는다.

표준 루프는 아래다.

1. backend와 gateway는 compose로 한 번 띄운다.
2. frontend는 child repo에서 host dev server로 띄운다.
3. UI 수정 확인은 `http://localhost:5174`에서 한다.
4. gateway/auth/API 포함 통합 확인은 `http://localhost:8080`에서 한다.
5. `docker compose ... up -d --build web-console`는 최종 통합 확인 시점에만 실행한다.

권장 명령:

```bash
cd /Users/jiin/Documents/Files/02_EVnSolution/00_Source_code/CLEVER/clever-msa-platform/development/integration-local-stack
docker compose -f docker-compose.account-driver-settlement.yml up -d gateway
```

```bash
cd /Users/jiin/Documents/Files/02_EVnSolution/00_Source_code/CLEVER/clever-msa-platform/development/front-web-console
npm run dev
```

이 규칙의 목적은 frontend edit loop에서 Docker Desktop rebuild latency를 제거하고, 최종 통합 검증만 Docker image 기준으로 남기는 것이다.

## Low CPU Hybrid Development

Docker Desktop이 무거운 환경에서는 full compose를 상시 띄우지 않는다.

권장 기준:
- Docker Desktop 리소스는 `2 CPU / 2 GiB RAM`으로 낮춘다.
- Docker AI는 끈다.
- 평소에는 `docker-compose.dev-infra.yml`로 DB/redis만 띄운다.
- backend는 필요한 repo만 host에서 실행한다.
- frontend는 계속 `http://localhost:5174`에서 확인한다.
- `http://localhost:8080` full integration은 최종 확인 시점에만 쓴다.

infra-only 실행:

```bash
cd /Users/jiin/Documents/Files/02_EVnSolution/00_Source_code/CLEVER/clever-msa-platform/development/integration-local-stack
docker compose -f docker-compose.dev-infra.yml up -d
```

또는:

```bash
./scripts/up_dev_infra.sh
```

infra-only 정지:

```bash
cd /Users/jiin/Documents/Files/02_EVnSolution/00_Source_code/CLEVER/clever-msa-platform/development/integration-local-stack
docker compose -f docker-compose.dev-infra.yml down
```

또는:

```bash
./scripts/down_dev_infra.sh
```

현재 `docker-compose.dev-infra.yml`는 dispatch + settlement slice 기준으로 아래만 띄운다.
- `redis`
- `account-db`
- `driver-db`
- `settlement-db`
- `settlement-registry-db`
- `delivery-record-db`
- `org-db`
- `vehicle-db`
- `dispatch-registry-db`

host 연결용 포트:
- `redis`: `127.0.0.1:16379`
- `account-db`: `127.0.0.1:15431`
- `driver-db`: `127.0.0.1:15432`
- `settlement-db`: `127.0.0.1:15433`
- `settlement-registry-db`: `127.0.0.1:15434`
- `delivery-record-db`: `127.0.0.1:15435`
- `org-db`: `127.0.0.1:15436`
- `vehicle-db`: `127.0.0.1:15437`
- `dispatch-registry-db`: `127.0.0.1:15438`

host에서 Django 서비스를 띄울 때는 기존 `infra/env/local/*.env.example`를 기준으로 아래만 override하면 된다.
- `POSTGRES_HOST=127.0.0.1`
- 각 서비스에 맞는 `POSTGRES_PORT`
- container service name으로 적혀 있던 `*_BASE_URL`은 host에서 띄운 주소로 교체

예:
- `driver-profile` host 실행: `POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=15432`
- `dispatch-registry` host 실행: `POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=15438`
- `settlement-registry` host 실행: `POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=15434`
- `delivery-record` host 실행: `POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=15435`
- `settlement-payroll` host 실행: `POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=15433`

Docker Desktop 설정 변경은 앱 재시작 후 반영된다.

### Optional Dev Gateway

`5174`의 host frontend와 host Django services를 `http://localhost:8080`으로 다시 묶고 싶으면 dev gateway만 따로 띄운다.

실행:

```bash
cd /Users/jiin/Documents/Files/02_EVnSolution/00_Source_code/CLEVER/clever-msa-platform/development/integration-local-stack
./scripts/up_dev_gateway.sh
```

정지:

```bash
cd /Users/jiin/Documents/Files/02_EVnSolution/00_Source_code/CLEVER/clever-msa-platform/development/integration-local-stack
./scripts/down_dev_gateway.sh
```

이 gateway는 아래 host 포트로 프록시한다.
- `/` -> `http://127.0.0.1:5174`
- `/api/auth/` -> `18001`
- `/api/org/` -> `18002`
- `/api/drivers/` -> `18003`
- `/api/vehicles/` -> `18004`
- `/api/dispatch/` -> `18005`
- `/api/settlement-registry/` -> `18006`
- `/api/delivery-record/` -> `18007`
- `/api/settlements/` -> `18008`
- `/api/settlement-ops/` -> `18009`

### Host Env Templates

dispatch + settlement slice용 host env template는 `infra/env/host/` 아래에 둔다.

- [account-auth.env.example](./infra/env/host/account-auth.env.example)
- [organization-master.env.example](./infra/env/host/organization-master.env.example)
- [driver-profile.env.example](./infra/env/host/driver-profile.env.example)
- [vehicle-asset.env.example](./infra/env/host/vehicle-asset.env.example)
- [dispatch-registry.env.example](./infra/env/host/dispatch-registry.env.example)
- [settlement-registry.env.example](./infra/env/host/settlement-registry.env.example)
- [delivery-record.env.example](./infra/env/host/delivery-record.env.example)
- [settlement-payroll.env.example](./infra/env/host/settlement-payroll.env.example)
- [settlement-ops.env.example](./infra/env/host/settlement-ops.env.example)

이 template들은 `docker-compose.dev-infra.yml`의 DB/redis 포트와 `docker-compose.dev-gateway.yml`의 host service 포트 기준으로 맞춰져 있다.

host Django 서비스 실행 helper:

```bash
./scripts/bootstrap_host_python_env.sh ../service-driver-profile
./scripts/bootstrap_host_python_env.sh ../service-organization-registry
./scripts/bootstrap_host_python_env.sh ../service-account-access

./scripts/migrate_host_django_service.sh ../service-driver-profile ./infra/env/host/driver-profile.env.example
./scripts/migrate_host_django_service.sh ../service-organization-registry ./infra/env/host/organization-master.env.example
./scripts/migrate_host_django_service.sh ../service-account-access ./infra/env/host/account-auth.env.example

./scripts/run_host_django_service.sh ../service-driver-profile ./infra/env/host/driver-profile.env.example
./scripts/run_host_django_service.sh ../service-organization-registry ./infra/env/host/organization-master.env.example
./scripts/run_host_django_service.sh ../service-account-access ./infra/env/host/account-auth.env.example
```

`bootstrap_host_python_env.sh`는 service repo별 `.venv`를 만들고 `requirements.txt`를 설치한다. 상대경로와 절대경로 둘 다 받을 수 있다.

`migrate_host_django_service.sh`는 같은 env file을 export한 뒤 `manage.py migrate`를 실행한다. 새 DB를 붙일 때는 첫 실행 전에 한 번 돌린다.

`run_host_django_service.sh`는 env file을 export한 뒤 service repo에 `.venv/bin/python`이 있으면 그 interpreter로 `manage.py runserver`를 실행한다. `.venv`가 없으면 `python3`로 fallback한다. 상대경로와 절대경로 둘 다 받을 수 있다.

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
