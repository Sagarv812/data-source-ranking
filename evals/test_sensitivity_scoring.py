from __future__ import annotations

from datetime import date

from data_source_ranking.loader import load_source_fixture
from data_source_ranking.models import (
    ContextNeed,
    NeededClaim,
    SensitivityLabel,
    Source,
    SourceSystem,
    SourceType,
    ValidationRecord,
    WeakPointType,
)
from data_source_ranking.scoring import ScoringContext, SensitivityScorer


def score_fixture(path: str):
    fixture = load_source_fixture(path)
    return SensitivityScorer().score(
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


def test_no_obvious_sensitivity_scores_zero() -> None:
    score = score_fixture("fixtures/strong/acme_recent_crm_note.json")

    assert score.score == 0.0
    assert score.label == "none"
    assert score.weak_points == []


def test_internal_only_is_caution_not_review_by_itself() -> None:
    source = Source(
        id="src_internal_only",
        type=SourceType.CRM_NOTE,
        title="Internal note",
        summary="Internal-only source.",
        sensitivity_labels=[SensitivityLabel.INTERNAL_ONLY],
    )

    score = SensitivityScorer().score(
        ScoringContext(
            context_need=minimal_context_need(),
            source=source,
        )
    )

    assert score.score == 0.45
    assert score.label == "internal_caution"
    assert score.weak_points == []


def test_partner_material_scores_high_risk() -> None:
    score = score_fixture("fixtures/weak/deltabank_unverified_partner_material.json")

    assert score.score == 0.85
    assert score.label == "high_risk"
    assert [point.type for point in score.weak_points] == [WeakPointType.SENSITIVE_SOURCE]


def test_unsupported_inference_adds_specific_weak_point() -> None:
    score = score_fixture("fixtures/weak/acme_unsupported_inferred_claim.json")

    assert score.score == 0.85
    assert score.label == "high_risk"
    assert [point.type for point in score.weak_points] == [
        WeakPointType.SENSITIVE_SOURCE,
        WeakPointType.UNSUPPORTED_INFERENCE,
    ]


def test_validation_reduces_but_does_not_erase_risk() -> None:
    source = Source(
        id="src_validated_partner_doc",
        type=SourceType.PARTNER_MATERIAL,
        title="Validated partner doc",
        summary="Partner material validated by owner.",
        source_system=SourceSystem.PARTNER_PORTAL,
        sensitivity_labels=[SensitivityLabel.PARTNER_CHANNEL],
        validation_history=[
            ValidationRecord(
                validated_at=date(2026, 6, 20),
                outcome="accepted",
            )
        ],
    )

    score = SensitivityScorer().score(
        ScoringContext(
            context_need=minimal_context_need(),
            source=source,
        )
    )

    assert score.score == 0.65
    assert score.label == "review_required"
    assert [point.type for point in score.weak_points] == [WeakPointType.SENSITIVE_SOURCE]

