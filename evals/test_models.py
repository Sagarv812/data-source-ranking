from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from data_source_ranking.loader import load_source_fixture
from data_source_ranking.models import (
    Claim,
    ClaimType,
    ContextNeed,
    DimensionScore,
    DirectnessRelation,
    NeededClaim,
    NeededClaimType,
    PersonRole,
    RankingDimension,
    Source,
    SourceFixture,
    SourceType,
    Tier,
    ValidationRecord,
)


def test_load_source_fixture_from_json() -> None:
    fixture = load_source_fixture(Path("fixtures/strong/acme_recent_crm_note.json"))

    assert fixture.context_need.id == "need_acme_renewal"
    assert fixture.source.id == "src_acme_recent_crm_note"
    assert fixture.source.type is SourceType.CRM_NOTE
    assert fixture.source.directness_relation is DirectnessRelation.SAME_CLIENT_SAME_OPPORTUNITY
    assert fixture.source.author is not None
    assert fixture.source.author.role is PersonRole.ACCOUNT_OWNER
    assert fixture.source.claims[0].claim_type is ClaimType.CLIENT_CONCERN
    assert fixture.source.claims[0].supports_needed_claim_ids == ["need_claim_current_concern"]
    assert fixture.context_need.needed_claims[0].type is NeededClaimType.CURRENT_CLIENT_CONCERN
    assert fixture.expected is not None
    assert fixture.expected.tier is Tier.STRONG


def test_source_requires_summary_or_body() -> None:
    with pytest.raises(ValidationError, match="source requires either summary or body"):
        Source(
            id="src_missing_content",
            type="crm_note",
            title="Missing content",
        )


def test_source_allows_missing_date_and_owner() -> None:
    source = Source(
        id="src_vague_note",
        type="crm_note",
        title="Vague CRM note",
        summary="Client interested in transformation.",
    )

    assert source.created_at is None
    assert source.owner_candidates == []


def test_unknown_fields_fail_fast() -> None:
    context_need = ContextNeed(
        id="need_test",
        client_id="client_test",
        email_goal="Prepare context.",
        needed_claims=[
            NeededClaim(
                id="need_claim_current_concern",
                type="current_client_concern",
                description="Current client concern.",
            )
        ],
    )
    source = Source(
        id="src_test",
        type="crm_note",
        title="Test note",
        summary="Client raised timeline risk.",
        claims=[
            Claim(
                id="claim_test",
                text="Client raised timeline risk.",
                claim_type="implementation_risk",
            )
        ],
    )

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SourceFixture.model_validate(
            {
                "context_need": context_need.model_dump(mode="json"),
                "source": source.model_dump(mode="json"),
                "unexpected": True,
            }
        )


def test_similar_client_relation_requires_reason() -> None:
    with pytest.raises(ValidationError, match="similar-client sources require similarity_reason"):
        Source(
            id="src_similar_client",
            type="proposal",
            title="Similar client proposal",
            summary="A similar client used this rollout approach.",
            directness_relation="similar_client",
        )


def test_claim_level_validation_is_supported() -> None:
    record = ValidationRecord(
        validated_claim_ids=["claim_acme_timeline_concern"],
        outcome="accepted",
    )

    assert record.validated_claim_ids == ["claim_acme_timeline_concern"]


def test_dimension_score_uses_dimension_enum() -> None:
    score = DimensionScore(
        dimension="freshness",
        score=0.9,
        label="recent",
        reason="Source was recently updated.",
    )

    assert score.dimension is RankingDimension.FRESHNESS
