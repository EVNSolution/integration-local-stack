Source: https://lessons.md

# integration-local-stack Lessons

## Keep Local And Deploy Env Templates Separate

`integration-local-stack` is the place where local verification convenience and deployed runtime structure meet, so env drift happens easily. Keep local verification templates under `infra/env/local/` and deployed runtime templates under `infra/env/deploy/`. Do not let local-only debug or shortcut flags leak into deploy templates.

## Startup Order Is Part Of The Contract

The stack is not “all containers at once.” The canonical local bring-up is the staged startup flow in `scripts/run_local_startup.py`. Treat the stage order as part of the operator contract, because infra, gateway, seed, and smoke each answer different failure questions.

## API Docs Drift Must Be Caught At The Stack Layer

The local stack owns unified API docs refresh and verification scripts. When a new service is active but missing from the docs aggregation rules, the failure shows up here first. Keep the docs scripts and the active runtime inventory aligned whenever a service changes status.
