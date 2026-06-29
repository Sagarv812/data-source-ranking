from __future__ import annotations

from data_source_ranking.decisions import ContextRequest
from data_source_ranking.models import (
    DecisionType,
    NeededClaim,
    OwnerCandidate,
    RankedBundle,
    Source,
    SourceBundle,
    SourceType,
    Tier,
)


def build_context_request(
    bundle: SourceBundle,
    ranked_bundle: RankedBundle,
    decision: DecisionType | None = None,
) -> ContextRequest | None:
    effective_decision = decision or ranked_bundle.decision
    if effective_decision is not DecisionType.GENERATE_CONTEXT_REQUEST:
        return None

    usable_sources = _usable_sources(bundle, ranked_bundle)
    owner, owner_source = _best_owner(usable_sources)
    if owner is None or owner_source is None:
        return None

    missing_claims = _claims_missing_strong_coverage(bundle, ranked_bundle)
    source_ids = _usable_source_ids_for_missing_claims(usable_sources, missing_claims)
    if not source_ids:
        source_ids = [owner_source.id]

    return ContextRequest(
        recipient_id=owner.id,
        recipient_name=owner.name,
        recipient_reason=owner.reason,
        question=_question(bundle, owner_source, missing_claims),
        missing_information=_missing_information(missing_claims),
        source_ids=source_ids,
        suggested_response_format=(
            "Reply with confirmed, outdated, or corrected context and include any safer wording."
        ),
        metadata={
            "recipient_role": owner.role.value if owner.role else None,
            "recipient_confidence": owner.confidence,
        },
    )


def _usable_sources(bundle: SourceBundle, ranked_bundle: RankedBundle) -> list[Source]:
    usable_source_ids = {
        ranked.source_id
        for ranked in ranked_bundle.ranked_sources
        if ranked.tier in {Tier.STRONG, Tier.MEDIUM}
    }
    return [source for source in bundle.sources if source.id in usable_source_ids]


def _best_owner(sources: list[Source]) -> tuple[OwnerCandidate | None, Source | None]:
    owner_pairs = [
        (owner, source)
        for source in sources
        for owner in source.owner_candidates
    ]
    if not owner_pairs:
        return None, None
    return max(owner_pairs, key=lambda pair: pair[0].confidence)


def _claims_missing_strong_coverage(
    bundle: SourceBundle,
    ranked_bundle: RankedBundle,
) -> list[NeededClaim]:
    strong_ids = set(ranked_bundle.metadata.get("strong_coverage", []))
    target_ids = set(ranked_bundle.metadata.get("target_needed_claim_ids", []))
    missing_ids = target_ids - strong_ids
    return [claim for claim in bundle.context_need.needed_claims if claim.id in missing_ids]


def _usable_source_ids_for_missing_claims(
    sources: list[Source],
    missing_claims: list[NeededClaim],
) -> list[str]:
    missing_ids = {claim.id for claim in missing_claims}
    return sorted(
        {
            source.id
            for source in sources
            for claim in source.claims
            if missing_ids & set(claim.supports_needed_claim_ids)
        }
    )


def _question(
    bundle: SourceBundle,
    source: Source,
    missing_claims: list[NeededClaim],
) -> str:
    goal = _email_goal_phrase(bundle.context_need.email_goal)
    if source.type is SourceType.MEETING_EVENT:
        return (
            f"What client concern, decision, or next step came out of '{source.title}' "
            f"that should be used for {goal}?"
        )
    if source.type is SourceType.PROPOSAL:
        descriptions = _claim_descriptions(missing_claims)
        if descriptions:
            return (
                f"Can you confirm whether '{source.title}' is still accurate for {goal}, "
                f"especially: {descriptions}"
            )
        return (
            f"Can you confirm whether '{source.title}' is still accurate enough to use for {goal}?"
        )
    if not missing_claims:
        return "Can you confirm whether this context is still accurate for the current outreach?"
    descriptions = _claim_descriptions(missing_claims)
    return f"Can you confirm whether this context is still accurate for {goal}: {descriptions}?"


def _email_goal_phrase(email_goal: str) -> str:
    goal = email_goal.strip().rstrip(".")
    prefixes = (
        "Prepare context for ",
        "Prepare account handoff before ",
        "Prepare account handoff context for ",
        "Prepare re-engagement context for ",
    )
    for prefix in prefixes:
        if goal.startswith(prefix):
            return goal.removeprefix(prefix)
    return goal[0].lower() + goal[1:] if goal else "the current outreach"


def _claim_descriptions(missing_claims: list[NeededClaim]) -> str:
    return "; ".join(claim.description for claim in missing_claims)


def _missing_information(missing_claims: list[NeededClaim]) -> list[str]:
    if not missing_claims:
        return ["Whether the available context is still accurate enough to use."]
    return [claim.description for claim in missing_claims]
