# Data Source Ranking

Prototype for ranking retrieved context by evidence quality before using it in automated email workflows.

## Day 1 Scope

The initial implementation defines the typed schema contract and fixture loader. Scoring, tiering, automation decisions, agent loops, and UI are intentionally added later.

## Planned Setup

```bash
uv sync --extra dev
pytest
```

If `uv` is not installed locally, create a Python 3.12 virtual environment and install the dependencies from `pyproject.toml`.

