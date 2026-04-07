# Current MSA API Docs

이 디렉토리는 CLEVER current MSA API 문서용 unified OpenAPI artifact와 local viewer entry를 둔다.

원칙:

- 설계 정본은 `../../../docs/decisions/specs/2026-03-26-clever-unified-openapi-and-api-mcp-design.md`
- 읽기 가이드는 `../../../docs/mappings/08-current-msa-api-docs-reading-guide.md`
- generated OpenAPI artifact는 이 디렉토리의 local build output이다.
- generated artifact는 git에 커밋하지 않고 필요할 때 재생성한다.

현재 파일:

- `index.html`
  - local viewer entry

## Build

플랫폼 루트에서 아래 명령을 실행한다.

```bash
python3 ./development/integration-local-stack/scripts/refresh_api_docs.py
```

기본 helper는 아래 세 단계를 한 번에 실행한다.

```bash
python3 ./development/integration-local-stack/scripts/export_service_openapi.py --keep-going
python3 ./development/integration-local-stack/scripts/build_unified_openapi.py
python3 ./development/integration-local-stack/scripts/verify_api_docs.py
```

옵션 예시:

```bash
python3 ./development/integration-local-stack/scripts/refresh_api_docs.py --strict
python3 ./development/integration-local-stack/scripts/refresh_api_docs.py --skip-verify
python3 ./development/integration-local-stack/scripts/refresh_api_docs.py --service service-telemetry-hub --service service-terminal-registry
python3 ./development/integration-local-stack/scripts/refresh_api_docs.py --build-only
```

build source는 아래 두 종류다.

- `docs/mappings/current-runtime-inventory.md`
- `docs/mappings/repo-responsibility-matrix.md`
- `development/service-*/**/urls.py`
- `development/service-*/**/views.py`
- `development/integration-local-stack/compose/api-docs/service-schemas/*.openapi.yaml`

service-owned OpenAPI export는 현재 아래 서비스부터 붙인다.

- `service-account-access`
- `service-personnel-document-registry`
- `service-delivery-record`
- `service-organization-registry`
- `service-driver-profile`
- `service-vehicle-registry`
- `service-vehicle-assignment`
- `service-vehicle-operations-view`
- `service-dispatch-registry`
- `service-dispatch-operations-view`
- `service-driver-operations-view`
- `service-settlement-payroll`
- `service-settlement-registry`
- `service-settlement-operations-view`
- `service-terminal-registry`
- `service-telemetry-hub`
- `service-telemetry-dead-letter`

schema export에 실패한 서비스는 unified build에서 자동으로 route inventory fallback으로 남는다.

verify helper는 현재 목표 기준으로 아래를 검사한다.

- active HTTP service 전부가 unified spec에 포함되는지
- `route-inventory` fallback operation이 남아 있지 않은지
- `components.schemas` 가 비어 있지 않은지
- path/response/request 안의 `$ref` 가 모두 해석되는지

## View

artifact를 만든 뒤 아래처럼 정적 서버로 본다.

```bash
python3 ./development/integration-local-stack/scripts/preview_api_docs.py
```

preview helper는 기본적으로 아래를 한 번에 수행한다.

```bash
python3 ./development/integration-local-stack/scripts/refresh_api_docs.py
python3 -m http.server 8099 --directory ./development/integration-local-stack/compose/api-docs
```

옵션 예시:

```bash
python3 ./development/integration-local-stack/scripts/preview_api_docs.py --skip-refresh
python3 ./development/integration-local-stack/scripts/preview_api_docs.py --port 8101
python3 ./development/integration-local-stack/scripts/preview_api_docs.py --service service-telemetry-hub --service service-terminal-registry
```

브라우저에서 `http://localhost:8099/` 를 연다.

GitHub에 이 루트를 단일 repo로 올리면 root-level workflow `/.github/workflows/refresh-api-docs.yml` 로 같은 refresh를 CI에서 자동 실행할 수 있다.

## Current MSA 성격

현재 산출물은 active MSA HTTP service만 포함한다.

- path는 현재 gateway 외부 prefix를 따른다.
- tag는 active runtime repo 이름 그대로 쓴다.
- service-owned OpenAPI가 있으면 request/response schema를 우선 사용한다.
- 없으면 method와 기본 endpoint metadata를 각 서비스 코드의 `views.py` class 형태에서 추론한다.
