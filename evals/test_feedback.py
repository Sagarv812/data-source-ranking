from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from data_source_ranking.feedback import (
    DecisionOutcome,
    FeedbackEvent,
    FeedbackStoreError,
    SourceOutcome,
    SourceOutcomeStatus,
    append_feedback_event,
    build_reliability_snapshot,
    load_feedback_events,
)
from data_source_ranking.models import DecisionType, SourceSystem, SourceType


def feedback_event(event_id: str = "feedback_acme_001") -> FeedbackEvent:
    return FeedbackEvent(
        id=event_id,
        created_at=datetime(2026, 6, 21, 10, 0, 0),
        bundle_id="bundle_acme_auto_handoff",
        decision=DecisionType.AUTO_HANDOFF,
        decision_outcome=DecisionOutcome.ACCEPTED,
        selected_source_ids=["src_acme_recent_crm_note"],
        source_outcomes=[
            SourceOutcome(
                source_id="src_acme_recent_crm_note",
                source_type=SourceType.CRM_NOTE,
                source_system=SourceSystem.SALESFORCE,
                outcome=SourceOutcomeStatus.ACCEPTED,
                reason="Generated handoff context was accepted.",
            )
        ],
        generated_handoff_accepted=True,
    )


def source_outcome(
    source_id: str,
    outcome: SourceOutcomeStatus,
    source_type: SourceType = SourceType.CRM_NOTE,
    source_system: SourceSystem = SourceSystem.SALESFORCE,
) -> SourceOutcome:
    return SourceOutcome(
        source_id=source_id,
        source_type=source_type,
        source_system=source_system,
        outcome=outcome,
        reason=f"{outcome.value} in fixture feedback.",
    )


def feedback_with_outcomes(
    event_id: str,
    outcomes: list[SourceOutcome],
) -> FeedbackEvent:
    return FeedbackEvent(
        id=event_id,
        created_at=datetime(2026, 6, 21, 10, 0, 0),
        bundle_id="bundle_feedback",
        decision=DecisionType.AUTO_HANDOFF,
        decision_outcome=DecisionOutcome.ACCEPTED,
        selected_source_ids=[
            outcome.source_id
            for outcome in outcomes
            if outcome.outcome is SourceOutcomeStatus.ACCEPTED
        ],
        rejected_source_ids=[
            outcome.source_id
            for outcome in outcomes
            if outcome.outcome in {
                SourceOutcomeStatus.REJECTED,
                SourceOutcomeStatus.CORRECTED,
            }
        ],
        source_outcomes=outcomes,
    )


def test_feedback_event_serializes_with_nested_source_outcomes() -> None:
    payload = feedback_event().model_dump(mode="json")

    assert payload["id"] == "feedback_acme_001"
    assert payload["created_at"] == "2026-06-21T10:00:00"
    assert payload["decision"] == "auto_handoff"
    assert payload["decision_outcome"] == "accepted"
    assert payload["selected_source_ids"] == ["src_acme_recent_crm_note"]
    assert payload["source_outcomes"][0] == {
        "source_id": "src_acme_recent_crm_note",
        "source_type": "crm_note",
        "source_system": "salesforce",
        "outcome": "accepted",
        "reason": "Generated handoff context was accepted.",
        "metadata": {},
    }
    assert payload["generated_handoff_accepted"] is True


def test_feedback_event_requires_selected_sources_to_have_source_outcomes() -> None:
    with pytest.raises(ValidationError, match="feedback source ids"):
        FeedbackEvent(
            id="feedback_missing_source_outcome",
            created_at=datetime(2026, 6, 21, 10, 0, 0),
            bundle_id="bundle_acme_auto_handoff",
            decision=DecisionType.AUTO_HANDOFF,
            decision_outcome=DecisionOutcome.ACCEPTED,
            selected_source_ids=["src_missing"],
            source_outcomes=[],
        )


def test_feedback_event_rejects_unknown_fields() -> None:
    payload = feedback_event().model_dump(mode="json")
    payload["unknown"] = "not allowed"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        FeedbackEvent.model_validate(payload)


def test_load_feedback_events_returns_empty_list_for_missing_store(tmp_path: Path) -> None:
    assert load_feedback_events(tmp_path / "missing.jsonl") == []


