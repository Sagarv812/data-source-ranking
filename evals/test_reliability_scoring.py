from __future__ import annotations

from data_source_ranking.loader import load_source_fixture
from data_source_ranking.models import (
    ContextNeed,
    NeededClaim,
    Source,
    SourceSystem,
    SourceType,
    WeakPointType,
)
from data_source_ranking.scoring import HistoricalReliabilityScorer, ScoringContext


def score_fixture(path: str, reliability_defaults: dict[str, float] | None = None):
    fixture = load_source_fixture(path)
    return HistoricalReliabilityScorer().score(
        ScoringContext(
            context_need=fixture.context_need,
            source=fixture.source,
            reliability_defaults=reliability_defaults or {},
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


def test_salesforce_crm_note_has_reliable_default() -> None:
    score = score_fixture("fixtures/strong/acme_recent_crm_note.json")

    assert score.score == 0.82
    assert score.label == "reliable_default"
    assert score.weak_points == []
    assert score.metadata["uses_learned_feedback"] is False


def test_partner_material_has_low_default_reliability() -> None:
    score = score_fixture("fixtures/weak/deltabank_unverified_partner_material.json")

    assert score.score == 0.27
    assert score.label == "very_low_default"
    assert [point.type for point in score.weak_points] == [
        WeakPointType.LOW_HISTORICAL_RELIABILITY
    ]


def test_source_type_override_is_used() -> None:
    score = score_fixture(
        "fixtures/strong/acme_recent_crm_note.json",
        reliability_defaults={"source_type:crm_note": 0.9},
    )

    assert score.score == 0.94
    assert score.metadata["base_score_source"] == "override"


def test_source_system_modifier_override_is_used() -> None:
    score = score_fixture(
        "fixtures/strong/acme_recent_crm_note.json",
        reliability_defaults={"source_system:salesforce": -0.1},
    )

    assert score.score == 0.68
    assert score.metadata["system_modifier_source"] == "override"


def test_unknown_source_type_uses_low_default() -> None:
    source = Source(
        id="src_other_reliability",
        type=SourceType.OTHER,
        title="Other source",
        summary="Unknown source type.",
        source_system=SourceSystem.OTHER,
    )

    score = HistoricalReliabilityScorer().score(
        ScoringContext(
            context_need=minimal_context_need(),
            source=source,
        )
    )

    assert score.score == 0.4
    assert score.label == "low_default"
    assert [point.type for point in score.weak_points] == [
        WeakPointType.LOW_HISTORICAL_RELIABILITY
    ]

