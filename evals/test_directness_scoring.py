from __future__ import annotations

from data_source_ranking.loader import load_source_fixture
from data_source_ranking.models import (
    ContextNeed,
    DirectnessRelation,
    NeededClaim,
    Source,
    SourceType,
    WeakPointType,
)
from data_source_ranking.scoring import DirectnessScorer, ScoringContext


def score_fixture(path: str):
    fixture = load_source_fixture(path)
    return DirectnessScorer().score(
        ScoringContext(
            context_need=fixture.context_need,
            source=fixture.source,
        )
    )


def minimal_context_need() -> ContextNeed:
    return ContextNeed(
        id="need_test",
        client_id="client_test",
        account_id="account_test",
        opportunity_id="opp_test",
        email_goal="Prepare context.",
        needed_claims=[
            NeededClaim(
                id="need_claim_test",
                description="Test claim.",
            )
        ],
    )


def test_same_client_same_opportunity_scores_highest() -> None:
    score = score_fixture("fixtures/strong/acme_recent_crm_note.json")

    assert score.score == 1.0
    assert score.label == "same_client_same_opportunity"
    assert score.weak_points == []


def test_same_client_adjacent_opportunity_is_medium_high_with_low_severity_weak_point() -> None:
    score = score_fixture("fixtures/medium/acme_same_client_adjacent_work.json")

    assert score.score == 0.78
    assert score.label == "same_client_adjacent_opportunity"
    assert [point.type for point in score.weak_points] == [WeakPointType.LOW_DIRECTNESS]
    assert score.weak_points[0].severity == "low"


def test_similar_client_scores_directional() -> None:
    score = score_fixture("fixtures/medium/northstar_similar_client_proposal.json")

    assert score.score == 0.42
    assert score.label == "similar_client_directional"
    assert [point.type for point in score.weak_points] == [WeakPointType.LOW_DIRECTNESS]
    assert score.weak_points[0].severity == "medium"


def test_generic_industry_scores_low() -> None:
    score = score_fixture("fixtures/weak/deltabank_unverified_partner_material.json")

    assert score.score == 0.22
    assert score.label == "generic_industry"
    assert [point.type for point in score.weak_points] == [WeakPointType.LOW_DIRECTNESS]
    assert score.weak_points[0].severity == "high"


def test_unknown_relation_scores_zero() -> None:
    source = Source(
        id="src_unknown_relation",
        type=SourceType.CRM_NOTE,
        title="Unknown relation",
        summary="A note with no relationship metadata.",
    )

    score = DirectnessScorer().score(
        ScoringContext(
            context_need=minimal_context_need(),
            source=source,
        )
    )

    assert score.score == 0.0
    assert score.label == "unknown"
    assert [point.type for point in score.weak_points] == [WeakPointType.LOW_DIRECTNESS]


def test_mismatched_ids_receive_penalty() -> None:
    source = Source(
        id="src_mismatched_ids",
        type=SourceType.CRM_NOTE,
        title="Mismatched relation",
        summary="Relation claims same opportunity, but metadata points elsewhere.",
        client_id="client_other",
        account_id="account_other",
        opportunity_id="opp_other",
        directness_relation=DirectnessRelation.SAME_CLIENT_SAME_OPPORTUNITY,
    )

    score = DirectnessScorer().score(
        ScoringContext(
            context_need=minimal_context_need(),
            source=source,
        )
    )

    assert score.score == 0.88
    assert score.metadata["mismatches"] == ["client_id", "account_id", "opportunity_id"]
    assert [point.type for point in score.weak_points] == [WeakPointType.LOW_DIRECTNESS]

