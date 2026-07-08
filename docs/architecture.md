# Architecture

Source Signal is a repo-contained local product for ranking business context before an automation system uses it in email workflows. It uses deterministic policy, synthetic fixtures, local JSONL persistence, a FastAPI backend, and a React UI.

## Layers

```text
fixtures/ -> loader -> scoring/ranking -> decision engine -> agent loop
                                      -> FastAPI -> React UI
                                      -> local JSONL stores
```

### Core Models

The core models live under `src/data_source_ranking/`.

- `models.py` defines context needs, sources, claims, owners, weak points, ranked sources, and ranked bundles.
- Scoring modules evaluate the nine evidence dimensions.
- `ranking.py` assigns source tiers and bundle-level evidence decisions.
- `decision_engine.py` creates the product-facing `AutomationDecision`.
- `review_responses.py` applies deterministic review responses.

The UI should render these objects. It should not recreate scoring, policy gates, or decision precedence in the browser.

### Agent Loop

The agent layer lives under `src/data_source_ranking/agents/`.

The loop shape is:

```text
rank -> decide -> inspect weak point -> take one bounded action -> decide again -> stop
```

Supported local actions include owner-response application, simulated retrieval, user review handoff, auto-handoff stop, and blocked stop. The agent loop is deterministic and bounded; it does not run open-ended LLM tool calls.

### API

The FastAPI app lives in `api/main.py`.

The API owns product workflow state:

- fixture discovery
- ranking and decision runs
- custom evidence decision runs
- agent runs
- persisted run history
- review queue
- inline review submissions
- run-attached feedback
- reliability snapshots
- local workspace reset

Important endpoints:

```text
GET  /health
GET  /fixtures
GET  /fixtures/{fixture_id}
POST /rank
POST /rank/custom
POST /decide
POST /run-agent
POST /runs/decide
POST /runs/custom/decide
POST /runs/agent
GET  /runs
GET  /runs/{run_id}
GET  /reviews/queue
POST /apply-review
POST /runs/{run_id}/review
POST /runs/{run_id}/feedback
POST /feedback
GET  /feedback/snapshot
POST /admin/reset-local-data
```

The product UI should use `POST /rank` and `POST /rank/custom` for non-persisted source-quality checks, and prefer persisted run endpoints when a workflow should become history:

```text
POST /rank
POST /rank/custom
POST /runs/decide
POST /runs/custom/decide
POST /runs/agent
GET  /runs
GET  /runs/{run_id}
GET  /reviews/queue
POST /runs/{run_id}/review
POST /runs/{run_id}/feedback
GET  /feedback/snapshot
POST /admin/reset-local-data
```

For AWS deployment, the same FastAPI app is packaged as a Python Lambda through `api/lambda_handler.py` using Mangum. Amplify creates an API Gateway REST API as a proxy to that Lambda, protects application methods with the Amplify Cognito user pool, and emits the endpoint under `custom.API.SourceSignalProductApi` in Amplify outputs. Local development still runs the same app with Uvicorn.

### Persistence

Week 3 persistence is local by default and API-owned.

```text
data/api_runs.jsonl
data/api_run_reviews.jsonl
data/feedback_events.jsonl
```

These stores are intentionally simple. UI-facing requests do not pass filesystem paths; the paths live behind API settings. Resetting local product state also goes through an API endpoint, which keeps the UI portable across local and AWS-backed storage.

The API now uses a `ProductStore` boundary. `local_jsonl` remains the default backend, while `dynamodb` can be selected with:

```text
API_PRODUCT_STORE_BACKEND=dynamodb
API_DYNAMODB_RUN_TABLE=<table name>
API_DYNAMODB_REVIEW_EVENT_TABLE=<table name>
API_DYNAMODB_FEEDBACK_TABLE=<table name>
AWS_REGION=<region>
```

The Amplify Gen 2 backend creates product-state DynamoDB tables for persisted runs, review events, and feedback events. It emits the table names and API environment mapping under `custom.productState` in Amplify outputs. The existing Amplify Data schema file still documents the broader future product model for workspaces, clients, scenarios, evidence sources, runs, review tasks, feedback signals, and source-system connections, but it is not deployed in the current backend because the live app persists through the FastAPI-owned product-state tables.

### UI

The React app lives in `ui/`.

Local development uses `VITE_API_BASE_URL` when it is set and otherwise falls back to `http://127.0.0.1:8000`. Amplify Hosting uses the root `amplify.yml` build: the backend is deployed, Amplify outputs are generated, `scripts/write-ui-api-env.mjs` writes `ui/.env.production.local`, and the Vite build reads the API endpoint plus Cognito user-pool client values.

Main routes:

```text
/               decision console with rank-only, decision, custom evidence, and guided checks
/runs/:runId    run detail
/runs/:runId/report
/review/local   review inbox
/review/:runId  review portal
/settings       local settings, theme controls, systems readiness, and data reset
```

The UI uses TanStack Query over the FastAPI endpoints. When Cognito env values are present, it shows a compact sign-in gate and sends the current user-pool token on API requests; without those values it stays in local unauthenticated mode. It displays backend results, standalone ranking, run history, review work, feedback learning, score breakdowns, audit timelines, and presentation-ready run reports. Manual evidence entry still submits backend-owned `SourceBundle` payloads, so the browser does not recreate scoring or decision policy.

## Product Boundaries

Implemented locally:

- synthetic fixture provider
- deterministic ranking and decision policy
- bounded agent loop
- local FastAPI product workflows
- local React UI
- run history
- review events
- feedback learning
- theme/settings controls
- systems readiness settings
- Cognito-protected AWS API access
- Amplify-ready data model scaffold, not deployed in the current backend

Simulated or deferred:

- real CRM, Drive, Calendar, proposal, and email connectors
- external database storage
- background jobs
- live owner notifications
- open-ended LLM agent autonomy
- semantic contradiction detection across claim meaning

## Design Rule

The backend owns trust decisions. The UI owns presentation and workflow ergonomics. Future integrations should feed evidence into the same core contract instead of bypassing or duplicating it.
