from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from data_source_ranking.models import (
    ContextNeed,
    DecisionType,
    DimensionScore,
    RankedBundle,
    RankedSource,
    RankingDimension,
    Source,
    SourceBundle,
    Tier,
    WeakPoint,
    WeakPointType,
)
from data_source_ranking.scoring import (
    AuthorityScorer,
    BaseScorer,
    CompletenessScorer,
    CorroborationScorer,
    DirectnessScorer,
    FreshnessScorer,
    HistoricalReliabilityScorer,
    OwnershipSignalScorer,
    ScoringContext,
    SensitivityScorer,
    SpecificityScorer,
)
from data_source_ranking.scoring.common import DEFAULT_AS_OF


def default_scorers() -> list[BaseScorer]:
    return [
        FreshnessScorer(),
        DirectnessScorer(),
        AuthorityScorer(),
        OwnershipSignalScorer(),
        CompletenessScorer(),
        CorroborationScorer(),
        SensitivityScorer(),
        SpecificityScorer(),
        HistoricalReliabilityScorer(),
    ]


def rank_source(
    context_need: ContextNeed,
    source: Source,
    bundle_sources: list[Source] | None = None,
    as_of: date = DEFAULT_AS_OF,
    reliability_defaults: dict[str, float] | None = None,
    scorers: list[BaseScorer] | None = None,
) -> RankedSource:
    context = ScoringContext(
        context_need=context_need,
        source=source,
        bundle_sources=bundle_sources or [],
        as_of=as_of,
        reliability_defaults=reliability_defaults or {},
    )
    scores = {
        score.dimension: score
        for score in [scorer.score(context) for scorer in (scorers or default_scorers())]
    }
    tier, tier_reason = _assign_tier_with_reason(scores)

    return RankedSource(
        source_id=source.id,
        tier=tier,
        scores=scores,
        reasons=_reasons(scores),
        weak_points=_weak_points(scores),
        metadata={
            "tier_status": "assigned",
            "tier_policy": "rule_based_v1",
            "tier_scope": "source_evidence_strength",
            "tier_reason": tier_reason,
            "scored_dimensions": sorted(dimension.value for dimension in scores),
        },
    )


def assign_tier(scores: dict[RankingDimension, DimensionScore]) -> Tier:
    tier, _reason = _assign_tier_with_reason(scores)
    return tier


def rank_bundle(
    bundle: SourceBundle,
    as_of: date = DEFAULT_AS_OF,
    reliability_defaults: dict[str, float] | None = None,
    scorers: list[BaseScorer] | None = None,
) -> RankedBundle:
    ranked_sources = [
        rank_source(
            bundle.context_need,
            source,
            bundle_sources=bundle.sources,
            as_of=as_of,
            reliability_defaults=reliability_defaults,
            scorers=scorers,
        )
        for source in bundle.sources
    ]
    decision, reason, weak_points = _assign_bundle_decision(bundle, ranked_sources)

    return RankedBundle(
        id=bundle.id,
        decision=decision,
        ranked_sources=ranked_sources,
        reasons=[reason],
        weak_points=weak_points,
        metadata={
            "decision_policy": "rule_based_v1",
            "source_tiers": {
                ranked.source_id: ranked.tier.value for ranked in ranked_sources
            },
            "target_needed_claim_ids": sorted(_target_needed_claim_ids(bundle)),
            "strong_coverage": sorted(
                _covered_needed_claim_ids(bundle, ranked_sources, {Tier.STRONG})
            ),
            "usable_coverage": sorted(
                _covered_needed_claim_ids(bundle, ranked_sources, {Tier.STRONG, Tier.MEDIUM})
            ),
        },
    )


def _assign_tier_with_reason(scores: dict[RankingDimension, DimensionScore]) -> tuple[Tier, str]:
    if _has_weak_blocker(scores):
        return Tier.WEAK, "One or more high-risk weakness signals block source use."
    if _is_strong(scores):
        return (
            Tier.STRONG,
            "Source has strong directness, provenance, ownership, and content signal.",
        )
    if _is_medium(scores):
        return Tier.MEDIUM, "Source has usable evidence but is not strong enough to rely on alone."
    return Tier.WEAK, "Source does not meet the minimum usable evidence bar."


def _has_weak_blocker(scores: dict[RankingDimension, DimensionScore]) -> bool:
    return (
        _score(scores, RankingDimension.SENSITIVITY) > 0.65
        or _score(scores, RankingDimension.FRESHNESS) < 0.25
        or _score(scores, RankingDimension.DIRECTNESS) < 0.30
        or _score(scores, RankingDimension.AUTHORITY) < 0.35
        or _score(scores, RankingDimension.OWNERSHIP_SIGNAL) < 0.35
        or _score(scores, RankingDimension.HISTORICAL_RELIABILITY) < 0.30
        or _has_high_vague_claim(scores)
        or _is_weak_similar_client_context(scores)
    )


