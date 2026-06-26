# Data Source Ranking

Prototype for ranking retrieved context by evidence quality before using it in automated email workflows.

## What It Does

This project is an inspectable trust gate for retrieved business context. It scores sources against a specific context need, assigns a source tier, and combines multiple sources into an automation decision.

The current prototype supports:

- source ranking: `strong`, `medium`, or `weak`
- bundle decisions: `auto_handoff`, `generate_context_request`, `needs_user_review`, or `blocked`
- nine scoring dimensions with reasons, labels, weak points, and metadata
- synthetic fixture data for testing and demo runs
- JSON output for future UI/API integration

Source tiers describe the strength of an individual source as evidence. A strong source may still cover only part of a context need. Bundle decisions decide whether the overall set of sources is complete and safe enough for automation.

## Setup

```bash
uv sync --extra dev
```

If `uv` is not installed locally, create a Python 3.12 virtual environment and install the dependencies from `pyproject.toml`.

## Quickstart

Validate all fixture files:

```bash
data-source-ranking validate-fixtures fixtures
```

Rank one source fixture:

```bash
data-source-ranking rank-source fixtures/strong/acme_recent_crm_note.json --as-of 2026-06-21
```

Rank a bundle fixture:

```bash
data-source-ranking rank-bundle fixtures/bundles/acme_auto_handoff.json --as-of 2026-06-21
```

Print machine-readable JSON:

```bash
data-source-ranking rank-bundle fixtures/bundles/acme_auto_handoff.json --json --as-of 2026-06-21
```

Show deeper metadata in readable output:

```bash
data-source-ranking rank-source fixtures/strong/acme_recent_crm_note.json --show-metadata --as-of 2026-06-21
```

## Commands

### `validate-fixtures`

Checks that fixture JSON files match the schema and that bundle source references resolve correctly. This does not rank anything; it verifies the input data is usable.

```bash
data-source-ranking validate-fixtures fixtures
```

### `rank-source`

Loads a single source fixture, runs all scoring dimensions, assigns a tier, and prints the weak points.

```bash
data-source-ranking rank-source fixtures/weak/gammahealth_vague_crm_note.json --as-of 2026-06-21
```

### `rank-bundle`

Loads a bundle fixture, ranks each source with bundle-aware context, and returns the overall automation decision.

```bash
data-source-ranking rank-bundle fixtures/bundles/gamma_blocked.json --as-of 2026-06-21
```

Use `--json` when the output should be consumed by tests, a backend, or a future UI. Use `--as-of` to make freshness scoring explicit and repeatable. Use `--show-metadata` when readable output should include the supporting scoring details.

## Verification

```bash
pytest
ruff check .
python -m compileall src evals
```

## Current Limits

- Fixtures are synthetic and normalized, not raw CRM/Drive/Calendar exports.
- Claims are manually supplied in fixtures for now.
- Scoring and tiering are rule-based.
- Historical reliability uses static defaults until real feedback history exists.
- Semantic contradiction detection is not implemented yet; sensitive overlapping evidence is conservatively sent to review.
- The polished presentation UI is planned later, after the ranking core is stable.
