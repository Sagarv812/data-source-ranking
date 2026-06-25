from __future__ import annotations

from data_source_ranking.loader import load_source_fixture
from data_source_ranking.models import (
    Claim,
    ClaimType,
    ContextNeed,
    NeededClaim,
    Source,
    SourceType,
    WeakPointType,
)
from data_source_ranking.scoring import CompletenessScorer, ScoringContext


def score_fixture(path: str):
    fixture = load_source_fixture(path)
    return CompletenessScorer().score(
        ScoringContext(
            context_need=fixture.context_need,
            source=fixture.source,
        )
    )


def test_partial_required_claim_coverage_scores_partial() -> None:
    score = score_fixture("fixtures/strong/acme_recent_crm_note.json")

    assert score.score == 0.45
    assert score.label == "partial"
    assert [point.type for point in score.weak_points] == [WeakPointType.INCOMPLETE_CONTEXT]
    assert score.metadata["covered_required_claim_ids"] == ["need_claim_current_concern"]
    assert score.metadata["missing_required_claim_ids"] == ["need_claim_validated_prior_work"]


def test_required_and_optional_claims_covered_scores_complete_with_optional() -> None:
    score = score_fixture("fixtures/strong/acme_recent_meeting_notes_clear_attendees.json")

    assert score.score == 1.0
    assert score.label == "complete_with_optional"
    assert score.weak_points == []


def test_no_claims_scores_none_and_incomplete() -> None:
    score = score_fixture("fixtures/medium/deltabank_meeting_title_without_notes.json")

    assert score.score == 0.0
    assert score.label == "none"
    assert [point.type for point in score.weak_points] == [WeakPointType.INCOMPLETE_CONTEXT]


def test_optional_only_scores_low() -> None:
    context_need = ContextNeed(
        id="need_optional_case",
        client_id="client_test",
        email_goal="Prepare context.",
        needed_claims=[
            NeededClaim(
                id="need_claim_required",
                description="Required claim.",
                required=True,
            ),
            NeededClaim(
                id="need_claim_optional",
                description="Optional claim.",
                required=False,
            ),
        ],
    )
    source = Source(
        id="src_optional_only",
        type=SourceType.CRM_NOTE,
        title="Optional only",
        summary="Only optional context.",
        claims=[
            Claim(
                id="claim_optional",
                text="Optional context exists.",
                claim_type=ClaimType.OTHER,
                supports_needed_claim_ids=["need_claim_optional"],
            )
        ],
    )

    score = CompletenessScorer().score(
        ScoringContext(
            context_need=context_need,
            source=source,
        )
    )

    assert score.score == 0.3
    assert score.label == "optional_only"
    assert [point.type for point in score.weak_points] == [WeakPointType.INCOMPLETE_CONTEXT]


def test_multiple_required_claims_can_be_mostly_complete() -> None:
    context_need = ContextNeed(
        id="need_mostly_complete",
        client_id="client_test",
        email_goal="Prepare context.",
        needed_claims=[
            NeededClaim(id="need_1", description="Need 1."),
            NeededClaim(id="need_2", description="Need 2."),
            NeededClaim(id="need_3", description="Need 3."),
            NeededClaim(id="need_4", description="Need 4."),
        ],
    )
    source = Source(
        id="src_mostly_complete",
        type=SourceType.CRM_NOTE,
        title="Mostly complete",
        summary="Covers most needs.",
        claims=[
            Claim(id="claim_1", text="Need 1.", supports_needed_claim_ids=["need_1"]),
            Claim(id="claim_2", text="Need 2.", supports_needed_claim_ids=["need_2"]),
            Claim(id="claim_3", text="Need 3.", supports_needed_claim_ids=["need_3"]),
        ],
    )

    score = CompletenessScorer().score(
        ScoringContext(
            context_need=context_need,
            source=source,
        )
    )

    assert score.score == 0.7
    assert score.label == "mostly_complete"
    assert score.metadata["missing_required_claim_ids"] == ["need_4"]
