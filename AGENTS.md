# AGENTS.md

## Must Know

- This repo is the local integration shell for CLEVER MSA.
- It owns local compose entrypoints, env templates, seed orchestration, and local smoke/bootstrap helpers only.
- Treat `../../docs/` as the architecture source of truth and this repo as runtime glue, not a domain source of truth.

## What Belongs Here

- `docker-compose*.yml`
- `infra/env/local/`
- `infra/env/deploy/`
- `infra/docker/seed-runner/`
- local smoke scripts
- local bootstrap helpers

## What Must Not Be Added Here

- domain models or business logic from any `service-*` repo
- front application code from any `front-*` repo
- gateway runtime source from `edge-api-gateway/`
- cross-service shared packages
- architecture specs, boundary decisions, or mapping docs that belong in `../../docs/`

## Coordination Rules

- When compose paths change, update this repo and the affected target repo README together.
- `seed-runner` must call service-local management commands. Do not write directly to service databases here.
- If a change affects service boundaries, stop and update the approved docs before changing runtime glue.
- Prefer gateway-based verification so routing, auth, and cross-repo wiring are exercised together.

## Current Scope Notes

- Active runtime repos live as siblings under `../`.
- Settlement local wiring is split across `../service-settlement-payroll/` and `../service-settlement-operations-view/`.
- `service-terminal-registry` and `service-telemetry-hub` are active runtime repos. Keep compose wiring aligned with their approved boundary specs and do not push unrelated logic into this repo.
