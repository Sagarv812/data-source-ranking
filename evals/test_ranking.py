from __future__ import annotations

from pathlib import Path

import pytest

from data_source_ranking.loader import load_source_bundle, load_source_fixture
from data_source_ranking.models import DecisionType, RankingDimension, Tier, WeakPointType
from data_source_ranking.ranking import assign_tier, rank_bundle, rank_source


def source_fixture_paths() -> list[Path]:
    return sorted(
        path
        for path in Path("fixtures").glob("*/*.json")
        if "bundles" not in path.parts and path.name != "README.md"
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


def test_rank_bundle_flags_sensitive_conflict_for_review() -> None:
    bundle = load_source_bundle("fixtures/bundles/delta_contradictory_sources.json")

    ranked = rank_bundle(bundle)

    assert ranked.decision is DecisionType.NEEDS_USER_REVIEW
    assert {point.type for point in ranked.weak_points} >= {
        WeakPointType.CONTRADICTION,
        WeakPointType.SENSITIVE_SOURCE,
    }


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
