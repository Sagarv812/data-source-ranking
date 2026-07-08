from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from api.run_store import (
    ApiRunRecord,
    ApiRunReviewEvent,
    RunStoreError,
    append_run_record,
    append_run_review_event,
    load_run_records,
    load_run_review_events,
)
from data_source_ranking.feedback import (
    FeedbackEvent,
    FeedbackStoreError,
    append_feedback_event,
    load_feedback_events,
)


class ProductStore(Protocol):
    def append_run(self, record: ApiRunRecord) -> ApiRunRecord: ...

    def load_runs(self) -> list[ApiRunRecord]: ...

    def append_review_event(self, event: ApiRunReviewEvent) -> ApiRunReviewEvent: ...

    def load_review_events(self) -> list[ApiRunReviewEvent]: ...

    def append_feedback(self, event: FeedbackEvent) -> FeedbackEvent: ...

    def load_feedback(self) -> list[FeedbackEvent]: ...

    def reset(self, scopes: list[str]) -> dict[str, int]: ...


class LocalJsonlProductStore:
    def __init__(
        self,
        run_store_path: str | Path,
        run_review_store_path: str | Path,
        feedback_store_path: str | Path,
    ) -> None:
        self.run_store_path = Path(run_store_path)
        self.run_review_store_path = Path(run_review_store_path)
        self.feedback_store_path = Path(feedback_store_path)

    def append_run(self, record: ApiRunRecord) -> ApiRunRecord:
        return append_run_record(record, self.run_store_path)

    def load_runs(self) -> list[ApiRunRecord]:
        return load_run_records(self.run_store_path)

    def append_review_event(self, event: ApiRunReviewEvent) -> ApiRunReviewEvent:
        return append_run_review_event(event, self.run_review_store_path)

    def load_review_events(self) -> list[ApiRunReviewEvent]:
        return load_run_review_events(self.run_review_store_path)

    def append_feedback(self, event: FeedbackEvent) -> FeedbackEvent:
        return append_feedback_event(event, self.feedback_store_path)

    def load_feedback(self) -> list[FeedbackEvent]:
        return load_feedback_events(self.feedback_store_path)

    def reset(self, scopes: list[str]) -> dict[str, int]:
        return {scope: _reset_store(self._path_for_scope(scope)) for scope in scopes}

    def _path_for_scope(self, scope: str) -> Path:
        if scope == "runs":
            return self.run_store_path
        if scope == "reviews":
            return self.run_review_store_path
        if scope == "feedback":
            return self.feedback_store_path
        raise ValueError(f"unknown product store scope: {scope}")


def _reset_store(path: Path) -> int:
    if not path.exists():
        return 0
    count = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    path.unlink()
    return count


class DynamoDbTable(Protocol):
    def put_item(self, **kwargs: Any) -> Any: ...

    def scan(self, **kwargs: Any) -> dict[str, Any]: ...

    def delete_item(self, **kwargs: Any) -> Any: ...


class DynamoDbResource(Protocol):
    def Table(self, name: str) -> DynamoDbTable: ...


