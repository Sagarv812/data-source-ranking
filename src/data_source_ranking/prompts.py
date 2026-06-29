from __future__ import annotations

from data_source_ranking.decisions import (
    ApprovalPrompt,
    PolicyGateResult,
    PolicyGateStatus,
    PromptChoice,
)
from data_source_ranking.models import ClaimType, DecisionType, RankedBundle, Source, SourceBundle

SIMILAR_CLIENT_DIRECTIONAL_CONTEXT = "similar_client_directional_context"
UNCLEAR_OWNER = "unclear_owner"
SENSITIVE_EVIDENCE_OVERLAP = "sensitive_evidence_overlap"
UNSUPPORTED_CLAIM = "unsupported_claim"
SENSITIVE_PARTNER_MATERIAL = "sensitive_partner_material"
OLD_PROPOSAL = "old_proposal"
USE_DIRECTIONAL_WITH_LABEL = "use_directional_with_label"
CHOOSE_OWNER = "choose_owner"
USE_WITHOUT_OWNER = "use_without_owner"
EXCLUDE_SENSITIVE_SOURCE = "exclude_sensitive_source"
REQUEST_VALIDATION = "request_validation"
STOP_AUTOMATION = "stop_automation"
REMOVE_CLAIM = "remove_claim"
USE_CAUTIOUS_WORDING = "use_cautious_wording"
USE_HISTORICAL_CONTEXT = "use_historical_context"
SKIP_SOURCE = "skip_source"


def build_approval_prompt(
    bundle: SourceBundle,
    ranked_bundle: RankedBundle,
    decision: DecisionType,
    policy_gates: list[PolicyGateResult],
) -> ApprovalPrompt | None:
    if decision is not DecisionType.NEEDS_USER_REVIEW:
        return None

    gate = _triggered_gate(policy_gates, "directional_context_review_absent")
    if gate is not None:
        return _similar_client_directional_prompt(bundle, ranked_bundle, gate)

    gate = _triggered_gate(policy_gates, "unsupported_inference_absent")
    if gate is not None:
        return _unsupported_claim_prompt(bundle, ranked_bundle, gate)

    gate = _triggered_gate(policy_gates, "old_proposal_review_absent")
    if gate is not None:
        return _old_proposal_prompt(bundle, ranked_bundle, gate)

    gate = _triggered_gate(policy_gates, "sensitive_evidence_overlap_absent")
    if gate is not None:
        return _sensitive_evidence_overlap_prompt(bundle, ranked_bundle, gate)

    gate = _triggered_gate(policy_gates, "sensitivity_allows_automation")
    if gate is not None:
        return _sensitive_partner_material_prompt(bundle, ranked_bundle, gate)

    gate = _triggered_gate(policy_gates, "owner_signal_available")
    if gate is not None:
        return _unclear_owner_prompt(bundle, ranked_bundle, gate)

    return None


def _similar_client_directional_prompt(
    bundle: SourceBundle,
    ranked_bundle: RankedBundle,
    gate: PolicyGateResult,
) -> ApprovalPrompt:
    sources = {source.id: source for source in bundle.sources}
    source_titles = {
        source_id: sources[source_id].title
        for source_id in gate.source_ids
        if source_id in sources
    }
    similarity_reasons = {
        source_id: sources[source_id].similarity_reason
        for source_id in gate.source_ids
        if source_id in sources and sources[source_id].similarity_reason
    }

    return ApprovalPrompt(
        issue_type=SIMILAR_CLIENT_DIRECTIONAL_CONTEXT,
        question=(
            f"Use {_source_phrase(source_titles)} only as directional context for this "
            "automation, or skip it?"
        ),
        explanation=(
            "This source comes from a similar client, not the current client. It can support "
            "cautious phrasing, but generated context must not present it as same-client evidence."
        ),
        recommended_action=USE_DIRECTIONAL_WITH_LABEL,
        choices=[
            PromptChoice(
                id=USE_DIRECTIONAL_WITH_LABEL,
                label="Use as directional",
                effect=(
                    "Allows cautious wording that clearly labels the source as a similar-client "
                    "example."
                ),
            ),
            PromptChoice(
                id=SKIP_SOURCE,
                label="Skip",
                effect=(
                    "Removes the similar-client source from selected context for this "
                    "automation."
                ),
            ),
        ],
        source_ids=gate.source_ids,
        metadata={
            "gate": gate.gate,
            "ranking_decision": ranked_bundle.decision.value,
            "source_titles": source_titles,
            "similarity_reasons": similarity_reasons,
        },
    )


