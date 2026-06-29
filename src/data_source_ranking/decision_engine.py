from __future__ import annotations

from datetime import date

from data_source_ranking.context_requests import build_context_request
from data_source_ranking.decisions import (
    ApprovalPrompt,
    AutomationDecision,
    ContextRequest,
    DecisionAuditEvent,
    DecisionConfidence,
    DecisionConfidenceLabel,
    DraftHandoff,
    NextAction,
    NextActionType,
    PolicyGateEffect,
    PolicyGateResult,
    PolicyGateStatus,
    SelectedClaim,
    SourceCitation,
)
from data_source_ranking.models import (
    Claim,
    DecisionType,
    RankedBundle,
    Source,
    SourceBundle,
    Tier,
)
from data_source_ranking.policy import evaluate_policy_gates
from data_source_ranking.prompts import build_approval_prompt
from data_source_ranking.ranking import rank_bundle
from data_source_ranking.scoring.common import DEFAULT_AS_OF


def decide(bundle: SourceBundle, as_of: date = DEFAULT_AS_OF) -> AutomationDecision:
    ranked_bundle = rank_bundle(bundle, as_of=as_of)
    policy_gates = evaluate_policy_gates(ranked_bundle)
    decision = select_final_decision(policy_gates)
    selected_claims = _selected_claims(bundle, ranked_bundle, decision)
    context_request = build_context_request(bundle, ranked_bundle, decision=decision)
    approval_prompt = build_approval_prompt(bundle, ranked_bundle, decision, policy_gates)
    selected_sources = _selected_source_ids(selected_claims, context_request, decision)

    return AutomationDecision(
        bundle_id=bundle.id,
        decision=decision,
        confidence=_confidence(decision, policy_gates),
        summary=_summary(decision, ranked_bundle),
        ranked_bundle=ranked_bundle,
        selected_claims=selected_claims,
        selected_sources=selected_sources,
        source_citations=_source_citations(bundle, selected_claims),
        weak_points=ranked_bundle.weak_points,
        policy_gates=policy_gates,
        next_action=_next_action(decision, policy_gates, context_request, approval_prompt),
        approval_prompt=approval_prompt,
        context_request=context_request,
        draft_handoff=_draft_handoff(bundle, decision, selected_claims, selected_sources),
        audit_trace=_audit_trace(decision, ranked_bundle, policy_gates),
        metadata={"decision_engine": "rule_based_v1", "as_of": as_of.isoformat()},
    )


def select_final_decision(policy_gates: list[PolicyGateResult]) -> DecisionType:
    gates = {gate.gate: gate for gate in policy_gates}
    triggered_effects = {
        gate.effect for gate in policy_gates if gate.status is PolicyGateStatus.TRIGGERED
    }

    if PolicyGateEffect.BLOCKS_AUTOMATION in triggered_effects:
        return DecisionType.BLOCKED
    if PolicyGateEffect.REQUIRES_USER_REVIEW in triggered_effects:
        return DecisionType.NEEDS_USER_REVIEW
    if _can_request_context(gates):
        return DecisionType.GENERATE_CONTEXT_REQUEST
    if _can_auto_handoff(gates, triggered_effects):
        return DecisionType.AUTO_HANDOFF
    if PolicyGateEffect.PREVENTS_AUTO_HANDOFF in triggered_effects:
        return DecisionType.NEEDS_USER_REVIEW
    return DecisionType.BLOCKED


def _confidence(
    decision: DecisionType,
    policy_gates: list[PolicyGateResult],
) -> DecisionConfidence:
    triggered = [gate for gate in policy_gates if gate.status is PolicyGateStatus.TRIGGERED]
    if decision is DecisionType.AUTO_HANDOFF:
        return DecisionConfidence(
            score=0.9,
            label=DecisionConfidenceLabel.HIGH,
            reasons=["All required claims have strong evidence and no review gate fired."],
        )
    if decision is DecisionType.GENERATE_CONTEXT_REQUEST:
        return DecisionConfidence(
            score=0.72,
            label=DecisionConfidenceLabel.MEDIUM,
            reasons=[
                "Required claims have usable evidence, but validation is needed before automation.",
                *_triggered_messages(triggered),
            ],
        )
    if decision is DecisionType.NEEDS_USER_REVIEW:
        return DecisionConfidence(
            score=0.68,
            label=DecisionConfidenceLabel.MEDIUM,
            reasons=[
                "Usable evidence exists, but at least one user-review gate fired.",
                *_triggered_messages(triggered),
            ],
        )
    return DecisionConfidence(
        score=0.86,
        label=DecisionConfidenceLabel.HIGH,
        reasons=[
            "The bundle does not have enough usable evidence for automation.",
            *_triggered_messages(triggered),
        ],
    )


