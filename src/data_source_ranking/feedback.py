from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from data_source_ranking.models import DecisionType, SourceSystem, SourceType, StrictModel
from data_source_ranking.scoring.reliability import (
    SOURCE_SYSTEM_MODIFIERS,
    SOURCE_TYPE_DEFAULTS,
)

DEFAULT_FEEDBACK_STORE_PATH = Path("data/feedback_events.jsonl")
SOURCE_TYPE_POSITIVE_DELTA = 0.03
SOURCE_TYPE_NEGATIVE_DELTA = -0.05
SOURCE_TYPE_MIN_RELIABILITY = 0.30
SOURCE_TYPE_MAX_RELIABILITY = 0.90
SOURCE_SYSTEM_POSITIVE_DELTA = 0.01
SOURCE_SYSTEM_NEGATIVE_DELTA = -0.02
SOURCE_SYSTEM_MIN_MODIFIER = -0.12
SOURCE_SYSTEM_MAX_MODIFIER = 0.08


class FeedbackStoreError(ValueError):
    pass


class DecisionOutcome(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CORRECTED = "corrected"
    BLOCKED_CONFIRMED = "blocked_confirmed"
    BLOCKED_OVERRIDDEN = "blocked_overridden"
    UNKNOWN = "unknown"


class SourceOutcomeStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CORRECTED = "corrected"
    UNUSED = "unused"
    UNKNOWN = "unknown"


class SourceOutcome(StrictModel):
    source_id: str = Field(min_length=1)
    source_type: SourceType
    source_system: SourceSystem
    outcome: SourceOutcomeStatus
    reason: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReliabilityUpdate(StrictModel):
    key: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    static_value: float
    learned_value: float
    delta: float
    accepted_count: int = 0
    rejected_count: int = 0
    corrected_count: int = 0
    unused_count: int = 0
    unknown_count: int = 0
    source_outcome_count: int = 0
    reasons: list[str] = Field(default_factory=list)


class ReliabilitySnapshot(StrictModel):
    reliability_defaults: dict[str, float] = Field(default_factory=dict)
    updates: list[ReliabilityUpdate] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FeedbackEvent(StrictModel):
    id: str = Field(min_length=1)
    created_at: datetime
    bundle_id: str = Field(min_length=1)
    decision: DecisionType
    decision_outcome: DecisionOutcome
    selected_source_ids: list[str] = Field(default_factory=list)
    rejected_source_ids: list[str] = Field(default_factory=list)
    source_outcomes: list[SourceOutcome] = Field(default_factory=list)
    user_approval_outcome: DecisionOutcome | None = None
    owner_response_outcome: str | None = None
    generated_handoff_accepted: bool | None = None
    correction_notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_referenced_sources_to_have_outcomes(self) -> FeedbackEvent:
        outcome_source_ids = {outcome.source_id for outcome in self.source_outcomes}
        missing_source_ids = sorted(
            {
                *self.selected_source_ids,
                *self.rejected_source_ids,
            }
            - outcome_source_ids
        )
        if missing_source_ids:
            raise ValueError(
                "feedback source ids must have matching source_outcomes: "
                + ", ".join(missing_source_ids)
            )
        return self


class FeedbackFixture(StrictModel):
    event: FeedbackEvent
    metadata: dict[str, Any] = Field(default_factory=dict)


def append_feedback_event(
    event: FeedbackEvent,
    path: str | Path = DEFAULT_FEEDBACK_STORE_PATH,
) -> FeedbackEvent:
    store_path = Path(path)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    with store_path.open("a", encoding="utf-8") as store:
        store.write(json.dumps(event.model_dump(mode="json"), sort_keys=True))
        store.write("\n")
    return event


def load_feedback_events(path: str | Path = DEFAULT_FEEDBACK_STORE_PATH) -> list[FeedbackEvent]:
    store_path = Path(path)
    if not store_path.exists():
        return []

    events: list[FeedbackEvent] = []
    for line_number, line in enumerate(store_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            events.append(FeedbackEvent.model_validate(payload))
        except (json.JSONDecodeError, ValueError) as exc:
            raise FeedbackStoreError(
                f"invalid feedback event on line {line_number} of {store_path}: {exc}"
            ) from exc
    return events


def build_reliability_snapshot(events: list[FeedbackEvent]) -> ReliabilitySnapshot:
    source_type_groups: dict[SourceType, list[SourceOutcome]] = {}
    source_system_groups: dict[SourceSystem, list[SourceOutcome]] = {}
    for event in events:
        for outcome in event.source_outcomes:
            source_type_groups.setdefault(outcome.source_type, []).append(outcome)
            source_system_groups.setdefault(outcome.source_system, []).append(outcome)

    updates: list[ReliabilityUpdate] = [
        *[
            _source_type_update(source_type, outcomes)
            for source_type, outcomes in sorted(
                source_type_groups.items(), key=lambda item: item[0].value
            )
        ],
        *[
            _source_system_update(source_system, outcomes)
            for source_system, outcomes in sorted(
                source_system_groups.items(), key=lambda item: item[0].value
            )
        ],
    ]
    reliability_defaults = {
        update.key: update.learned_value
        for update in updates
        if update.delta != 0
    }
    return ReliabilitySnapshot(
        reliability_defaults=reliability_defaults,
        updates=updates,
        metadata={
            "feedback_event_count": len(events),
            "source_outcome_count": sum(len(event.source_outcomes) for event in events),
            "source_type_group_count": len(source_type_groups),
            "source_system_group_count": len(source_system_groups),
            "policy": "conservative_feedback_v1",
        },
    )


def _source_type_update(
    source_type: SourceType,
    outcomes: list[SourceOutcome],
) -> ReliabilityUpdate:
    static_value = SOURCE_TYPE_DEFAULTS[source_type]
    delta = _feedback_delta(
        outcomes,
        positive_delta=SOURCE_TYPE_POSITIVE_DELTA,
        negative_delta=SOURCE_TYPE_NEGATIVE_DELTA,
    )
    learned_value = _clamp(
        round(static_value + delta, 2),
        SOURCE_TYPE_MIN_RELIABILITY,
        SOURCE_TYPE_MAX_RELIABILITY,
    )
    return _reliability_update(
        key=f"source_type:{source_type.value}",
        scope="source_type",
        static_value=static_value,
        learned_value=learned_value,
        outcomes=outcomes,
    )


def _source_system_update(
    source_system: SourceSystem,
    outcomes: list[SourceOutcome],
) -> ReliabilityUpdate:
    static_value = SOURCE_SYSTEM_MODIFIERS[source_system]
    delta = _feedback_delta(
        outcomes,
        positive_delta=SOURCE_SYSTEM_POSITIVE_DELTA,
        negative_delta=SOURCE_SYSTEM_NEGATIVE_DELTA,
    )
    learned_value = _clamp(
        round(static_value + delta, 2),
        SOURCE_SYSTEM_MIN_MODIFIER,
        SOURCE_SYSTEM_MAX_MODIFIER,
    )
    return _reliability_update(
        key=f"source_system:{source_system.value}",
        scope="source_system",
        static_value=static_value,
        learned_value=learned_value,
        outcomes=outcomes,
    )


def _reliability_update(
    key: str,
    scope: str,
    static_value: float,
    learned_value: float,
    outcomes: list[SourceOutcome],
) -> ReliabilityUpdate:
    accepted_count = _outcome_count(outcomes, SourceOutcomeStatus.ACCEPTED)
    rejected_count = _outcome_count(outcomes, SourceOutcomeStatus.REJECTED)
    corrected_count = _outcome_count(outcomes, SourceOutcomeStatus.CORRECTED)
    unused_count = _outcome_count(outcomes, SourceOutcomeStatus.UNUSED)
    unknown_count = _outcome_count(outcomes, SourceOutcomeStatus.UNKNOWN)
    return ReliabilityUpdate(
        key=key,
        scope=scope,
        static_value=static_value,
        learned_value=learned_value,
        delta=round(learned_value - static_value, 2),
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        corrected_count=corrected_count,
        unused_count=unused_count,
        unknown_count=unknown_count,
        source_outcome_count=len(outcomes),
        reasons=_reliability_reasons(
            accepted_count,
            rejected_count,
            corrected_count,
            unused_count,
            unknown_count,
        ),
    )


def _feedback_delta(
    outcomes: list[SourceOutcome],
    positive_delta: float,
    negative_delta: float,
) -> float:
    return round(
        _outcome_count(outcomes, SourceOutcomeStatus.ACCEPTED) * positive_delta
        + (
            _outcome_count(outcomes, SourceOutcomeStatus.REJECTED)
            + _outcome_count(outcomes, SourceOutcomeStatus.CORRECTED)
        )
        * negative_delta,
        2,
    )


def _outcome_count(
    outcomes: list[SourceOutcome],
    status: SourceOutcomeStatus,
) -> int:
    return sum(outcome.outcome is status for outcome in outcomes)


def _reliability_reasons(
    accepted_count: int,
    rejected_count: int,
    corrected_count: int,
    unused_count: int,
    unknown_count: int,
) -> list[str]:
    reasons: list[str] = []
    if accepted_count:
        reasons.append(f"{accepted_count} accepted source outcome(s)")
    if rejected_count:
        reasons.append(f"{rejected_count} rejected source outcome(s)")
    if corrected_count:
        reasons.append(f"{corrected_count} corrected source outcome(s)")
    if unused_count:
        reasons.append(f"{unused_count} unused source outcome(s)")
    if unknown_count:
        reasons.append(f"{unknown_count} unknown source outcome(s)")
    return reasons


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))
