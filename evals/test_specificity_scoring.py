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
from data_source_ranking.scoring import ScoringContext, SpecificityScorer


def score_fixture(path: str):
    fixture = load_source_fixture(path)
    return SpecificityScorer().score(
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


def test_concrete_client_concern_scores_high() -> None:
    score = score_fixture("fixtures/strong/acme_recent_meeting_notes_clear_attendees.json")

    assert score.score >= 0.8
    assert score.label in {"specific", "email_ready"}
    assert score.weak_points == []
    assert "risk" in score.metadata["concrete_markers"]
    assert score.metadata["concrete_markers"]


def test_vague_crm_note_gets_vague_claim_weak_point() -> None:
    score = score_fixture("fixtures/weak/gammahealth_vague_crm_note.json")

    assert score.score <= 0.35
    assert score.label in {"vague", "generic"}
    assert [point.type for point in score.weak_points] == [WeakPointType.VAGUE_CLAIM]
    assert "transformation" in score.metadata["generic_markers"]


def test_meeting_event_without_claims_uses_summary_with_low_ceiling() -> None:
    score = score_fixture("fixtures/medium/deltabank_meeting_title_without_notes.json")

    assert score.score <= 0.45
    assert score.metadata["best_source"] == "summary"


def test_unsupported_inferred_claim_gets_specific_weak_point() -> None:
    score = score_fixture("fixtures/weak/acme_unsupported_inferred_claim.json")

    assert score.score <= 0.35
    assert [point.type for point in score.weak_points] == [
        WeakPointType.VAGUE_CLAIM,
        WeakPointType.UNSUPPORTED_INFERENCE,
    ]


def test_fallback_summary_can_be_moderately_specific_but_capped() -> None:
    source = Source(
        id="src_summary_only",
        type=SourceType.MEETING_NOTES,
        title="Summary only",
        summary="Client raised rollout risk for regional support workflow before Q3 planning.",
    )

    score = SpecificityScorer().score(
        ScoringContext(
            context_need=minimal_context_need(),
            source=source,
        )
    )

    assert score.score == 0.45
    assert score.metadata["best_source"] == "summary"
    assert "rollout" in score.metadata["concrete_markers"]


def test_claims_are_preferred_over_summary() -> None:
    source = Source(
        id="src_claims_preferred",
        type=SourceType.CRM_NOTE,
        title="Specific title",
        summary="Client raised rollout risk for support workflow.",
        claims=[
            Claim(
                id="claim_generic",
                text="Client interested in transformation.",
                claim_type=ClaimType.PROGRAM_SIGNAL,
            )
        ],
    )

    score = SpecificityScorer().score(
        ScoringContext(
            context_need=minimal_context_need(),
            source=source,
        )
    )

    assert score.metadata["best_source"] == "claim:claim_generic"
    assert [point.type for point in score.weak_points] == [WeakPointType.VAGUE_CLAIM]