def _unclear_owner_prompt(
    bundle: SourceBundle,
    ranked_bundle: RankedBundle,
    gate: PolicyGateResult,
) -> ApprovalPrompt:
    sources = {source.id: source for source in bundle.sources}
    source_titles = {
        source_id: sources[source_id].title
        for source_id in gate.source_ids
        if source_id in sources
    }

    return ApprovalPrompt(
        issue_type=UNCLEAR_OWNER,
        question=(
            f"Who should validate or own {_source_phrase(source_titles)} before automation "
            "continues?"
        ),
        explanation=(
            "The source has useful context, but it does not have a clear owner signal. The "
            "current user needs to identify who can validate it, accept the ownership risk, "
            "or skip it."
        ),
        recommended_action=CHOOSE_OWNER,
        choices=[
            PromptChoice(
                id=CHOOSE_OWNER,
                label="Choose owner",
                effect="Lets the user identify the person who should validate this source.",
            ),
            PromptChoice(
                id=USE_WITHOUT_OWNER,
                label="Use carefully",
                effect=(
                    "Allows cautious use without owner validation when the user accepts the "
                    "ownership risk."
                ),
                metadata={
                    "requires_user_acceptance": True,
                    "risk": "owner_unvalidated",
                },
            ),
            PromptChoice(
                id=SKIP_SOURCE,
                label="Skip",
                effect="Removes this source from selected context for this automation.",
            ),
        ],
        source_ids=gate.source_ids,
        metadata={
            "gate": gate.gate,
            "ranking_decision": ranked_bundle.decision.value,
            "source_titles": source_titles,
            "owner_candidates": _owner_candidates(sources, gate.source_ids),
        },
    )


def _sensitive_evidence_overlap_prompt(
    bundle: SourceBundle,
    ranked_bundle: RankedBundle,
    gate: PolicyGateResult,
) -> ApprovalPrompt:
    sources = {source.id: source for source in bundle.sources}
    source_titles = {
        source_id: sources[source_id].title
        for source_id in gate.source_ids
        if source_id in sources
    }

    return ApprovalPrompt(
        issue_type=SENSITIVE_EVIDENCE_OVERLAP,
        question=(
            "Sensitive evidence overlaps with usable source-backed context. Should we exclude "
            "the sensitive source, request validation, or stop?"
        ),
        explanation=(
            "A sensitive or partner-channel source supports the same need as usable evidence. "
            "It should not be used automatically unless a human validates that it is safe and "
            "appropriate."
        ),
        recommended_action=EXCLUDE_SENSITIVE_SOURCE,
        choices=[
            PromptChoice(
                id=EXCLUDE_SENSITIVE_SOURCE,
                label="Exclude sensitive source",
                effect=(
                    "Keeps the safer usable evidence and removes the sensitive source from "
                    "selected context."
                ),
            ),
            PromptChoice(
                id=REQUEST_VALIDATION,
                label="Request validation",
                effect=(
                    "Asks a responsible owner to confirm whether the sensitive source can be "
                    "used."
                ),
            ),
            PromptChoice(
                id=STOP_AUTOMATION,
                label="Stop",
                effect="Blocks automation for this bundle.",
            ),
        ],
        source_ids=gate.source_ids,
        metadata={
            "gate": gate.gate,
            "ranking_decision": ranked_bundle.decision.value,
            "source_titles": source_titles,
            "overlapping_needed_claim_ids": gate.needed_claim_ids,
            "sensitive_source_ids": gate.source_ids,
            "owner_candidates": _owner_candidates(sources, gate.source_ids),
        },
    )


def _unsupported_claim_prompt(
    bundle: SourceBundle,
    ranked_bundle: RankedBundle,
    gate: PolicyGateResult,
) -> ApprovalPrompt:
    sources = {source.id: source for source in bundle.sources}
    source_titles = {
        source_id: sources[source_id].title
        for source_id in gate.source_ids
        if source_id in sources
    }

    return ApprovalPrompt(
        issue_type=UNSUPPORTED_CLAIM,
        question=(
            "This source includes an unsupported inferred claim. Should we remove the claim, "
            "use only cautious wording, or stop?"
        ),
        explanation=(
            "The claim is not directly supported by the source. It should not be presented as "
            "fact unless a human confirms it or rewrites it safely."
        ),
        recommended_action=REMOVE_CLAIM,
        choices=[
            PromptChoice(
                id=REMOVE_CLAIM,
                label="Remove claim",
                effect="Excludes the unsupported claim from selected context.",
            ),
            PromptChoice(
                id=USE_CAUTIOUS_WORDING,
                label="Use cautiously",
                effect=(
                    "Allows only hedged wording that does not present the claim as confirmed "
                    "fact."
                ),
                metadata={
                    "requires_user_acceptance": True,
                    "risk": "unsupported_inference",
                },
            ),
            PromptChoice(
                id=STOP_AUTOMATION,
                label="Stop",
                effect="Blocks automation for this bundle.",
            ),
        ],
        source_ids=gate.source_ids,
        metadata={
            "gate": gate.gate,
            "ranking_decision": ranked_bundle.decision.value,
            "source_titles": source_titles,
            "unsupported_claims": _unsupported_claims(sources, gate.source_ids),
        },
    )


