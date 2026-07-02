from __future__ import annotations

from pathlib import Path

import pytest

from data_source_ranking.loader import load_source_bundle, load_source_fixture
from data_source_ranking.models import (
    ContextNeed,
    DecisionType,
    NeededClaim,
    RankingDimension,
    SourceBundle,
    Tier,
    WeakPointType,
)
from data_source_ranking.ranking import assign_tier, rank_bundle, rank_source


def source_fixture_paths() -> list[Path]:
    return sorted(
        path
        for path in Path("fixtures").glob("*/*.json")
        if "bundles" not in path.parts
        and "reviews" not in path.parts
        and path.name != "README.md"
    )


def bundle_fixture_paths() -> list[Path]:
    return sorted(Path("fixtures/bundles").glob("*.json"))


def test_rank_source_runs_all_dimensions_with_assigned_tier() -> None:
    fixture = load_source_fixture("fixtures/strong/acme_recent_crm_note.json")

    ranked = rank_source(fixture.context_need, fixture.source)

    assert ranked.source_id == "src_acme_recent_crm_note"
    assert ranked.tier is Tier.STRONG
    assert ranked.metadata["tier_status"] == "assigned"
    assert ranked.metadata["tier_policy"] == "rule_based_v1"
    assert set(ranked.scores) == set(RankingDimension)
    assert len(ranked.reasons) == len(RankingDimension)


@pytest.mark.parametrize("path", source_fixture_paths(), ids=str)
def test_rank_source_matches_expected_fixture_tier(path: Path) -> None:
    fixture = load_source_fixture(path)

    ranked = rank_source(fixture.context_need, fixture.source)

    assert fixture.expected is not None
    assert ranked.tier is fixture.expected.tier


@pytest.mark.parametrize("path", bundle_fixture_paths(), ids=str)
def test_rank_bundle_matches_expected_fixture_decision(path: Path) -> None:
    bundle = load_source_bundle(path)

    ranked = rank_bundle(bundle)

    assert bundle.expected is not None
    assert ranked.decision is bundle.expected.decision
    assert {point.type for point in ranked.weak_points} >= set(bundle.expected.weak_points)


def test_rank_bundle_auto_handoff_has_no_decision_weak_points() -> None:
    bundle = load_source_bundle("fixtures/bundles/acme_auto_handoff.json")

    ranked = rank_bundle(bundle)

    assert ranked.decision is DecisionType.AUTO_HANDOFF
    assert ranked.weak_points == []
    assert ranked.metadata["strong_coverage"] == ["need_claim_current_concern"]
    assert ranked.metadata["usable_coverage"] == ["need_claim_current_concern"]


def test_bundle_auto_handoff_ignores_auxiliary_medium_source_weak_points() -> None:
    bundle = load_source_bundle("fixtures/bundles/acme_auto_handoff.json")

    ranked = rank_bundle(bundle)
    medium_source = next(
        source
        for source in ranked.ranked_sources
        if source.source_id == "src_acme_same_client_adjacent_work"
    )

    assert ranked.decision is DecisionType.AUTO_HANDOFF
    assert {point.type for point in medium_source.weak_points} == {WeakPointType.LOW_DIRECTNESS}
    assert ranked.weak_points == []


def test_bundle_generates_context_request_when_required_claims_only_have_usable_coverage() -> None:
    bundle = load_source_bundle("fixtures/bundles/beta_needs_owner_validation.json")

    ranked = rank_bundle(bundle)

    assert ranked.decision is DecisionType.GENERATE_CONTEXT_REQUEST
    assert ranked.metadata["target_needed_claim_ids"] == [
        "need_claim_current_concern",
        "need_claim_prior_work",
    ]
    assert ranked.metadata["strong_coverage"] == []
    assert ranked.metadata["usable_coverage"] == [
        "need_claim_current_concern",
        "need_claim_prior_work",
    ]
    assert WeakPointType.STALE_SOURCE in {point.type for point in ranked.weak_points}


def test_rank_bundle_flags_sensitive_conflict_for_review() -> None:
    bundle = load_source_bundle("fixtures/bundles/delta_contradictory_sources.json")

    ranked = rank_bundle(bundle)

    assert ranked.decision is DecisionType.NEEDS_USER_REVIEW
    assert {point.type for point in ranked.weak_points} >= {
        WeakPointType.SENSITIVE_EVIDENCE_OVERLAP,
        WeakPointType.SENSITIVE_SOURCE,
    }


def test_bundle_review_preempts_auto_handoff_when_sensitive_evidence_overlaps() -> None:
    bundle = load_source_bundle("fixtures/bundles/delta_contradictory_sources.json")

    ranked = rank_bundle(bundle)
    overlap = next(
        point
        for point in ranked.weak_points
        if point.type is WeakPointType.SENSITIVE_EVIDENCE_OVERLAP
    )

    assert ranked.metadata["strong_coverage"] == [
        "need_claim_current_concern",
        "need_claim_next_step",
    ]
    assert ranked.decision is DecisionType.NEEDS_USER_REVIEW
    assert overlap.metadata["overlapping_needed_claim_ids"] == ["need_claim_current_concern"]


