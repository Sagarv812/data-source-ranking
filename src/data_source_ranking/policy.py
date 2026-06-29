from __future__ import annotations

from collections.abc import Iterable

from data_source_ranking.decisions import (
    PolicyGateEffect,
    PolicyGateResult,
    PolicyGateStatus,
)
from data_source_ranking.models import (
    RankedBundle,
    RankedSource,
    RankingDimension,
    Tier,
    WeakPoint,
    WeakPointType,
)


def evaluate_policy_gates(ranked_bundle: RankedBundle) -> list[PolicyGateResult]:
    return [
        _required_claims_have_usable_coverage(ranked_bundle),
        _required_claims_have_strong_coverage(ranked_bundle),
        _sensitivity_allows_automation(ranked_bundle),
        _sensitive_evidence_overlap_absent(ranked_bundle),
        _directional_context_review_absent(ranked_bundle),
        _stale_unvalidated_source_absent(ranked_bundle),
        _unsupported_inference_absent(ranked_bundle),
        _owner_signal_available(ranked_bundle),
    ]


def _required_claims_have_usable_coverage(ranked_bundle: RankedBundle) -> PolicyGateResult:
    target_ids = _metadata_ids(ranked_bundle, "target_needed_claim_ids")
    usable_ids = _metadata_ids(ranked_bundle, "usable_coverage")
    missing_ids = sorted(target_ids - usable_ids)
    if missing_ids:
        if _has_recoverable_incomplete_source(ranked_bundle):
            return PolicyGateResult(
                gate="required_claims_have_usable_coverage",
                status=PolicyGateStatus.TRIGGERED,
                effect=PolicyGateEffect.REQUIRES_CONTEXT_REQUEST,
                message="A direct source exists, but missing notes or details must be filled in.",
                source_ids=_recoverable_incomplete_source_ids(ranked_bundle),
                needed_claim_ids=missing_ids,
                metadata={"target_needed_claim_ids": sorted(target_ids)},
            )
        return PolicyGateResult(
            gate="required_claims_have_usable_coverage",
            status=PolicyGateStatus.TRIGGERED,
            effect=PolicyGateEffect.BLOCKS_AUTOMATION,
            message="One or more required claims do not have usable source coverage.",
            needed_claim_ids=missing_ids,
            metadata={"target_needed_claim_ids": sorted(target_ids)},
        )
    return PolicyGateResult(
        gate="required_claims_have_usable_coverage",
        status=PolicyGateStatus.PASSED,
        effect=PolicyGateEffect.INFORMATIONAL,
        message="All required claims have usable source coverage.",
        needed_claim_ids=sorted(target_ids),
    )


def _required_claims_have_strong_coverage(ranked_bundle: RankedBundle) -> PolicyGateResult:
    target_ids = _metadata_ids(ranked_bundle, "target_needed_claim_ids")
    strong_ids = _metadata_ids(ranked_bundle, "strong_coverage")
    missing_ids = sorted(target_ids - strong_ids)
    if missing_ids:
        return PolicyGateResult(
            gate="required_claims_have_strong_coverage",
            status=PolicyGateStatus.TRIGGERED,
            effect=PolicyGateEffect.PREVENTS_AUTO_HANDOFF,
            message="One or more required claims need stronger evidence before auto handoff.",
            needed_claim_ids=missing_ids,
            metadata={"target_needed_claim_ids": sorted(target_ids)},
        )
    return PolicyGateResult(
        gate="required_claims_have_strong_coverage",
        status=PolicyGateStatus.PASSED,
        effect=PolicyGateEffect.ALLOWS_AUTO_HANDOFF,
        message="All required claims have strong source coverage.",
        needed_claim_ids=sorted(target_ids),
    )


def _sensitivity_allows_automation(ranked_bundle: RankedBundle) -> PolicyGateResult:
    weak_points = _source_weak_points(ranked_bundle, {WeakPointType.SENSITIVE_SOURCE})
    if weak_points:
        return PolicyGateResult(
            gate="sensitivity_allows_automation",
            status=PolicyGateStatus.TRIGGERED,
            effect=PolicyGateEffect.PREVENTS_AUTO_HANDOFF,
            message="At least one source has sensitivity risk that prevents auto handoff.",
            source_ids=_source_ids(weak_points),
            metadata={"weak_point_types": _weak_point_type_values(weak_points)},
        )
    return PolicyGateResult(
        gate="sensitivity_allows_automation",
        status=PolicyGateStatus.PASSED,
        effect=PolicyGateEffect.INFORMATIONAL,
        message="No high-sensitivity source risk was detected.",
    )