def _sensitive_partner_material_prompt(
    bundle: SourceBundle,
    ranked_bundle: RankedBundle,
    gate: PolicyGateResult,
) -> ApprovalPrompt:
    sources = {source.id: source for source in bundle.sources}
    source_titles = {
        source_id: sources[source_id].title
        for source_id in gate.source_ids
        if source_id in sources
    }

    return ApprovalPrompt(
        issue_type=SENSITIVE_PARTNER_MATERIAL,
        question=(
            "This source is sensitive partner material. Should we request validation, "
            "exclude it, or stop?"
        ),
        explanation=(
            "Partner-channel or sensitive material should not be used automatically in "
            "outreach unless a responsible owner confirms it is safe and appropriate."
        ),
        recommended_action=REQUEST_VALIDATION,
        choices=[
            PromptChoice(
                id=REQUEST_VALIDATION,
                label="Request validation",
                effect=(
                    "Asks a responsible owner to confirm whether this source can be used."
                ),
            ),
            PromptChoice(
                id=EXCLUDE_SENSITIVE_SOURCE,
                label="Exclude source",
                effect="Removes the sensitive source from selected context.",
            ),
            PromptChoice(
                id=STOP_AUTOMATION,
                label="Stop",
                effect="Blocks automation for this bundle.",
            ),
        ],
        source_ids=gate.source_ids,
        metadata={
            "gate": gate.gate,
            "ranking_decision": ranked_bundle.decision.value,
            "source_titles": source_titles,
            "sensitive_source_ids": gate.source_ids,
            "source_risks": _source_risks(sources, gate.source_ids),
            "owner_candidates": _owner_candidates(sources, gate.source_ids),
        },
    )


def _old_proposal_prompt(
    bundle: SourceBundle,
    ranked_bundle: RankedBundle,
    gate: PolicyGateResult,
) -> ApprovalPrompt:
    sources = {source.id: source for source in bundle.sources}
    source_titles = {
        source_id: sources[source_id].title
        for source_id in gate.source_ids
        if source_id in sources
    }

    return ApprovalPrompt(
        issue_type=OLD_PROPOSAL,
        question=(
            "This proposal may be stale. Should we request validation, use it only as "
            "historical context, or skip it?"
        ),
        explanation=(
            "Older proposal content can be useful, but it may no longer reflect the client's "
            "current situation. It should not be used as current fact unless validated."
        ),
        recommended_action=REQUEST_VALIDATION,
        choices=[
            PromptChoice(
                id=REQUEST_VALIDATION,
                label="Request validation",
                effect=(
                    "Asks a responsible owner to confirm whether the proposal still applies."
                ),
            ),
            PromptChoice(
                id=USE_HISTORICAL_CONTEXT,
                label="Use as historical",
                effect=(
                    "Allows cautious wording that labels the proposal as historical context."
                ),
                metadata={
                    "requires_user_acceptance": True,
                    "risk": "stale_proposal",
                },
            ),
            PromptChoice(
                id=SKIP_SOURCE,
                label="Skip",
                effect="Removes the old proposal from selected context.",
            ),
        ],
        source_ids=gate.source_ids,
        metadata={
            "gate": gate.gate,
            "ranking_decision": ranked_bundle.decision.value,
            "source_titles": source_titles,
            "max_age_days": gate.metadata.get("max_age_days"),
            "owner_candidates": _owner_candidates(sources, gate.source_ids),
        },
    )


def _triggered_gate(
    policy_gates: list[PolicyGateResult],
    gate_name: str,
) -> PolicyGateResult | None:
    return next(
        (
            gate
            for gate in policy_gates
            if gate.gate == gate_name and gate.status is PolicyGateStatus.TRIGGERED
        ),
        None,
    )


def _source_phrase(source_titles: dict[str, str]) -> str:
    titles = list(source_titles.values())
    if len(titles) == 1:
        return f"'{titles[0]}'"
    if titles:
        return "these sources"
    return "this source"


def _owner_candidates(sources: dict[str, Source], source_ids: list[str]) -> dict[str, list[dict]]:
    return {
        source_id: [
            candidate.model_dump(mode="json")
            for candidate in sources[source_id].owner_candidates
        ]
        for source_id in source_ids
        if source_id in sources
    }


def _unsupported_claims(sources: dict[str, Source], source_ids: list[str]) -> dict[str, list[dict]]:
    return {
        source_id: [
            {
                "id": claim.id,
                "text": claim.text,
                "claim_type": claim.claim_type.value,
                "is_inferred": claim.is_inferred,
                "supports_needed_claim_ids": claim.supports_needed_claim_ids,
            }
            for claim in sources[source_id].claims
            if claim.is_inferred or claim.claim_type is ClaimType.UNSUPPORTED_INFERENCE
        ]
        for source_id in source_ids
        if source_id in sources
    }


def _source_risks(sources: dict[str, Source], source_ids: list[str]) -> dict[str, dict]:
    return {
        source_id: {
            "source_type": sources[source_id].type.value,
            "source_system": sources[source_id].source_system.value,
            "sensitivity_labels": [
                label.value for label in sources[source_id].sensitivity_labels
            ],
        }
        for source_id in source_ids
        if source_id in sources
    }
