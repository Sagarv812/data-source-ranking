from __future__ import annotations

from datetime import date

from data_source_ranking.context_requests import build_context_request
from data_source_ranking.decisions import (
    ApprovalPrompt,
    AutomationDecision,
    BlockedOutput,
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


def decide(
    bundle: SourceBundle,
    as_of: date = DEFAULT_AS_OF,
    reliability_defaults: dict[str, float] | None = None,
) -> AutomationDecision:
    ranked_bundle = rank_bundle(
        bundle,
        as_of=as_of,
        reliability_defaults=reliability_defaults,
    )
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
        draft_handoff=_draft_handoff(
            bundle,
            decision,
            selected_claims,
            selected_sources,
            policy_gates,
        ),
        blocked_output=_blocked_output(bundle, decision, ranked_bundle, policy_gates),
        audit_trace=_audit_trace(decision, ranked_bundle, policy_gates),
        metadata={
            "decision_engine": "rule_based_v1",
            "as_of": as_of.isoformat(),
            "uses_learned_feedback": bool(reliability_defaults),
            "reliability_default_count": len(reliability_defaults or {}),
        },
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
    policy_gates: list[PolicyGateResult],
) -> DraftHandoff | None:
    if decision is not DecisionType.AUTO_HANDOFF or not selected_claims:
        return None
    return DraftHandoff(
        text=_draft_handoff_text(bundle, selected_claims),
        supported_claim_ids=_unique([claim.claim_id for claim in selected_claims]),
        source_ids=selected_sources,
        caveats=[],
        metadata={
            "handoff_type": "auto",
            "review_skipped_reason": _review_skipped_reason(policy_gates),
            "selected_claim_count": len(selected_claims),
            "source_count": len(selected_sources),
        },
    )


def _draft_handoff_text(bundle: SourceBundle, selected_claims: list[SelectedClaim]) -> str:
    claim_text = " ".join(_sentence(claim.text) for claim in selected_claims)
    return (
        f"For {_handoff_goal(bundle.context_need.email_goal)}, use this "
        f"source-backed context: {claim_text}"
    )


def _handoff_goal(email_goal: str) -> str:
    goal = email_goal.strip().rstrip(".")
    lowered = goal.casefold()
    for prefix in ("prepare ", "draft ", "write ", "create "):
        if lowered.startswith(prefix):
            return _lower_initial(goal[len(prefix) :])
    return _lower_initial(goal)


def _lower_initial(text: str) -> str:
    if len(text) > 1 and text[1].isupper():
        return text
    return f"{text[:1].lower()}{text[1:]}"


def _sentence(text: str) -> str:
    stripped = text.strip()
    if stripped.endswith((".", "!", "?")):
        return stripped
    return f"{stripped}."


def _review_skipped_reason(policy_gates: list[PolicyGateResult]) -> str:
    passed_gate_names = {
        gate.gate for gate in policy_gates if gate.status is PolicyGateStatus.PASSED
    }
    if "required_claims_have_strong_coverage" in passed_gate_names:
        return "All required claims have strong source coverage and no review gate fired."
    return "No review gate fired for the selected source-backed claims."


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _blocked_output(
    bundle: SourceBundle,
    decision: DecisionType,
    ranked_bundle: RankedBundle,
    policy_gates: list[PolicyGateResult],
) -> BlockedOutput | None:
    if decision is not DecisionType.BLOCKED:
        return None
    blocking_gates = _blocking_gates(policy_gates)
    triggered_gates = _triggered_gates(policy_gates)
    return BlockedOutput(
        blocking_reason=_blocking_reason(blocking_gates, ranked_bundle),
        missing_evidence=_missing_evidence(bundle, ranked_bundle, blocking_gates),
        sources_considered=_ranked_source_ids(ranked_bundle),
        blocking_policy_gates=[gate.gate for gate in blocking_gates],
        manual_next_step=_manual_next_step(blocking_gates),
        metadata={
            "triggered_policy_gates": [gate.gate for gate in triggered_gates],
            "sources_considered_count": len(ranked_bundle.ranked_sources),
            "weak_point_types": _weak_point_types(ranked_bundle),
        },
    )


def _blocking_gates(policy_gates: list[PolicyGateResult]) -> list[PolicyGateResult]:
    return [
        gate
        for gate in policy_gates
        if gate.status is PolicyGateStatus.TRIGGERED
        and gate.effect is PolicyGateEffect.BLOCKS_AUTOMATION
    ]


def _triggered_gates(policy_gates: list[PolicyGateResult]) -> list[PolicyGateResult]:
    return [gate for gate in policy_gates if gate.status is PolicyGateStatus.TRIGGERED]


def _blocking_reason(
    blocking_gates: list[PolicyGateResult],
    ranked_bundle: RankedBundle,
) -> str:
    if blocking_gates:
        return blocking_gates[0].message
    return ranked_bundle.reasons[0] if ranked_bundle.reasons else "Automation was blocked."


def _missing_evidence(
    bundle: SourceBundle,
    ranked_bundle: RankedBundle,
    blocking_gates: list[PolicyGateResult],
) -> list[str]:
    needed_claims = {claim.id: claim.description for claim in bundle.context_need.needed_claims}
    missing_ids = _unique(
        [needed_claim_id for gate in blocking_gates for needed_claim_id in gate.needed_claim_ids]
    )
    if not missing_ids:
        target_ids = ranked_bundle.metadata.get("target_needed_claim_ids", [])
        usable_ids = set(ranked_bundle.metadata.get("usable_coverage", []))
        missing_ids = [
            needed_claim_id for needed_claim_id in target_ids if needed_claim_id not in usable_ids
        ]
    return [needed_claims.get(needed_claim_id, needed_claim_id) for needed_claim_id in missing_ids]


def _ranked_source_ids(ranked_bundle: RankedBundle) -> list[str]:
    return [ranked.source_id for ranked in ranked_bundle.ranked_sources]


def _manual_next_step(blocking_gates: list[PolicyGateResult]) -> str:
    gate_names = {gate.gate for gate in blocking_gates}
    if {
        "required_claims_have_usable_coverage",
        "owner_signal_available",
    } <= gate_names:
        return (
            "Find a recent same-client source that directly covers the missing required "
            "context, or identify an owner who can provide validated current context."
        )
    if "required_claims_have_usable_coverage" in gate_names:
        return (
            "Find a recent same-client source that directly covers the missing required "
            "context before restarting automation."
        )
    if "owner_signal_available" in gate_names:
        return (
            "Identify an owner who can validate the usable context before restarting "
            "automation."
        )
    return "Manually review the evidence and add a reliable source before restarting automation."


def _weak_point_types(ranked_bundle: RankedBundle) -> list[str]:
    return sorted({point.type.value for point in ranked_bundle.weak_points})


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