def _is_strong(scores: dict[RankingDimension, DimensionScore]) -> bool:
    if not (
        _score(scores, RankingDimension.FRESHNESS) >= 0.70
        and _score(scores, RankingDimension.DIRECTNESS) >= 0.75
        and _score(scores, RankingDimension.AUTHORITY) >= 0.75
        and _score(scores, RankingDimension.OWNERSHIP_SIGNAL) >= 0.70
        and _score(scores, RankingDimension.COMPLETENESS) >= 0.45
        and _score(scores, RankingDimension.SPECIFICITY) >= 0.65
        and _score(scores, RankingDimension.HISTORICAL_RELIABILITY) >= 0.65
        and _score(scores, RankingDimension.SENSITIVITY) <= 0.45
    ):
        return False

    return (
        _score(scores, RankingDimension.CORROBORATION) >= 0.45
        or _score(scores, RankingDimension.AUTHORITY) >= 0.90
        or _has_excellent_first_party_context(scores)
    )


def _is_medium(scores: dict[RankingDimension, DimensionScore]) -> bool:
    if _score(scores, RankingDimension.SENSITIVITY) > 0.65:
        return False
    return (
        _has_direct_current_context(scores)
        or _has_useful_older_context(scores)
        or _has_useful_similar_client_context(scores)
    )


def _has_direct_current_context(scores: dict[RankingDimension, DimensionScore]) -> bool:
    return (
        _score(scores, RankingDimension.FRESHNESS) >= 0.70
        and _score(scores, RankingDimension.DIRECTNESS) >= 0.75
        and _score(scores, RankingDimension.AUTHORITY) >= 0.50
        and (
            _score(scores, RankingDimension.OWNERSHIP_SIGNAL) >= 0.55
            or _score(scores, RankingDimension.SPECIFICITY) >= 0.65
        )
    )


def _has_useful_older_context(scores: dict[RankingDimension, DimensionScore]) -> bool:
    return (
        _score(scores, RankingDimension.FRESHNESS) >= 0.35
        and _score(scores, RankingDimension.DIRECTNESS) >= 0.65
        and _score(scores, RankingDimension.AUTHORITY) >= 0.65
        and _score(scores, RankingDimension.OWNERSHIP_SIGNAL) >= 0.70
        and _score(scores, RankingDimension.SPECIFICITY) >= 0.65
    )


def _has_useful_similar_client_context(scores: dict[RankingDimension, DimensionScore]) -> bool:
    return (
        _score(scores, RankingDimension.FRESHNESS) >= 0.70
        and _score(scores, RankingDimension.DIRECTNESS) >= 0.40
        and _score(scores, RankingDimension.AUTHORITY) >= 0.65
        and _score(scores, RankingDimension.OWNERSHIP_SIGNAL) >= 0.70
        and _score(scores, RankingDimension.SPECIFICITY) >= 0.60
        and _score(scores, RankingDimension.HISTORICAL_RELIABILITY) >= 0.65
    )


def _has_excellent_first_party_context(scores: dict[RankingDimension, DimensionScore]) -> bool:
    return (
        _score(scores, RankingDimension.DIRECTNESS) >= 0.95
        and _score(scores, RankingDimension.OWNERSHIP_SIGNAL) >= 0.85
        and _score(scores, RankingDimension.COMPLETENESS) >= 0.90
        and _score(scores, RankingDimension.SPECIFICITY) >= 0.90
    )


def _has_high_vague_claim(scores: dict[RankingDimension, DimensionScore]) -> bool:
    return any(
        weak_point.type is WeakPointType.VAGUE_CLAIM and weak_point.severity == "high"
        for score in scores.values()
        for weak_point in score.weak_points
    )


def _is_weak_similar_client_context(scores: dict[RankingDimension, DimensionScore]) -> bool:
    return (
        _score(scores, RankingDimension.DIRECTNESS) <= 0.42
        and (
            _score(scores, RankingDimension.FRESHNESS) < 0.70
            or _score(scores, RankingDimension.SPECIFICITY) < 0.65
            or _score(scores, RankingDimension.HISTORICAL_RELIABILITY) < 0.65
        )
    )


def _score(scores: dict[RankingDimension, DimensionScore], dimension: RankingDimension) -> float:
    return scores[dimension].score


def _assign_bundle_decision(
    bundle: SourceBundle,
    ranked_sources: list[RankedSource],
) -> tuple[DecisionType, str, list[WeakPoint]]:
    target_ids = _target_needed_claim_ids(bundle)
    strong_coverage = _covered_needed_claim_ids(bundle, ranked_sources, {Tier.STRONG})
    usable_coverage = _covered_needed_claim_ids(bundle, ranked_sources, {Tier.STRONG, Tier.MEDIUM})

    review_weak_points = _review_weak_points(bundle, ranked_sources)
    if review_weak_points:
        return (
            DecisionType.NEEDS_USER_REVIEW,
            "Bundle has usable evidence, but sensitive or conflicting support needs review.",
            review_weak_points,
        )

    if target_ids and target_ids <= strong_coverage:
        return (
            DecisionType.AUTO_HANDOFF,
            "All required needed claims are covered by strong source evidence.",
            [],
        )

    if target_ids and target_ids <= usable_coverage:
        return (
            DecisionType.GENERATE_CONTEXT_REQUEST,
            "Required needed claims are covered, but at least one needs stronger validation.",
            _context_request_weak_points(ranked_sources),
        )

    return (
        DecisionType.BLOCKED,
        "Required needed claims are not covered by usable source evidence.",
        _blocked_weak_points(ranked_sources),
    )


