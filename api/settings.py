from __future__ import annotations

import os
from pathlib import Path

API_FIXTURE_ROOT = Path(os.environ.get("API_FIXTURE_ROOT", "fixtures"))
API_CORS_ALLOW_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "API_CORS_ALLOW_ORIGINS",
        ",".join(
            [
                "http://localhost:5173",
                "http://localhost:5174",
                "http://localhost:4173",
                "http://localhost:4174",
                "http://127.0.0.1:5173",
                "http://127.0.0.1:5174",
                "http://127.0.0.1:4173",
                "http://127.0.0.1:4174",
            ]
        ),
    ).split(",")
    if origin.strip()
]
API_FEEDBACK_STORE_PATH = Path(
    os.environ.get("API_FEEDBACK_STORE_PATH", "data/feedback_events.jsonl")
)
API_RUN_STORE_PATH = Path(os.environ.get("API_RUN_STORE_PATH", "data/api_runs.jsonl"))
API_RUN_REVIEW_STORE_PATH = Path(
    os.environ.get("API_RUN_REVIEW_STORE_PATH", "data/api_run_reviews.jsonl")
)
API_PRODUCT_STORE_BACKEND = os.environ.get("API_PRODUCT_STORE_BACKEND", "local_jsonl")
API_DYNAMODB_RUN_TABLE = os.environ.get("API_DYNAMODB_RUN_TABLE")
API_DYNAMODB_REVIEW_EVENT_TABLE = os.environ.get("API_DYNAMODB_REVIEW_EVENT_TABLE")
API_DYNAMODB_FEEDBACK_TABLE = os.environ.get("API_DYNAMODB_FEEDBACK_TABLE")
AWS_REGION = os.environ.get("AWS_REGION")