class DynamoDbProductStore:
    def __init__(
        self,
        run_table: DynamoDbTable,
        review_event_table: DynamoDbTable,
        feedback_table: DynamoDbTable,
    ) -> None:
        self.run_table = run_table
        self.review_event_table = review_event_table
        self.feedback_table = feedback_table

    @classmethod
    def from_table_names(
        cls,
        run_table_name: str,
        review_event_table_name: str,
        feedback_table_name: str,
        region_name: str | None = None,
        dynamodb_resource: DynamoDbResource | None = None,
    ) -> DynamoDbProductStore:
        resource = dynamodb_resource or _boto3_dynamodb_resource(region_name)
        return cls(
            run_table=resource.Table(run_table_name),
            review_event_table=resource.Table(review_event_table_name),
            feedback_table=resource.Table(feedback_table_name),
        )

    def append_run(self, record: ApiRunRecord) -> ApiRunRecord:
        _put_payload(
            self.run_table,
            item_id=record.run_id,
            payload=record.model_dump(mode="json", exclude={"review_events"}),
        )
        return record

    def load_runs(self) -> list[ApiRunRecord]:
        return sorted(
            _load_model_payloads(
                self.run_table,
                ApiRunRecord,
                error_cls=RunStoreError,
                item_label="run record",
            ),
            key=lambda record: record.created_at,
        )

    def append_review_event(self, event: ApiRunReviewEvent) -> ApiRunReviewEvent:
        _put_payload(
            self.review_event_table,
            item_id=event.review_event_id,
            payload=event.model_dump(mode="json"),
        )
        return event

    def load_review_events(self) -> list[ApiRunReviewEvent]:
        return sorted(
            _load_model_payloads(
                self.review_event_table,
                ApiRunReviewEvent,
                error_cls=RunStoreError,
                item_label="run review event",
            ),
            key=lambda event: event.created_at,
        )

    def append_feedback(self, event: FeedbackEvent) -> FeedbackEvent:
        _put_payload(
            self.feedback_table,
            item_id=event.id,
            payload=event.model_dump(mode="json"),
        )
        return event

    def load_feedback(self) -> list[FeedbackEvent]:
        return sorted(
            _load_model_payloads(
                self.feedback_table,
                FeedbackEvent,
                error_cls=FeedbackStoreError,
                item_label="feedback event",
            ),
            key=lambda event: event.created_at,
        )

    def reset(self, scopes: list[str]) -> dict[str, int]:
        return {scope: _delete_all(self._table_for_scope(scope)) for scope in scopes}

    def _table_for_scope(self, scope: str) -> DynamoDbTable:
        if scope == "runs":
            return self.run_table
        if scope == "reviews":
            return self.review_event_table
        if scope == "feedback":
            return self.feedback_table
        raise ValueError(f"unknown product store scope: {scope}")


def _boto3_dynamodb_resource(region_name: str | None) -> DynamoDbResource:
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError(
            "boto3 is required when API_PRODUCT_STORE_BACKEND=dynamodb."
        ) from exc
    if region_name:
        return boto3.resource("dynamodb", region_name=region_name)
    return boto3.resource("dynamodb")


def _put_payload(table: DynamoDbTable, item_id: str, payload: dict[str, Any]) -> None:
    table.put_item(
        Item={
            "id": item_id,
            "payload": _to_dynamodb_value(payload),
        }
    )


def _load_model_payloads(
    table: DynamoDbTable,
    model_type: type[Any],
    error_cls: type[ValueError],
    item_label: str,
) -> list[Any]:
    models: list[Any] = []
    for index, item in enumerate(_scan_all_items(table), 1):
        try:
            models.append(model_type.model_validate(_payload_from_item(item)))
        except ValueError as exc:
            raise error_cls(f"invalid {item_label} in DynamoDB item {index}: {exc}") from exc
    return models


def _payload_from_item(item: dict[str, Any]) -> dict[str, Any]:
    payload = item.get("payload")
    if isinstance(payload, dict):
        return _from_dynamodb_value(payload)
    return _from_dynamodb_value({key: value for key, value in item.items() if key != "id"})


def _scan_all_items(table: DynamoDbTable) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    scan_kwargs: dict[str, Any] = {}
    while True:
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return items
        scan_kwargs["ExclusiveStartKey"] = last_key


def _delete_all(table: DynamoDbTable) -> int:
    items = _scan_all_items(table)
    deleted_count = 0
    for item in items:
        item_id = item.get("id")
        if isinstance(item_id, str) and item_id:
            table.delete_item(Key={"id": item_id})
            deleted_count += 1
    return deleted_count


def _to_dynamodb_value(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: _to_dynamodb_value(nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [_to_dynamodb_value(item) for item in value]
    return value


def _from_dynamodb_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    if isinstance(value, dict):
        return {key: _from_dynamodb_value(nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [_from_dynamodb_value(item) for item in value]
    return value