def _selected_claims(
    bundle: SourceBundle,
    ranked_bundle: RankedBundle,
    decision: DecisionType,
) -> list[SelectedClaim]:
    target_ids = set(ranked_bundle.metadata.get("target_needed_claim_ids", []))
    allowed_tiers = _selected_tiers(decision)
    allowed_source_ids = {
        ranked.source_id for ranked in ranked_bundle.ranked_sources if ranked.tier in allowed_tiers
    }
    selected: list[SelectedClaim] = []
    for source in bundle.sources:
        if source.id not in allowed_source_ids:
            continue
        for claim in source.claims:
            for needed_claim_id in claim.supports_needed_claim_ids:
                if needed_claim_id in target_ids:
                    selected.append(_selected_claim(claim, needed_claim_id, source.id))
    return selected


def _selected_tiers(decision: DecisionType) -> set[Tier]:
    if decision is DecisionType.AUTO_HANDOFF:
        return {Tier.STRONG}
    if decision in {DecisionType.GENERATE_CONTEXT_REQUEST, DecisionType.NEEDS_USER_REVIEW}:
        return {Tier.STRONG, Tier.MEDIUM}
    return set()


def _selected_claim(claim: Claim, needed_claim_id: str, source_id: str) -> SelectedClaim:
    return SelectedClaim(
        claim_id=claim.id,
        needed_claim_id=needed_claim_id,
        text=claim.text,
        claim_type=claim.claim_type,
        source_ids=[source_id],
        is_inferred=claim.is_inferred,
        metadata=claim.metadata,
    )


def _selected_source_ids(
    selected_claims: list[SelectedClaim],
    context_request: ContextRequest | None,
    decision: DecisionType,
) -> list[str]:
    source_ids = {source_id for claim in selected_claims for source_id in claim.source_ids}
    if decision is DecisionType.GENERATE_CONTEXT_REQUEST and context_request is not None:
        source_ids.update(context_request.source_ids)
    return sorted(source_ids)


def _source_citations(
    bundle: SourceBundle,
    selected_claims: list[SelectedClaim],
) -> list[SourceCitation]:
    sources = {source.id: source for source in bundle.sources}
    citations: list[SourceCitation] = []
    for selected_claim in selected_claims:
        for source_id in selected_claim.source_ids:
            source = sources[source_id]
            citations.append(
                SourceCitation(
                    source_id=source.id,
                    title=source.title,
                    source_type=source.type,
                    claim_id=selected_claim.claim_id,
                    needed_claim_id=selected_claim.needed_claim_id,
                    citation_label=_citation_label(source),
                )
            )
    return citations


def _next_action(
    decision: DecisionType,
    policy_gates: list[PolicyGateResult],
    context_request: ContextRequest | None,
    approval_prompt: ApprovalPrompt | None,
) -> NextAction:
    if decision is DecisionType.AUTO_HANDOFF:
        return NextAction(
            type=NextActionType.PREPARE_HANDOFF,
            label="Prepare handoff",
            description="Use selected source-backed context for downstream email generation.",
        )
    if decision is DecisionType.GENERATE_CONTEXT_REQUEST:
        return NextAction(
            type=NextActionType.ASK_OWNER,
            label="Ask owner for validation",
            description="Ask the likely owner to validate stale or medium-strength evidence.",
            owner_id=context_request.recipient_id if context_request else None,
            owner_name=context_request.recipient_name if context_request else None,
            question=context_request.question if context_request else None,
            metadata={"triggered_gates": _triggered_gate_names(policy_gates)},
        )
    if decision is DecisionType.NEEDS_USER_REVIEW:
        metadata = {"triggered_gates": _triggered_gate_names(policy_gates)}
        if approval_prompt:
            metadata["approval_prompt_issue_type"] = approval_prompt.issue_type
        return NextAction(
            type=NextActionType.ASK_USER,
            label="Ask user to review",
            description="Ask the current user to resolve the review-triggering evidence issue.",
            question=(
                approval_prompt.question
                if approval_prompt
                else "Should this evidence be used, validated, or excluded before automation?"
            ),
            metadata=metadata,
        )
    return NextAction(
        type=NextActionType.STOP,
        label="Stop automation",
        description="Do not generate automated handoff context from this evidence bundle.",
        metadata={"triggered_gates": _triggered_gate_names(policy_gates)},
    )


