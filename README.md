# Data Source Ranking

Prototype for ranking retrieved business context before an automation system uses it in generated email workflows.

Use this prototype as an inspectable trust gate. It scores normalized source records, ranks source bundles, applies policy gates, and returns a structured automation decision that a CLI, API, or future UI can render without recalculating policy.

## Current Capabilities

- Source ranking into `strong`, `medium`, or `weak`.
- Bundle decisions across `auto_handoff`, `generate_context_request`, `needs_user_review`, and `blocked`.
- Product-facing automation decisions with confidence, policy gates, selected evidence, source citations, next action, audit trace, and metadata.
- Context requests for owner-validation cases.
- Focused approval prompts for similar-client context, unclear ownership, sensitive evidence overlap, unsupported claims, sensitive partner material, and old proposals.
- Source-backed draft handoff text for safe auto-handoff cases.
- Structured blocked output for safety-stop cases.
- Review-response validation and deterministic transitions through `apply-review`.
- A bounded `run-agent` loop that can apply owner-response or simulated-retrieval fixtures, re-run the decision, and record an audit timeline.
- Feedback event models, local JSONL persistence, conservative reliability snapshots, and feedback-aware agent audit output.
- FastAPI foundation with health, fixture discovery, ranking, decision, agent-run, review-application, and feedback endpoints for the future UI.
- Synthetic source, bundle, review, owner-response, and simulated-retrieval fixtures for repeatable demos.

Source tiers describe individual evidence strength. Bundle ranking combines those sources into an evidence-layer decision. The `decide` command returns the product decision: use the context, ask an owner, ask the current user, or stop automation.

## Setup

```bash
uv sync --extra dev
```

If `uv` is unavailable, create a Python 3.12 virtual environment and install the dependencies from `pyproject.toml`.

Run commands through the installed script:

```bash
data-source-ranking --help
```

You can also run the module form from the repo:

```bash
python -m data_source_ranking.cli --help
```

## Demo Path

Use the stable fixture date for repeatable output:

```bash
export AS_OF=2026-06-21
```

Validate fixture data:

```bash
data-source-ranking validate-fixtures fixtures
```

Inspect a strong source:

```bash
data-source-ranking rank-source fixtures/strong/acme_recent_crm_note.json --as-of "$AS_OF"
```

Inspect an evidence bundle:

```bash
data-source-ranking rank-bundle fixtures/bundles/acme_auto_handoff.json --as-of "$AS_OF"
```

Produce a full automation decision:

```bash
data-source-ranking decide fixtures/bundles/acme_auto_handoff.json --as-of "$AS_OF"
```

Inspect a focused review case:

```bash
data-source-ranking decide fixtures/bundles/northstar_similar_client_review.json --as-of "$AS_OF"
```

Apply a review response:

```bash
data-source-ranking apply-review fixtures/reviews/similar_client_use_directional.json
```

Run the Week 3 agent loop skeleton:

```bash
data-source-ranking run-agent fixtures/bundles/beta_needs_owner_validation.json --as-of "$AS_OF"
```

Apply an owner response and re-run the agent loop:

```bash
data-source-ranking run-agent fixtures/bundles/beta_needs_owner_validation.json --owner-response fixtures/owner_responses/beta_lina_validates_old_proposal.json
```

Apply simulated retrieval and re-run the agent loop:

```bash
data-source-ranking run-agent fixtures/bundles/gamma_blocked.json --simulated-retrieval fixtures/simulated_retrieval/gammahealth_retrieves_validated_context.json
```

Inspect a retrieval no-hit case that remains blocked:

```bash
data-source-ranking run-agent fixtures/bundles/gamma_blocked.json --simulated-retrieval fixtures/simulated_retrieval/gammahealth_no_retrieval_hit.json
```

Record feedback and inspect learned reliability defaults:

```bash
data-source-ranking feedback add fixtures/feedback/acme_handoff_accepted.json
data-source-ranking feedback snapshot
```

Use stored feedback during scoring:

```bash
data-source-ranking rank-source fixtures/strong/acme_recent_crm_note.json --feedback-store data/feedback_events.jsonl --json
data-source-ranking decide fixtures/bundles/acme_auto_handoff.json --feedback-store data/feedback_events.jsonl --json
data-source-ranking run-agent fixtures/bundles/acme_auto_handoff.json --feedback-store data/feedback_events.jsonl --json
```