def test_bundle_blocks_when_required_claim_has_no_usable_coverage() -> None:
    bundle = load_source_bundle("fixtures/bundles/gamma_blocked.json")

    ranked = rank_bundle(bundle)

    assert ranked.decision is DecisionType.BLOCKED
    assert ranked.metadata["target_needed_claim_ids"] == ["need_claim_current_concern"]
    assert ranked.metadata["strong_coverage"] == []
    assert ranked.metadata["usable_coverage"] == []
    assert {point.type for point in ranked.weak_points} >= {
        WeakPointType.VAGUE_CLAIM,
        WeakPointType.STALE_SOURCE,
        WeakPointType.LOW_DIRECTNESS,
    }


def test_bundle_uses_optional_claims_as_targets_when_no_required_claims() -> None:
    fixture = load_source_fixture("fixtures/strong/acme_recent_crm_note.json")
    context_need = ContextNeed(
        id="need_optional_only",
        client_id="client_acme",
        account_id="account_acme",
        opportunity_id="opp_acme_renewal_2026",
        email_goal="Prepare optional-only context.",
        needed_claims=[
            NeededClaim(
                id="need_claim_current_concern",
                type="current_client_concern",
                description="Optional current concern.",
                required=False,
            )
        ],
    )
    bundle = SourceBundle(
        id="bundle_optional_only",
        title="Optional-only bundle",
        context_need=context_need,
        sources=[fixture.source],
    )

    ranked = rank_bundle(bundle)

    assert ranked.decision is DecisionType.AUTO_HANDOFF
    assert ranked.metadata["target_needed_claim_ids"] == ["need_claim_current_concern"]
    assert ranked.metadata["strong_coverage"] == ["need_claim_current_concern"]


def test_assign_tier_allows_single_authoritative_source_to_be_strong() -> None:
    fixture = load_source_fixture("fixtures/strong/betaworks_current_opportunity_owner_note.json")

    ranked = rank_source(fixture.context_need, fixture.source)

    assert ranked.scores[RankingDimension.CORROBORATION].score == 0.3
    assert assign_tier(ranked.scores) is Tier.STRONG


def test_assign_tier_caps_sensitive_source_at_weak() -> None:
    fixture = load_source_fixture("fixtures/weak/acme_unsupported_inferred_claim.json")

    ranked = rank_source(fixture.context_need, fixture.source)

    assert ranked.scores[RankingDimension.SENSITIVITY].score == 0.85
    assert ranked.tier is Tier.WEAK


@pytest.mark.parametrize(
    ("path", "dimension", "weak_point_type"),
    [
        (
            "fixtures/weak/betaworks_stale_account_context.json",
            RankingDimension.FRESHNESS,
            WeakPointType.STALE_SOURCE,
        ),
        (
            "fixtures/weak/gammahealth_vague_crm_note.json",
            RankingDimension.SPECIFICITY,
            WeakPointType.VAGUE_CLAIM,
        ),
        (
            "fixtures/weak/deltabank_unverified_partner_material.json",
            RankingDimension.DIRECTNESS,
            WeakPointType.LOW_DIRECTNESS,
        ),
        (
            "fixtures/weak/deltabank_unverified_partner_material.json",
            RankingDimension.AUTHORITY,
            WeakPointType.LOW_AUTHORITY,
        ),
        (
            "fixtures/weak/acme_document_no_clear_owner.json",
            RankingDimension.OWNERSHIP_SIGNAL,
            WeakPointType.MISSING_OWNER,
        ),
    ],
)
def test_tier_hard_gates_prevent_strong_sources(
    path: str,
    dimension: RankingDimension,
    weak_point_type: WeakPointType,
) -> None:
    fixture = load_source_fixture(path)

    ranked = rank_source(fixture.context_need, fixture.source)

    assert ranked.tier is Tier.WEAK
    assert ranked.scores[dimension].weak_points
    assert weak_point_type in {point.type for point in ranked.weak_points}


def test_useful_similar_client_context_is_capped_at_medium() -> None:
    fixture = load_source_fixture("fixtures/medium/northstar_similar_client_proposal.json")

    ranked = rank_source(fixture.context_need, fixture.source)

    assert ranked.scores[RankingDimension.DIRECTNESS].score == 0.42
    assert ranked.tier is Tier.MEDIUM


def test_rank_source_aggregates_weak_points() -> None:
    fixture = load_source_fixture("fixtures/weak/gammahealth_vague_crm_note.json")

    ranked = rank_source(fixture.context_need, fixture.source)

    assert WeakPointType.VAGUE_CLAIM in {point.type for point in ranked.weak_points}


def test_rank_source_uses_bundle_context_for_corroboration() -> None:
    bundle = load_source_bundle("fixtures/bundles/acme_auto_handoff.json")
    source = next(source for source in bundle.sources if source.id == "src_acme_recent_crm_note")

    ranked = rank_source(bundle.context_need, source, bundle_sources=bundle.sources)

    assert ranked.scores[RankingDimension.CORROBORATION].score == 1.0
    assert ranked.scores[RankingDimension.CORROBORATION].label == "multiple_independent"


def test_rank_source_respects_reliability_overrides() -> None:
    fixture = load_source_fixture("fixtures/strong/acme_recent_crm_note.json")

    ranked = rank_source(
        fixture.context_need,
        fixture.source,
        reliability_defaults={"source_system:salesforce": -0.1},
    )

    assert ranked.scores[RankingDimension.HISTORICAL_RELIABILITY].score == 0.68