def _draft_handoff(
    bundle: SourceBundle,
    decision: DecisionType,
    selected_claims: list[SelectedClaim],
    selected_sources: list[str],
) -> DraftHandoff | None:
    if decision is not DecisionType.AUTO_HANDOFF or not selected_claims:
        return None
    claim_text = " ".join(claim.text for claim in selected_claims)
    return DraftHandoff(
        text=f"{bundle.context_need.email_goal} {claim_text}",
        supported_claim_ids=[claim.claim_id for claim in selected_claims],
        source_ids=selected_sources,
    )


def _audit_trace(
    decision: DecisionType,
    ranked_bundle: RankedBundle,
    policy_gates: list[PolicyGateResult],
) -> list[DecisionAuditEvent]:
    triggered_gates = _triggered_gate_names(policy_gates)
    return [
        DecisionAuditEvent(
            event="rank_bundle_completed",
            message=f"Starter bundle decision was {ranked_bundle.decision.value}.",
            metadata={"ranked_source_count": len(ranked_bundle.ranked_sources)},
        ),
        DecisionAuditEvent(
            event="final_decision_selected",
            message=f"Final automation decision was {decision.value}.",
            metadata={"starter_decision": ranked_bundle.decision.value},
        ),
        DecisionAuditEvent(
            event="policy_gates_evaluated",
            message=f"Evaluated {len(policy_gates)} policy gates.",
            level="warning" if triggered_gates else "info",
            metadata={"triggered_gates": triggered_gates},
        ),
    ]


def _summary(decision: DecisionType, ranked_bundle: RankedBundle) -> str:
    if decision is ranked_bundle.decision:
        return ranked_bundle.reasons[0] if ranked_bundle.reasons else "Decision completed."
    return f"Policy gates changed starter decision to {decision.value}."


def _can_request_context(gates: dict[str, PolicyGateResult]) -> bool:
    usable_coverage_gate = gates.get("required_claims_have_usable_coverage")
    return (
        (
            _gate_passed(gates, "required_claims_have_usable_coverage")
            or (
                usable_coverage_gate is not None
                and usable_coverage_gate.status is PolicyGateStatus.TRIGGERED
                and usable_coverage_gate.effect is PolicyGateEffect.REQUIRES_CONTEXT_REQUEST
            )
        )
        and _gate_passed(gates, "owner_signal_available")
        and (
            _gate_triggered(gates, "required_claims_have_strong_coverage")
            or _gate_triggered(gates, "stale_unvalidated_source_absent")
        )
    )


def _can_auto_handoff(
    gates: dict[str, PolicyGateResult],
    triggered_effects: set[PolicyGateEffect],
) -> bool:
    return (
        _gate_passed(gates, "required_claims_have_strong_coverage")
        and not triggered_effects
    )


def _gate_passed(gates: dict[str, PolicyGateResult], gate_name: str) -> bool:
    return gates.get(gate_name) is not None and gates[gate_name].status is PolicyGateStatus.PASSED


def _gate_triggered(gates: dict[str, PolicyGateResult], gate_name: str) -> bool:
    return (
        gates.get(gate_name) is not None
        and gates[gate_name].status is PolicyGateStatus.TRIGGERED
    )


def _citation_label(source: Source) -> str:
    return source.source_system.value if source.source_system else source.type.value


def _triggered_messages(policy_gates: list[PolicyGateResult]) -> list[str]:
    return [gate.message for gate in policy_gates if gate.status is PolicyGateStatus.TRIGGERED]


def _triggered_gate_names(policy_gates: list[PolicyGateResult]) -> list[str]:
    return [gate.gate for gate in policy_gates if gate.status is PolicyGateStatus.TRIGGERED]