def _sensitive_evidence_overlap_absent(ranked_bundle: RankedBundle) -> PolicyGateResult:
    weak_points = _bundle_weak_points(
        ranked_bundle,
        {WeakPointType.SENSITIVE_EVIDENCE_OVERLAP},
    )
    if weak_points:
        overlapping_ids = sorted(
            {
                needed_claim_id
                for point in weak_points
                for needed_claim_id in point.metadata.get("overlapping_needed_claim_ids", [])
            }
        )
        source_ids = sorted(
            {
                source_id
                for point in weak_points
                for source_id in point.metadata.get("sensitive_source_ids", [])
            }
        )
        return PolicyGateResult(
            gate="sensitive_evidence_overlap_absent",
            status=PolicyGateStatus.TRIGGERED,
            effect=PolicyGateEffect.REQUIRES_USER_REVIEW,
            message="Sensitive weak evidence overlaps with usable evidence for the same need.",
            source_ids=source_ids,
            needed_claim_ids=overlapping_ids,
        )
    return PolicyGateResult(
        gate="sensitive_evidence_overlap_absent",
        status=PolicyGateStatus.PASSED,
        effect=PolicyGateEffect.INFORMATIONAL,
        message="No sensitive evidence overlap was detected.",
    )


def _directional_context_review_absent(ranked_bundle: RankedBundle) -> PolicyGateResult:
    weak_points = [
        point
        for point in _source_weak_points(ranked_bundle, {WeakPointType.LOW_DIRECTNESS})
        if point.metadata.get("directness_relation") == "similar_client"
    ]
    if weak_points:
        return PolicyGateResult(
            gate="directional_context_review_absent",
            status=PolicyGateStatus.TRIGGERED,
            effect=PolicyGateEffect.REQUIRES_USER_REVIEW,
            message="Similar-client evidence must be approved as directional context or skipped.",
            source_ids=_source_ids(weak_points),
            metadata={"weak_point_types": _weak_point_type_values(weak_points)},
        )
    return PolicyGateResult(
        gate="directional_context_review_absent",
        status=PolicyGateStatus.PASSED,
        effect=PolicyGateEffect.INFORMATIONAL,
        message="No similar-client directional review was needed.",
    )


def _stale_unvalidated_source_absent(ranked_bundle: RankedBundle) -> PolicyGateResult:
    weak_points = _bundle_weak_points(ranked_bundle, {WeakPointType.STALE_SOURCE})
    if weak_points:
        return PolicyGateResult(
            gate="stale_unvalidated_source_absent",
            status=PolicyGateStatus.TRIGGERED,
            effect=PolicyGateEffect.REQUIRES_CONTEXT_REQUEST,
            message="Stale evidence should be validated before automation.",
            source_ids=_source_ids(weak_points),
            metadata={"max_age_days": _max_age_days(weak_points)},
        )
    return PolicyGateResult(
        gate="stale_unvalidated_source_absent",
        status=PolicyGateStatus.PASSED,
        effect=PolicyGateEffect.INFORMATIONAL,
        message="No decision-relevant stale evidence was detected.",
    )


def _unsupported_inference_absent(ranked_bundle: RankedBundle) -> PolicyGateResult:
    weak_points = _all_weak_points(ranked_bundle, {WeakPointType.UNSUPPORTED_INFERENCE})
    if weak_points:
        return PolicyGateResult(
            gate="unsupported_inference_absent",
            status=PolicyGateStatus.TRIGGERED,
            effect=PolicyGateEffect.REQUIRES_USER_REVIEW,
            message="At least one claim is inferred without enough support.",
            source_ids=_source_ids(weak_points),
            metadata={"weak_point_types": _weak_point_type_values(weak_points)},
        )
    return PolicyGateResult(
        gate="unsupported_inference_absent",
        status=PolicyGateStatus.PASSED,
        effect=PolicyGateEffect.INFORMATIONAL,
        message="No unsupported inference was detected.",
    )


