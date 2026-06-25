from __future__ import annotations

from datetime import date

from data_source_ranking.loader import load_source_fixture
from data_source_ranking.models import (
    ContextNeed,
    NeededClaim,
    Source,
    SourceType,
    ValidationRecord,
    WeakPointType,
)
from data_source_ranking.scoring import FreshnessScorer, ScoringContext

AS_OF = date(2026, 6, 21)


def score_fixture(path: str):
    fixture = load_source_fixture(path)
    return FreshnessScorer().score(
        ScoringContext(
            context_need=fixture.context_need,
            source=fixture.source,
            as_of=AS_OF,
        )
    )


def minimal_context_need() -> ContextNeed:
    return ContextNeed(
        id="need_test",
        client_id="client_test",
        email_goal="Prepare context.",
        needed_claims=[
            NeededClaim(
                id="need_claim_test",
                description="Test claim.",
            )
        ],
    )


def test_recent_source_scores_current_or_very_recent() -> None:
    score = score_fixture("fixtures/strong/acme_recent_meeting_notes_clear_attendees.json")

    assert score.score >= 0.9
    assert score.label in {"current", "very_recent"}
    assert score.weak_points == []
    assert score.metadata["age_days"] == 8


def test_old_source_gets_stale_weak_point() -> None:
    score = score_fixture("fixtures/weak/betaworks_stale_account_context.json")

    assert score.score == 0.15
    assert score.label == "stale"
    assert [point.type for point in score.weak_points] == [WeakPointType.STALE_SOURCE]


def test_validation_history_refreshes_source_date() -> None:
    source = Source(
        id="src_validated_old_doc",
        type=SourceType.PROPOSAL,
        title="Validated old proposal",
        summary="Old proposal revalidated by owner.",
        created_at=date(2024, 1, 1),
        updated_at=date(2024, 1, 2),
        validation_history=[
            ValidationRecord(
                validated_at=date(2026, 6, 20),
                outcome="accepted",
            )
        ],
    )

    score = FreshnessScorer().score(
        ScoringContext(
            context_need=minimal_context_need(),
            source=source,
            as_of=AS_OF,
        )
    )

    assert score.score == 1.0
    assert score.label == "current"
    assert score.metadata["source_date"] == "2026-06-20"
    assert score.metadata["age_days"] == 1


def test_missing_date_scores_unknown() -> None:
    source = Source(
        id="src_missing_date",
        type=SourceType.CRM_NOTE,
        title="Missing date note",
        summary="Useful-looking note with no timestamp.",
    )

    score = FreshnessScorer().score(
        ScoringContext(
            context_need=minimal_context_need(),
            source=source,
            as_of=AS_OF,
        )
    )

    assert score.score == 0.0
    assert score.label == "unknown"
    assert [point.type for point in score.weak_points] == [WeakPointType.MISSING_DATE]


def test_future_dated_source_is_suspicious() -> None:
    source = Source(
        id="src_future_date",
        type=SourceType.CRM_NOTE,
        title="Future dated note",
        summary="Note with impossible future date.",
        updated_at=date(2026, 7, 1),
    )

    score = FreshnessScorer().score(
        ScoringContext(
            context_need=minimal_context_need(),
            source=source,
            as_of=AS_OF,
        )
    )

    assert score.score == 0.4
    assert score.label == "future_dated"
    assert [point.type for point in score.weak_points] == [WeakPointType.MISSING_DATE]