def _target_needed_claim_ids(bundle: SourceBundle) -> set[str]:
    required_ids = {claim.id for claim in bundle.context_need.needed_claims if claim.required}
    if required_ids:
        return required_ids
    return {claim.id for claim in bundle.context_need.needed_claims}


def _covered_needed_claim_ids(
    bundle: SourceBundle,
    ranked_sources: list[RankedSource],
    allowed_tiers: set[Tier],
) -> set[str]:
    allowed_source_ids = {
        ranked.source_id for ranked in ranked_sources if ranked.tier in allowed_tiers
    }
    target_ids = _target_needed_claim_ids(bundle)
    return {
        needed_claim_id
        for source in bundle.sources
        if source.id in allowed_source_ids
        for claim in source.claims
        for needed_claim_id in claim.supports_needed_claim_ids
        if needed_claim_id in target_ids
    }


def _review_weak_points(
    bundle: SourceBundle,
    ranked_sources: list[RankedSource],
) -> list[WeakPoint]:
    sensitive_source_ids = {
        ranked.source_id
        for ranked in ranked_sources
        if _ranked_score(ranked, RankingDimension.SENSITIVITY) > 0.65
    }
    if not sensitive_source_ids:
        return []

    sensitive_claim_ids = _supported_target_ids(bundle, sensitive_source_ids)
    usable_source_ids = {
        ranked.source_id
        for ranked in ranked_sources
        if ranked.tier in {Tier.STRONG, Tier.MEDIUM}
    }
    usable_claim_ids = _supported_target_ids(bundle, usable_source_ids)
    if not sensitive_claim_ids & usable_claim_ids:
        return []

    return _unique_weak_points(
        [
            WeakPoint(
                type=WeakPointType.SENSITIVE_EVIDENCE_OVERLAP,
                message="Sensitive weak evidence overlaps with usable evidence for the same need.",
                severity="high",
                metadata={
                    "sensitive_source_ids": sorted(sensitive_source_ids),
                    "overlapping_needed_claim_ids": sorted(sensitive_claim_ids & usable_claim_ids),
                },
            ),
            *[
                weak_point
                for ranked in ranked_sources
                if ranked.source_id in sensitive_source_ids
                for weak_point in ranked.weak_points
                if weak_point.type is WeakPointType.SENSITIVE_SOURCE
            ],
        ]
    )


def _supported_target_ids(bundle: SourceBundle, source_ids: set[str]) -> set[str]:
    target_ids = _target_needed_claim_ids(bundle)
    return {
        needed_claim_id
        for source in bundle.sources
        if source.id in source_ids
        for claim in source.claims
        for needed_claim_id in claim.supports_needed_claim_ids
        if needed_claim_id in target_ids
    }


def _context_request_weak_points(ranked_sources: list[RankedSource]) -> list[WeakPoint]:
    return _unique_weak_points(
        weak_point
        for ranked in ranked_sources
        for weak_point in ranked.weak_points
        if weak_point.type in {WeakPointType.STALE_SOURCE, WeakPointType.UNCLEAR_OWNER}
    )


def _blocked_weak_points(ranked_sources: list[RankedSource]) -> list[WeakPoint]:
    decision_relevant_types = {
        WeakPointType.VAGUE_CLAIM,
        WeakPointType.STALE_SOURCE,
        WeakPointType.LOW_DIRECTNESS,
        WeakPointType.INCOMPLETE_CONTEXT,
        WeakPointType.SENSITIVE_SOURCE,
        WeakPointType.LOW_AUTHORITY,
        WeakPointType.MISSING_OWNER,
        WeakPointType.UNCLEAR_OWNER,
    }
    return _unique_weak_points(
        weak_point
        for ranked in ranked_sources
        for weak_point in ranked.weak_points
        if weak_point.type in decision_relevant_types
    )


def _ranked_score(ranked: RankedSource, dimension: RankingDimension) -> float:
    return ranked.scores[dimension.value].score


def _unique_weak_points(weak_points: Iterable[WeakPoint]) -> list[WeakPoint]:
    unique: list[WeakPoint] = []
    seen: set[tuple[WeakPointType, str | None]] = set()
    for weak_point in weak_points:
        key = (weak_point.type, weak_point.source_id)
        if key not in seen:
            unique.append(weak_point)
            seen.add(key)
    return unique


def _reasons(scores: dict[RankingDimension, DimensionScore]) -> list[str]:
    return [f"{dimension.value}: {score.reason}" for dimension, score in scores.items()]


def _weak_points(scores: dict[RankingDimension, DimensionScore]) -> list[WeakPoint]:
    return [weak_point for score in scores.values() for weak_point in score.weak_points]
