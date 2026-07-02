from __future__ import annotations

import os
from pathlib import Path

API_FIXTURE_ROOT = Path(os.environ.get("API_FIXTURE_ROOT", "fixtures"))
API_FEEDBACK_STORE_PATH = Path(
    os.environ.get("API_FEEDBACK_STORE_PATH", "data/feedback_events.jsonl")
)
API_RUN_STORE_PATH = Path(os.environ.get("API_RUN_STORE_PATH", "data/api_runs.jsonl"))
API_RUN_REVIEW_STORE_PATH = Path(
    os.environ.get("API_RUN_REVIEW_STORE_PATH", "data/api_run_reviews.jsonl")
)
