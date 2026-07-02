from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import Field

from data_source_ranking.models import StrictModel


class RunStoreError(ValueError):
    pass


class ApiRunKind(StrEnum):
    DECISION = "decision"
    AGENT = "agent"


class ApiRunReviewEvent(StrictModel):
    review_event_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    bundle_id: str = Field(min_length=1)
    fixture_id: str = Field(min_length=1)
    created_at: datetime
    request: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)


class ApiRunRecord(StrictModel):
    run_id: str = Field(min_length=1)
    kind: ApiRunKind
    bundle_id: str = Field(min_length=1)
    fixture_id: str = Field(min_length=1)
    created_at: datetime
    request: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    review_events: list[ApiRunReviewEvent] = Field(default_factory=list)


class ApiRunSummary(StrictModel):
    run_id: str = Field(min_length=1)
    kind: ApiRunKind
    bundle_id: str = Field(min_length=1)
    fixture_id: str = Field(min_length=1)
    created_at: datetime
    decision: str | None = None
    final_decision: str | None = None


class ApiRunListResponse(StrictModel):
    runs: list[ApiRunSummary] = Field(default_factory=list)


def create_run_record(
    kind: ApiRunKind,
    bundle_id: str,
    fixture_id: str,
    request: dict[str, Any],
    result: dict[str, Any],
) -> ApiRunRecord:
    return ApiRunRecord(
        run_id=f"run_{uuid4().hex}",
        kind=kind,
        bundle_id=bundle_id,
        fixture_id=fixture_id,
        created_at=datetime.now(UTC),
        request=request,
        result=result,
    )


def append_run_record(record: ApiRunRecord, path: str | Path) -> ApiRunRecord:
    store_path = Path(path)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    with store_path.open("a", encoding="utf-8") as store:
        store.write(
            json.dumps(
                record.model_dump(mode="json", exclude={"review_events"}),
                sort_keys=True,
            )
        )
        store.write("\n")
    return record


def create_run_review_event(
    run_id: str,
    bundle_id: str,
    fixture_id: str,
    request: dict[str, Any],
    result: dict[str, Any],
) -> ApiRunReviewEvent:
    return ApiRunReviewEvent(
        review_event_id=f"review_{uuid4().hex}",
        run_id=run_id,
        bundle_id=bundle_id,
        fixture_id=fixture_id,
        created_at=datetime.now(UTC),
        request=request,
        result=result,
    )


def append_run_review_event(
    event: ApiRunReviewEvent,
    path: str | Path,
) -> ApiRunReviewEvent:
    store_path = Path(path)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    with store_path.open("a", encoding="utf-8") as store:
        store.write(json.dumps(event.model_dump(mode="json"), sort_keys=True))
        store.write("\n")
    return event


def load_run_records(path: str | Path) -> list[ApiRunRecord]:
    store_path = Path(path)
    if not store_path.exists():
        return []

    records: list[ApiRunRecord] = []
    for line_number, line in enumerate(store_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(ApiRunRecord.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValueError) as exc:
            raise RunStoreError(
                f"invalid run record on line {line_number} of {store_path}: {exc}"
            ) from exc
    return records


def load_run_review_events(path: str | Path) -> list[ApiRunReviewEvent]:
    store_path = Path(path)
    if not store_path.exists():
        return []

    events: list[ApiRunReviewEvent] = []
    for line_number, line in enumerate(store_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            events.append(ApiRunReviewEvent.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValueError) as exc:
            raise RunStoreError(
                f"invalid run review event on line {line_number} of {store_path}: {exc}"
            ) from exc
    return events


def run_summary(record: ApiRunRecord) -> ApiRunSummary:
    return ApiRunSummary(
        run_id=record.run_id,
        kind=record.kind,
        bundle_id=record.bundle_id,
        fixture_id=record.fixture_id,
        created_at=record.created_at,
        decision=record.result.get("decision"),
        final_decision=(
            record.result.get("final_decision", {}).get("decision")
            if isinstance(record.result.get("final_decision"), dict)
            else None
        ),
    )