Start the API foundation:

```bash
uvicorn api.main:app --reload
```

Then inspect:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/fixtures
curl http://127.0.0.1:8000/fixtures/bundles/acme_auto_handoff
```

Start the local UI:

```bash
cd ui
npm install
npm run dev
```

Print JSON for API or UI work:

```bash
data-source-ranking decide fixtures/bundles/acme_auto_handoff.json --json --as-of "$AS_OF"
data-source-ranking apply-review fixtures/reviews/unclear_owner_choose_owner.json --json
data-source-ranking run-agent fixtures/bundles/beta_needs_owner_validation.json --json --as-of "$AS_OF"
data-source-ranking run-agent fixtures/bundles/beta_needs_owner_validation.json --owner-response fixtures/owner_responses/beta_lina_validates_old_proposal.json --json
data-source-ranking run-agent fixtures/bundles/gamma_blocked.json --simulated-retrieval fixtures/simulated_retrieval/gammahealth_retrieves_validated_context.json --json
data-source-ranking feedback snapshot --json
```

## Decision Demos

| Outcome | Command |
| --- | --- |
| `auto_handoff` | `data-source-ranking decide fixtures/bundles/acme_auto_handoff.json --as-of "$AS_OF"` |
| `generate_context_request` | `data-source-ranking decide fixtures/bundles/beta_needs_owner_validation.json --as-of "$AS_OF"` |
| `needs_user_review` | `data-source-ranking decide fixtures/bundles/delta_contradictory_sources.json --as-of "$AS_OF"` |
| `blocked` | `data-source-ranking decide fixtures/bundles/gamma_blocked.json --as-of "$AS_OF"` |

## Review Demos

| Review Flow | Command |
| --- | --- |
| Use similar-client evidence as directional context | `data-source-ranking apply-review fixtures/reviews/similar_client_use_directional.json` |
| Skip similar-client evidence and block | `data-source-ranking apply-review fixtures/reviews/similar_client_skip_source.json --json` |
| Choose an owner for validation | `data-source-ranking apply-review fixtures/reviews/unclear_owner_choose_owner.json --json` |
| Accept owner-unvalidated use | `data-source-ranking apply-review fixtures/reviews/unclear_owner_use_without_owner.json --show-metadata` |
| Exclude sensitive overlapping evidence | `data-source-ranking apply-review fixtures/reviews/sensitive_overlap_exclude_source.json --json` |
| Request validation for sensitive partner material | `data-source-ranking apply-review fixtures/reviews/sensitive_partner_request_validation.json --json` |
| Remove an unsupported claim | `data-source-ranking apply-review fixtures/reviews/unsupported_claim_remove.json --json` |
| Use old proposal context as historical | `data-source-ranking apply-review fixtures/reviews/old_proposal_use_historical_context.json --show-metadata` |

## Command Reference

### `validate-fixtures`

Checks source, bundle, review, owner-response, simulated-retrieval, and feedback fixture JSON files.

```bash
data-source-ranking validate-fixtures fixtures
```

### `rank-source`

Scores one source against a context need and assigns a source tier.

```bash
data-source-ranking rank-source fixtures/weak/gammahealth_vague_crm_note.json --as-of "$AS_OF"
```

Add `--show-metadata` to inspect scoring metadata, or `--feedback-store` to apply feedback-derived reliability defaults.

### `rank-bundle`

Ranks each source in a bundle and returns the evidence-layer decision.

```bash
data-source-ranking rank-bundle fixtures/bundles/gamma_blocked.json --as-of "$AS_OF"
```

### `decide`

Ranks a bundle, evaluates policy gates, selects the final automation decision, and prints the next action.

```bash
data-source-ranking decide fixtures/bundles/betaworks_old_proposal_review.json --as-of "$AS_OF"
```

The decision output can include selected claims, selected sources, source citations, context requests, approval prompts, draft handoff text, blocked-output details, weak points, and audit events.
Use `--feedback-store` to apply conservative learned reliability defaults inside the embedded ranked bundle.

### `apply-review`

Loads a review fixture, runs the referenced bundle through `decide`, applies the prompt response, and prints accepted effects plus the updated decision state.

```bash
data-source-ranking apply-review fixtures/reviews/similar_client_use_directional.json
```

Use `--json` when tests, API code, or UI code need the full structured payload.

### `run-agent`

Runs the bounded deterministic agent loop for a bundle.

```bash
data-source-ranking run-agent fixtures/bundles/beta_needs_owner_validation.json --as-of "$AS_OF"
```

The loop records selected actions, stop reasons, and audit events. Use `--owner-response` to apply owner validation, `--simulated-retrieval` to add fixture-backed retrieved sources, `--feedback-store` to apply and audit conservative learned reliability defaults, `--max-iterations` to exercise the guardrail contract, and `--json` to inspect the full `AgentRunResult`.

### `feedback`

Appends fixture-backed feedback events and builds conservative reliability snapshots from the local JSONL store.

```bash
data-source-ranking feedback add fixtures/feedback/acme_handoff_accepted.json
data-source-ranking feedback snapshot
```

Use `--store-path` for isolated demos or tests, and `--json` to inspect the full `FeedbackEvent` or `ReliabilitySnapshot` payload.

### API

The API foundation is available at `api.main:app`.

```bash
uvicorn api.main:app --reload
```

Initial endpoints:

- `GET /health`
- `GET /fixtures`
- `GET /fixtures/{fixture_id}`
- `POST /rank`
- `POST /decide`
- `POST /run-agent`
- `POST /runs/decide`
- `POST /runs/agent`
- `GET /runs`
- `GET /runs/{run_id}`
- `POST /apply-review`
- `POST /runs/{run_id}/review`
- `POST /runs/{run_id}/feedback`
- `POST /feedback`
- `GET /feedback/snapshot`

Fixture IDs are relative fixture paths without `.json`, such as `bundles/acme_auto_handoff`.
Use `GET /fixtures?kind=bundle` to filter by fixture kind, and `GET /fixtures?grouped=true` when the UI needs pre-grouped fixture lists with counts.
Run history is API-owned: `POST /runs/decide` and `POST /runs/agent` persist product-shaped run records, while `GET /runs` and `GET /runs/{run_id}` support UI history views.
Review application supports both deterministic fixtures and product-style local review submissions: `POST /apply-review` applies a review fixture, while `POST /runs/{run_id}/review` accepts inline prompt choices such as `selected_choice_id`, `selected_owner_id`, `selected_owner_name`, `user_accepts_risk`, and `notes`. Inline review submissions are stored as append-only review events and returned on run detail responses as `review_events`.
Feedback recording is API-owned: `POST /feedback` accepts a feedback fixture id for deterministic demos, while `POST /runs/{run_id}/feedback` records structured UI feedback against a persisted run and returns the updated reliability snapshot. `GET /feedback/snapshot` reads the API-managed local feedback store without exposing storage paths in UI-facing requests.

The UI workflow should use the product endpoints in this order:

```text
POST /runs/decide
POST /runs/{run_id}/review
POST /runs/{run_id}/feedback
GET /runs/{run_id}
GET /feedback/snapshot
```

## Docs

- [Fixture conventions and scenario index](fixtures/README.md)
- [Decision policy contract](docs/decision_policy.md)
- [Prompt and review-response examples](docs/prompt_examples.md)
- [Week 2 implementation notes](notes.md)

## Verification

```bash
pytest
ruff check .
python -m compileall src evals
python -m data_source_ranking.cli validate-fixtures fixtures
```

## Current Limits

- Fixtures use normalized synthetic data, not raw CRM, Drive, Calendar, proposal, or partner-system exports.
- Fixtures include hand-written claims.
- Scoring, tiering, and policy gates use deterministic rules.
- Historical reliability can accept conservative feedback-derived source-type and source-system overrides.
- The system detects sensitive evidence overlap, but it does not compare claim meaning for semantic contradictions yet.
- Review-response transitions apply prompt answers to the current decision state. They do not run a full recompute.
- The `run-agent` command uses deterministic loop actions rather than live LLM tool execution.
- `run-agent` accepts either owner response or simulated retrieval in one run, not both yet.
- A polished presentation UI remains Week 3 work.