def _owner_signal_available(ranked_bundle: RankedBundle) -> PolicyGateResult:
    owner_source_ids = sorted(
        ranked.source_id
        for ranked in ranked_bundle.ranked_sources
        if ranked.tier in {Tier.STRONG, Tier.MEDIUM}
        and _score(ranked, RankingDimension.OWNERSHIP_SIGNAL) >= 0.7
    )
    if not owner_source_ids:
        unclear_owner_points = _source_weak_points(ranked_bundle, {WeakPointType.UNCLEAR_OWNER})
        if _has_usable_coverage(ranked_bundle) and unclear_owner_points:
            return PolicyGateResult(
                gate="owner_signal_available",
                status=PolicyGateStatus.TRIGGERED,
                effect=PolicyGateEffect.REQUIRES_USER_REVIEW,
                message="Usable evidence exists, but the user must identify the right owner.",
                source_ids=_source_ids(unclear_owner_points),
                metadata={"weak_point_types": _weak_point_type_values(unclear_owner_points)},
            )
        return PolicyGateResult(
            gate="owner_signal_available",
            status=PolicyGateStatus.TRIGGERED,
            effect=PolicyGateEffect.BLOCKS_AUTOMATION,
            message="No usable source has a clear owner signal for validation or follow-up.",
        )
    return PolicyGateResult(
        gate="owner_signal_available",
        status=PolicyGateStatus.PASSED,
        effect=PolicyGateEffect.INFORMATIONAL,
        message="At least one usable source has a clear owner signal.",
        source_ids=owner_source_ids,
    )


def _metadata_ids(ranked_bundle: RankedBundle, key: str) -> set[str]:
    return set(ranked_bundle.metadata.get(key, []))


def _has_usable_coverage(ranked_bundle: RankedBundle) -> bool:
    target_ids = _metadata_ids(ranked_bundle, "target_needed_claim_ids")
    usable_ids = _metadata_ids(ranked_bundle, "usable_coverage")
    return bool(target_ids) and target_ids <= usable_ids


def _has_recoverable_incomplete_source(ranked_bundle: RankedBundle) -> bool:
    return bool(_recoverable_incomplete_source_ids(ranked_bundle))


def _recoverable_incomplete_source_ids(ranked_bundle: RankedBundle) -> list[str]:
    return sorted(
        ranked.source_id
        for ranked in ranked_bundle.ranked_sources
        if ranked.tier in {Tier.STRONG, Tier.MEDIUM}
        and _score(ranked, RankingDimension.OWNERSHIP_SIGNAL) >= 0.7
        and any(point.type is WeakPointType.INCOMPLETE_CONTEXT for point in ranked.weak_points)
    )


def _score(ranked: RankedSource, dimension: RankingDimension) -> float:
    return ranked.scores[dimension.value].score


def _bundle_weak_points(
    ranked_bundle: RankedBundle,
    types: set[WeakPointType],
) -> list[WeakPoint]:
    return [point for point in ranked_bundle.weak_points if point.type in types]


def _source_weak_points(
    ranked_bundle: RankedBundle,
    types: set[WeakPointType],
) -> list[WeakPoint]:
    return [
        point
        for ranked in ranked_bundle.ranked_sources
        for point in ranked.weak_points
        if point.type in types
    ]


def _all_weak_points(
    ranked_bundle: RankedBundle,
    types: set[WeakPointType],
) -> list[WeakPoint]:
    return [
        point
        for point in [*ranked_bundle.weak_points, *_source_weak_points(ranked_bundle, types)]
        if point.type in types
    ]


def _source_ids(weak_points: Iterable[WeakPoint]) -> list[str]:
    return sorted({point.source_id for point in weak_points if point.source_id})


def _weak_point_type_values(weak_points: Iterable[WeakPoint]) -> list[str]:
    return sorted({point.type.value for point in weak_points})


def _max_age_days(weak_points: Iterable[WeakPoint]) -> int | None:
    ages = [
        point.metadata["age_days"]
        for point in weak_points
        if isinstance(point.metadata.get("age_days"), int)
    ]
    return max(ages) if ages else None
