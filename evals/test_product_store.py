from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import api.main
import pytest
from api.product_store import DynamoDbProductStore, LocalJsonlProductStore
from api.run_store import ApiRunKind, create_run_record, create_run_review_event
from fastapi import HTTPException

from data_source_ranking.loader import load_feedback_fixture


class FakeDynamoDbTable:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}

    def put_item(self, **kwargs: Any) -> None:
        item = kwargs["Item"]
        self.items[item["id"]] = item

    def scan(self, **kwargs: Any) -> dict[str, Any]:
        return {"Items": list(self.items.values())}

    def delete_item(self, **kwargs: Any) -> None:
        self.items.pop(kwargs["Key"]["id"], None)


def test_local_jsonl_product_store_round_trips_and_resets(tmp_path: Path) -> None:
    store = LocalJsonlProductStore(
        run_store_path=tmp_path / "api_runs.jsonl",
        run_review_store_path=tmp_path / "api_run_reviews.jsonl",
        feedback_store_path=tmp_path / "feedback_events.jsonl",
    )
    run = create_run_record(
        kind=ApiRunKind.DECISION,
        bundle_id="bundle_acme_auto_handoff",
        fixture_id="bundles/acme_auto_handoff",
        request={"fixture_id": "bundles/acme_auto_handoff"},
        result={"decision": "auto_handoff"},
    )
    review_event = create_run_review_event(
        run_id=run.run_id,
        bundle_id=run.bundle_id,
        fixture_id=run.fixture_id,
        request={"selected_choice_id": "use_directional_with_label"},
        result={"accepted": True},
    )
    feedback_event = load_feedback_fixture(
        Path("fixtures/feedback/acme_handoff_accepted.json")
    ).event

    assert store.append_run(run) == run
    assert store.append_review_event(review_event) == review_event
    assert store.append_feedback(feedback_event) == feedback_event

    assert store.load_runs() == [run]
    assert store.load_review_events() == [review_event]
    assert store.load_feedback() == [feedback_event]
    assert store.reset(["runs", "reviews", "feedback"]) == {
        "runs": 1,
        "reviews": 1,
        "feedback": 1,
    }
    assert store.load_runs() == []
    assert store.load_review_events() == []
    assert store.load_feedback() == []


def test_dynamodb_product_store_round_trips_and_resets() -> None:
    run_table = FakeDynamoDbTable()
    review_table = FakeDynamoDbTable()
    feedback_table = FakeDynamoDbTable()
    store = DynamoDbProductStore(
        run_table=run_table,
        review_event_table=review_table,
        feedback_table=feedback_table,
    )
    run = create_run_record(
        kind=ApiRunKind.DECISION,
        bundle_id="bundle_acme_auto_handoff",
        fixture_id="bundles/acme_auto_handoff",
        request={"fixture_id": "bundles/acme_auto_handoff"},
        result={"decision": "auto_handoff", "confidence": {"score": 0.9}},
    )
    review_event = create_run_review_event(
        run_id=run.run_id,
        bundle_id=run.bundle_id,
        fixture_id=run.fixture_id,
        request={"selected_choice_id": "use_directional_with_label"},
        result={"accepted": True},
    )
    feedback_event = load_feedback_fixture(
        Path("fixtures/feedback/acme_handoff_accepted.json")
    ).event

    assert store.append_run(run) == run
    assert store.append_review_event(review_event) == review_event
    assert store.append_feedback(feedback_event) == feedback_event
    assert run_table.items[run.run_id]["payload"]["result"]["confidence"]["score"] == Decimal(
        "0.9"
    )

    assert store.load_runs() == [run]
    assert store.load_review_events() == [review_event]
    assert store.load_feedback() == [feedback_event]
    assert store.reset(["runs", "reviews", "feedback"]) == {
        "runs": 1,
        "reviews": 1,
        "feedback": 1,
    }
    assert store.load_runs() == []
    assert store.load_review_events() == []
    assert store.load_feedback() == []


def test_api_product_store_uses_dynamodb_table_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str | None] = {}
    fake_store = object()

    def fake_from_table_names(
        run_table_name: str,
        review_event_table_name: str,
        feedback_table_name: str,
        region_name: str | None = None,
    ) -> object:
        captured.update(
            {
                "run_table_name": run_table_name,
                "review_event_table_name": review_event_table_name,
                "feedback_table_name": feedback_table_name,
                "region_name": region_name,
            }
        )
        return fake_store

    monkeypatch.setattr(api.main, "API_PRODUCT_STORE_BACKEND", "dynamodb")
    monkeypatch.setattr(api.main, "API_DYNAMODB_RUN_TABLE", "runs-table")
    monkeypatch.setattr(api.main, "API_DYNAMODB_REVIEW_EVENT_TABLE", "reviews-table")
    monkeypatch.setattr(api.main, "API_DYNAMODB_FEEDBACK_TABLE", "feedback-table")
    monkeypatch.setattr(api.main, "AWS_REGION", "us-east-1")
    monkeypatch.setattr(
        api.main.DynamoDbProductStore,
        "from_table_names",
        staticmethod(fake_from_table_names),
    )

    assert api.main._product_store() is fake_store
    assert captured == {
        "run_table_name": "runs-table",
        "review_event_table_name": "reviews-table",
        "feedback_table_name": "feedback-table",
        "region_name": "us-east-1",
    }


def test_api_product_store_requires_dynamodb_table_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api.main, "API_PRODUCT_STORE_BACKEND", "dynamodb")
    monkeypatch.setattr(api.main, "API_DYNAMODB_RUN_TABLE", "runs-table")
    monkeypatch.setattr(api.main, "API_DYNAMODB_REVIEW_EVENT_TABLE", None)
    monkeypatch.setattr(api.main, "API_DYNAMODB_FEEDBACK_TABLE", None)

    with pytest.raises(HTTPException) as exc_info:
        api.main._product_store()

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == (
        "DynamoDB product store is missing table configuration for: reviews, feedback"
    )