def test_append_and_load_feedback_events_round_trip_jsonl(tmp_path: Path) -> None:
    store_path = tmp_path / "feedback" / "events.jsonl"
    first = feedback_event("feedback_acme_001")
    second = feedback_event("feedback_acme_002").model_copy(
        update={"decision_outcome": DecisionOutcome.CORRECTED, "correction_notes": "Wrong angle."}
    )

    append_feedback_event(first, store_path)
    append_feedback_event(second, store_path)

    raw_lines = store_path.read_text(encoding="utf-8").splitlines()
    assert len(raw_lines) == 2
    assert json.loads(raw_lines[0])["id"] == "feedback_acme_001"
    assert load_feedback_events(store_path) == [first, second]


def test_load_feedback_events_skips_blank_lines(tmp_path: Path) -> None:
    store_path = tmp_path / "feedback.jsonl"
    store_path.write_text(
        "\n" + json.dumps(feedback_event().model_dump(mode="json")) + "\n\n",
        encoding="utf-8",
    )

    assert load_feedback_events(store_path) == [feedback_event()]


def test_load_feedback_events_raises_for_malformed_jsonl(tmp_path: Path) -> None:
    store_path = tmp_path / "feedback.jsonl"
    store_path.write_text("{not json}\n", encoding="utf-8")

    with pytest.raises(FeedbackStoreError, match="line 1"):
        load_feedback_events(store_path)


def test_build_reliability_snapshot_learns_source_type_and_system_overrides() -> None:
    snapshot = build_reliability_snapshot(
        [
            feedback_with_outcomes(
                "feedback_learning_001",
                [
                    source_outcome("src_crm_accepted", SourceOutcomeStatus.ACCEPTED),
                    source_outcome("src_crm_rejected", SourceOutcomeStatus.REJECTED),
                    source_outcome("src_crm_corrected", SourceOutcomeStatus.CORRECTED),
                ],
            )
        ]
    )
    updates = {update.key: update for update in snapshot.updates}

    assert snapshot.reliability_defaults == {
        "source_type:crm_note": 0.71,
        "source_system:salesforce": 0.01,
    }
    assert updates["source_type:crm_note"].accepted_count == 1
    assert updates["source_type:crm_note"].rejected_count == 1
    assert updates["source_type:crm_note"].corrected_count == 1
    assert updates["source_type:crm_note"].delta == -0.07
    assert updates["source_system:salesforce"].delta == -0.03
    assert snapshot.metadata == {
        "feedback_event_count": 1,
        "source_outcome_count": 3,
        "source_type_group_count": 1,
        "source_system_group_count": 1,
        "policy": "conservative_feedback_v1",
    }


def test_build_reliability_snapshot_ignores_unused_and_unknown_for_defaults() -> None:
    snapshot = build_reliability_snapshot(
        [
            feedback_with_outcomes(
                "feedback_learning_002",
                [
                    source_outcome("src_unused", SourceOutcomeStatus.UNUSED),
                    source_outcome("src_unknown", SourceOutcomeStatus.UNKNOWN),
                ],
            )
        ]
    )
    updates = {update.key: update for update in snapshot.updates}

    assert snapshot.reliability_defaults == {}
    assert updates["source_type:crm_note"].unused_count == 1
    assert updates["source_type:crm_note"].unknown_count == 1
    assert updates["source_type:crm_note"].learned_value == 0.78
    assert updates["source_system:salesforce"].learned_value == 0.04


def test_build_reliability_snapshot_caps_source_type_and_system_learning() -> None:
    accepted_human_outcomes = [
        source_outcome(
            f"src_human_{index}",
            SourceOutcomeStatus.ACCEPTED,
            source_type=SourceType.HUMAN_VALIDATED_CONTEXT,
            source_system=SourceSystem.HUMAN,
        )
        for index in range(10)
    ]
    rejected_partner_outcomes = [
        source_outcome(
            f"src_partner_{index}",
            SourceOutcomeStatus.REJECTED,
            source_type=SourceType.PARTNER_MATERIAL,
            source_system=SourceSystem.PARTNER_PORTAL,
        )
        for index in range(10)
    ]
    snapshot = build_reliability_snapshot(
        [
            feedback_with_outcomes("feedback_learning_003", accepted_human_outcomes),
            feedback_with_outcomes("feedback_learning_004", rejected_partner_outcomes),
        ]
    )
    updates = {update.key: update for update in snapshot.updates}

    assert updates["source_type:human_validated_context"].learned_value == 0.9
    assert "source_type:human_validated_context" not in snapshot.reliability_defaults
    assert snapshot.reliability_defaults["source_system:human"] == 0.08
    assert snapshot.reliability_defaults["source_type:partner_material"] == 0.3
    assert snapshot.reliability_defaults["source_system:partner_portal"] == -0.12
