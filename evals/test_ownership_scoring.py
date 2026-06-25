from __future__ import annotations

from data_source_ranking.loader import load_source_fixture
from data_source_ranking.models import (
    ContextNeed,
    NeededClaim,
    Person,
    PersonRole,
    Source,
    SourceType,
    WeakPointType,
)
from data_source_ranking.scoring import OwnershipSignalScorer, ScoringContext


def score_fixture(path: str):
    fixture = load_source_fixture(path)
    return OwnershipSignalScorer().score(
        ScoringContext(
            context_need=fixture.context_need,
            source=fixture.source,
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


def test_clear_owner_candidate_scores_highest() -> None:
    score = score_fixture("fixtures/strong/gammahealth_human_validated_context.json")

    assert score.score == 1.0
    assert score.label == "clear"
    assert score.weak_points == []
    assert score.metadata["best_owner"]["person_id"] == "user_priya"


def test_multiple_good_owner_signals_are_recognized() -> None:
    score = score_fixture("fixtures/strong/deltabank_recent_meeting_notes_clear_attendees.json")

    assert score.score == 0.88
    assert score.label == "multiple_good"
    assert score.weak_points == []
    assert score.metadata["best_owner"]["person_id"] == "user_jordan"


def test_unclear_owner_gets_weak_point() -> None:
    score = score_fixture("fixtures/medium/gammahealth_useful_document_unclear_owner.json")

    assert score.score == 0.55
    assert score.label == "unclear"
    assert [point.type for point in score.weak_points] == [WeakPointType.UNCLEAR_OWNER]


def test_missing_owner_scores_zero() -> None:
    score = score_fixture("fixtures/weak/acme_document_no_clear_owner.json")

    assert score.score == 0.0
    assert score.label == "none"
    assert [point.type for point in score.weak_points] == [WeakPointType.MISSING_OWNER]


def test_author_can_be_owner_signal_without_explicit_candidate() -> None:
    source = Source(
        id="src_author_only",
        type=SourceType.CRM_NOTE,
        title="Author only note",
        summary="Source has author but no owner candidates.",
        author=Person(
            id="user_author",
            name="Author User",
            role=PersonRole.ACCOUNT_OWNER,
            role_title="Account Owner",
        ),
    )

    score = OwnershipSignalScorer().score(
        ScoringContext(
            context_need=minimal_context_need(),
            source=source,
        )
    )

    assert score.score == 0.82
    assert score.label == "good"
    assert score.weak_points == []


def test_partner_contact_is_weak_owner_signal() -> None:
    score = score_fixture("fixtures/weak/deltabank_unverified_partner_material.json")

    assert score.score == 0.3
    assert score.label == "weak"
    assert [point.type for point in score.weak_points] == [WeakPointType.UNCLEAR_OWNER]

