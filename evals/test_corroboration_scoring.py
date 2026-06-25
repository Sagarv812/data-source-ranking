from __future__ import annotations

from data_source_ranking.loader import load_source_bundle, load_source_fixture
from data_source_ranking.models import (
    Claim,
    ContextNeed,
    NeededClaim,
    Source,
    SourceSystem,
    SourceType,
    WeakPointType,
)
from data_source_ranking.scoring import CorroborationScorer, ScoringContext


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


def test_acme_bundle_has_independent_support() -> None:
    bundle = load_source_bundle("fixtures/bundles/acme_auto_handoff.json")
    source = next(source for source in bundle.sources if source.id == "src_acme_recent_crm_note")

    score = CorroborationScorer().score(
        ScoringContext(
            context_need=bundle.context_need,
            source=source,
            bundle_sources=bundle.sources,
        )
    )

    assert score.score == 1.0
    assert score.label == "multiple_independent"
    assert score.weak_points == []
    assert score.metadata["independent_support_count"] == 2


def test_single_source_gets_low_corroboration_weak_point() -> None:
    fixture = load_source_fixture("fixtures/strong/acme_recent_crm_note.json")

    score = CorroborationScorer().score(
        ScoringContext(
            context_need=fixture.context_need,
            source=fixture.source,
        )
    )

    assert score.score == 0.3
    assert score.label == "single_source"
    assert [point.type for point in score.weak_points] == [WeakPointType.LOW_CORROBORATION]
    assert score.weak_points[0].severity == "medium"


def test_source_with_no_claims_is_unsupported() -> None:
    fixture = load_source_fixture("fixtures/medium/deltabank_meeting_title_without_notes.json")

    score = CorroborationScorer().score(
        ScoringContext(
            context_need=fixture.context_need,
            source=fixture.source,
        )
    )

    assert score.score == 0.0
    assert score.label == "unsupported"
    assert [point.type for point in score.weak_points] == [WeakPointType.LOW_CORROBORATION]


def test_related_support_scores_lower_than_independent_support() -> None:
    context_need = minimal_context_need()
    source = Source(
        id="src_primary",
        type=SourceType.CRM_NOTE,
        title="Primary",
        summary="Primary claim.",
        source_system=SourceSystem.SALESFORCE,
        claims=[
            Claim(
                id="claim_primary",
                text="Primary claim.",
                supports_needed_claim_ids=["need_claim_test"],
            )
        ],
    )
    related_source = Source(
        id="src_related",
        type=SourceType.CRM_NOTE,
        title="Related",
        summary="Related claim.",
        source_system=SourceSystem.SALESFORCE,
        claims=[
            Claim(
                id="claim_related",
                text="Related claim.",
                supports_needed_claim_ids=["need_claim_test"],
            )
        ],
    )

    score = CorroborationScorer().score(
        ScoringContext(
            context_need=context_need,
            source=source,
            bundle_sources=[source, related_source],
        )
    )

    assert score.score == 0.45
    assert score.label == "related_support"
    assert score.weak_points == []
