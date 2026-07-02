from __future__ import annotations

from datetime import date
from typing import Any

from data_source_ranking.agents.owner_resolution import (
    apply_owner_response as apply_owner_response_to_bundle,
)
from data_source_ranking.agents.retrieval import (
    SimulatedRetrievalFixture,
    SimulatedRetrievalResult,
    apply_simulated_retrieval,
)
from data_source_ranking.agents.state import (
    AgentLoopState,
    AgentRunResult,
    AuditEvent,
    AuditEventLevel,
    AuditTrace,
    LoopAction,
    LoopActionType,
    LoopStep,
    OwnerResponse,
    OwnerResponseResult,
    StopReason,
)
from data_source_ranking.decision_engine import decide
from data_source_ranking.decisions import AutomationDecision, NextActionType
from data_source_ranking.models import DecisionType, Source, SourceBundle
from data_source_ranking.scoring.common import DEFAULT_AS_OF

AGENT_LOOP_VERSION = "deterministic_loop_v1"
EXECUTION_MODE = "single_action_skeleton"
OWNER_RESPONSE_RERUN_EXECUTION_MODE = "owner_response_rerun"
OWNER_RESPONSE_REJECTED_EXECUTION_MODE = "owner_response_rejected"
SIMULATED_RETRIEVAL_RERUN_EXECUTION_MODE = "simulated_retrieval_rerun"
SIMULATED_RETRIEVAL_REJECTED_EXECUTION_MODE = "simulated_retrieval_rejected"


def run_agent(
    bundle: SourceBundle,
    as_of: date = DEFAULT_AS_OF,
    max_iterations: int = 3,
    owner_response: OwnerResponse | None = None,
    simulated_retrieval: SimulatedRetrievalFixture | None = None,
    retrieved_sources: list[Source] | None = None,
    reliability_defaults: dict[str, float] | None = None,
    feedback_metadata: dict[str, Any] | None = None,
) -> AgentRunResult:
    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1")
    if owner_response is not None and simulated_retrieval is not None:
        raise ValueError("owner_response and simulated_retrieval cannot be combined yet")
    if simulated_retrieval is not None and retrieved_sources is None:
        raise ValueError("retrieved_sources are required with simulated_retrieval")

    learned_defaults = dict(reliability_defaults or {})
    initial_decision = decide(
        bundle,
        as_of=as_of,
        reliability_defaults=learned_defaults or None,
    )
    state = _build_initial_state(
        bundle,
        initial_decision,
        as_of,
        max_iterations,
        learned_defaults,
        feedback_metadata,
    )
    state = _run_loop_once(state, initial_decision, max_iterations)

    if owner_response is not None:
        state = _run_owner_response_rerun(
            bundle,
            state,
            owner_response,
            as_of,
            max_iterations,
            learned_defaults,
            feedback_metadata,
        )
    if simulated_retrieval is not None:
        state = _run_simulated_retrieval_rerun(
            bundle,
            state,
            simulated_retrieval,
            retrieved_sources or [],
            as_of,
            max_iterations,
            learned_defaults,
            feedback_metadata,
        )

    return AgentRunResult(
        bundle_id=bundle.id,
        initial_decision=initial_decision,
        final_decision=state.final_decision or initial_decision,
        state=state,
        steps=state.steps,
        audit_trace=state.audit_trace,
        stop_reason=state.stop_reason,
        metadata=state.metadata,
    )


def _run_simulated_retrieval_rerun(
    bundle: SourceBundle,
    state: AgentLoopState,
    retrieval_fixture: SimulatedRetrievalFixture,
    retrieved_sources: list[Source],
    as_of: date,
    max_iterations: int,
    reliability_defaults: dict[str, float],
    feedback_metadata: dict[str, Any] | None,
) -> AgentLoopState:
    if state.automation_decision.decision is DecisionType.AUTO_HANDOFF:
        return _record_simulated_retrieval_not_applicable(
            state,
            retrieval_fixture,
            retrieved_sources,
            as_of,
            max_iterations,
            reliability_defaults,
            feedback_metadata,
        )

    result = apply_simulated_retrieval(bundle, retrieval_fixture, retrieved_sources)
    state = _record_simulated_retrieval_result(
        state,
        result,
        as_of,
        max_iterations,
        reliability_defaults,
        feedback_metadata,
    )
    if not result.accepted or result.updated_bundle is None or not result.added_source_ids:
        return state

    updated_decision = decide(
        result.updated_bundle,
        as_of=as_of,
        reliability_defaults=reliability_defaults or None,
    )
    state = state.model_copy(
        update={
            "current_sources": result.updated_bundle.sources,
            "ranked_sources": updated_decision.ranked_bundle.ranked_sources,
            "automation_decision": updated_decision,
            "candidate_claims": [
                claim for source in result.updated_bundle.sources for claim in source.claims
            ],
            "weak_points": updated_decision.weak_points,
            "owner_candidates": [
                candidate
                for source in result.updated_bundle.sources
                for candidate in source.owner_candidates
            ],
            "pending_approval_prompt": updated_decision.approval_prompt,
            "pending_context_request": updated_decision.context_request,
            "final_decision": updated_decision,
            "metadata": _metadata(
                as_of,
                max_iterations,
                SIMULATED_RETRIEVAL_RERUN_EXECUTION_MODE,
                reliability_defaults,
                feedback_metadata,
            ),
        }
    )
    state = _append_audit_event(
        state,
        AuditEvent(
            sequence=len(state.audit_trace.events) + 1,
            event_type="decision_recorded",
            title="Decision re-run after simulated retrieval",
            detail="The deterministic decision engine re-ran after retrieved sources were added.",
            action_type="decide_automation",
            source_ids=updated_decision.selected_sources,
            policy_gate_ids=[
                gate.gate
                for gate in updated_decision.policy_gates
                if gate.status == "triggered"
            ],
            metadata={"decision": updated_decision.decision.value},
        ),
    )
    return _run_loop_once(state, updated_decision, max_iterations)


def _record_simulated_retrieval_result(
    state: AgentLoopState,
    result: SimulatedRetrievalResult,
    as_of: date,
    max_iterations: int,
    reliability_defaults: dict[str, float],
    feedback_metadata: dict[str, Any] | None,
) -> AgentLoopState:
    retrieved_source_ids = [source.id for source in result.retrieved_sources]
    state_changed = result.accepted and bool(result.added_source_ids)
    step = LoopStep(
        sequence=len(state.steps) + 1,
        input_summary={
            "needed_claim_ids": result.fixture.query.needed_claim_ids,
            "weak_point_types": [
                weak_point_type.value
                for weak_point_type in result.fixture.query.weak_point_types
            ],
            "retrieved_source_count": len(result.retrieved_sources),
        },
        action=LoopAction(
            type=LoopActionType.RETRIEVE_MORE_CONTEXT,
            label="Apply simulated retrieval",
            reason="Apply fixture-backed retrieved sources before re-running the decision.",
            source_ids=retrieved_source_ids,
            claim_ids=result.fixture.query.needed_claim_ids,
            metadata={
                "accepted": str(result.accepted).lower(),
                "added_source_count": str(len(result.added_source_ids)),
                "skipped_duplicate_source_count": str(
                    len(result.skipped_duplicate_source_ids)
                ),
            },
        ),
        output_summary={
            "state_changed": state_changed,
            "stop_reason": state.stop_reason.value if state.stop_reason else None,
        },
        reason="The loop applied simulated retrieval results before a decision rerun.",
        stop_reason=state.stop_reason,
        metadata={
            "applied_effects": result.applied_effects,
            "validation_errors": result.validation_errors,
            "added_source_ids": result.added_source_ids,
            "skipped_duplicate_source_ids": result.skipped_duplicate_source_ids,
        },
    )
    state = state.model_copy(
        update={
            "iteration_count": state.iteration_count + 1,
            "steps": [*state.steps, step],
            "simulated_retrieval_result": result,
            "metadata": _metadata(
                as_of,
                max_iterations,
                (
                    SIMULATED_RETRIEVAL_RERUN_EXECUTION_MODE
                    if result.accepted
                    else SIMULATED_RETRIEVAL_REJECTED_EXECUTION_MODE
                ),
                reliability_defaults,
                feedback_metadata,
            ),
        }
    )
    return _append_simulated_retrieval_audit_event(state, result)


def _record_simulated_retrieval_not_applicable(
    state: AgentLoopState,
    retrieval_fixture: SimulatedRetrievalFixture,
    retrieved_sources: list[Source],
    as_of: date,
    max_iterations: int,
    reliability_defaults: dict[str, float],
    feedback_metadata: dict[str, Any] | None,
) -> AgentLoopState:
    result = SimulatedRetrievalResult(
        accepted=False,
        fixture=retrieval_fixture,
        original_bundle=SourceBundle(
            id=state.bundle_id,
            title=state.context_need.email_goal,
            context_need=state.context_need,
            sources=state.current_sources,
        ),
        retrieved_sources=retrieved_sources,
        validation_errors=["Simulated retrieval is not applicable after auto handoff."],
        metadata={
            "bundle_id": retrieval_fixture.bundle_id,
            "retrieved_source_ids": [source.id for source in retrieved_sources],
            "reason": "simulated_retrieval_not_applicable",
        },
    )
    return _record_simulated_retrieval_result(
        state,
        result,
        as_of,
        max_iterations,
        reliability_defaults,
        feedback_metadata,
    )


def _append_simulated_retrieval_audit_event(
    state: AgentLoopState,
    result: SimulatedRetrievalResult,
) -> AgentLoopState:
    accepted = result.accepted
    return _append_audit_event(
        state,
        AuditEvent(
            sequence=len(state.audit_trace.events) + 1,
            event_type=(
                "simulated_retrieval_applied"
                if accepted
                else "simulated_retrieval_rejected"
            ),
            title=(
                "Simulated retrieval applied"
                if accepted
                else "Simulated retrieval rejected"
            ),
            detail=(
                "Retrieved sources were applied to the source bundle."
                if accepted
                else "Simulated retrieval could not be applied to the source bundle."
            ),
            level=AuditEventLevel.INFO if accepted else AuditEventLevel.WARNING,
            action_type="retrieve_more_context",
            source_ids=[source.id for source in result.retrieved_sources],
            claim_ids=result.fixture.query.needed_claim_ids,
            metadata={
                **result.metadata,
                "added_source_ids": result.added_source_ids,
                "skipped_duplicate_source_ids": result.skipped_duplicate_source_ids,
                "validation_errors": result.validation_errors,
            },
        ),
    )


def _build_initial_state(
    bundle: SourceBundle,
    decision: AutomationDecision,
    as_of: date,
    max_iterations: int,
    reliability_defaults: dict[str, float],
    feedback_metadata: dict[str, Any] | None,
) -> AgentLoopState:
    stop_reason = _initial_stop_reason(decision.decision)
    return AgentLoopState(
        bundle_id=bundle.id,
        context_need=bundle.context_need,
        current_sources=bundle.sources,
        ranked_sources=decision.ranked_bundle.ranked_sources,
        automation_decision=decision,
        candidate_claims=[claim for source in bundle.sources for claim in source.claims],
        weak_points=decision.weak_points,
        owner_candidates=[
            candidate for source in bundle.sources for candidate in source.owner_candidates
        ],
        pending_approval_prompt=decision.approval_prompt,
        pending_context_request=decision.context_request,
        audit_trace=_initial_audit_trace(
            bundle,
            decision,
            reliability_defaults,
            feedback_metadata,
        ),
        final_decision=decision,
        stop_reason=stop_reason,
        metadata=_metadata(
            as_of,
            max_iterations,
            reliability_defaults=reliability_defaults,
            feedback_metadata=feedback_metadata,
        ),
    )


def _run_loop_once(
    state: AgentLoopState,
    decision: AutomationDecision,
    max_iterations: int,
) -> AgentLoopState:
    action, selected_stop_reason = _select_next_action(decision)
    stop_reason = _guarded_stop_reason(state, action, selected_stop_reason, max_iterations)
    sequence = len(state.steps) + 1
    step = LoopStep(
        sequence=sequence,
        input_summary={
            "decision": decision.decision.value,
            "next_action_type": decision.next_action.type.value,
        },
        action=action,
        output_summary={
            "state_changed": False,
            "stop_reason": stop_reason.value,
        },
        reason="The loop selected the next action from the deterministic decision output.",
        stop_reason=stop_reason,
    )
    audit_trace = AuditTrace(
        events=[
            *state.audit_trace.events,
            AuditEvent(
                sequence=len(state.audit_trace.events) + 1,
                event_type="action_selected",
                title="Action selected",
                detail="The loop selected one bounded action from the decision next action.",
                action_type=action.type,
                source_ids=action.source_ids,
                claim_ids=action.claim_ids,
                metadata={
                    "stop_reason": stop_reason.value,
                    **action.metadata,
                },
            ),
        ]
    )
    return state.model_copy(
        update={
            "iteration_count": state.iteration_count + 1,
            "steps": [*state.steps, step],
            "audit_trace": audit_trace,
            "stop_reason": stop_reason,
        }
    )


def _run_owner_response_rerun(
    bundle: SourceBundle,
    state: AgentLoopState,
    owner_response: OwnerResponse,
    as_of: date,
    max_iterations: int,
    reliability_defaults: dict[str, float],
    feedback_metadata: dict[str, Any] | None,
) -> AgentLoopState:
    if not state.steps or state.steps[-1].action.type is not LoopActionType.ASK_OWNER:
        return _record_owner_response_not_applicable(
            state,
            owner_response,
            as_of,
            max_iterations,
            reliability_defaults,
            feedback_metadata,
        )

    result = apply_owner_response_to_bundle(bundle, owner_response, as_of=as_of)
    state = _record_owner_response_result(
        state,
        result,
        as_of,
        max_iterations,
        reliability_defaults,
        feedback_metadata,
    )
    if not result.accepted or result.updated_bundle is None:
        return state

    updated_decision = decide(
        result.updated_bundle,
        as_of=as_of,
        reliability_defaults=reliability_defaults or None,
    )
    state = state.model_copy(
        update={
            "current_sources": result.updated_bundle.sources,
            "ranked_sources": updated_decision.ranked_bundle.ranked_sources,
            "automation_decision": updated_decision,
            "candidate_claims": [
                claim for source in result.updated_bundle.sources for claim in source.claims
            ],
            "weak_points": updated_decision.weak_points,
            "owner_candidates": [
                candidate
                for source in result.updated_bundle.sources
                for candidate in source.owner_candidates
            ],
            "pending_approval_prompt": updated_decision.approval_prompt,
            "pending_context_request": updated_decision.context_request,
            "final_decision": updated_decision,
            "metadata": _metadata(
                as_of,
                max_iterations,
                OWNER_RESPONSE_RERUN_EXECUTION_MODE,
                reliability_defaults,
                feedback_metadata,
            ),
        }
    )
    state = _append_audit_event(
        state,
        AuditEvent(
            sequence=len(state.audit_trace.events) + 1,
            event_type="decision_recorded",
            title="Decision re-run after owner response",
            detail="The deterministic decision engine re-ran after owner validation.",
            action_type="decide_automation",
            source_ids=updated_decision.selected_sources,
            policy_gate_ids=[
                gate.gate
                for gate in updated_decision.policy_gates
                if gate.status == "triggered"
            ],
            metadata={"decision": updated_decision.decision.value},
        ),
    )
    return _run_loop_once(state, updated_decision, max_iterations)


def _record_owner_response_result(
    state: AgentLoopState,
    result: OwnerResponseResult,
    as_of: date,
    max_iterations: int,
    reliability_defaults: dict[str, float],
    feedback_metadata: dict[str, Any] | None,
) -> AgentLoopState:
    stop_reason = (
        state.stop_reason
        if result.accepted
        else StopReason.PENDING_OWNER_RESPONSE
    )
    step = LoopStep(
        sequence=len(state.steps) + 1,
        input_summary={
            "owner_response_outcome": result.response.outcome.value,
            "source_id": result.response.source_id,
        },
        action=LoopAction(
            type=LoopActionType.APPLY_OWNER_RESPONSE,
            label="Apply owner response",
            reason="Apply fixture-backed owner validation to the selected source.",
            source_ids=[result.response.source_id],
            claim_ids=result.response.validated_claim_ids,
            metadata={
                "accepted": str(result.accepted).lower(),
                **{
                    key: str(value)
                    for key, value in result.metadata.items()
                    if not isinstance(value, list)
                },
            },
        ),
        output_summary={
            "state_changed": result.accepted,
            "stop_reason": stop_reason.value if stop_reason else None,
        },
        reason="The loop applied the owner response before re-running the decision.",
        stop_reason=stop_reason,
        metadata={
            "applied_effects": result.applied_effects,
            "validation_errors": result.validation_errors,
        },
    )
    state = state.model_copy(
        update={
            "iteration_count": state.iteration_count + 1,
            "steps": [*state.steps, step],
            "owner_responses": [*state.owner_responses, result.response],
            "owner_response_result": result,
            "stop_reason": stop_reason,
            "metadata": _metadata(
                as_of,
                max_iterations,
                (
                    OWNER_RESPONSE_RERUN_EXECUTION_MODE
                    if result.accepted
                    else OWNER_RESPONSE_REJECTED_EXECUTION_MODE
                ),
                reliability_defaults,
                feedback_metadata,
            ),
        }
    )
    return _append_owner_response_audit_events(state, result)


def _record_owner_response_not_applicable(
    state: AgentLoopState,
    owner_response: OwnerResponse,
    as_of: date,
    max_iterations: int,
    reliability_defaults: dict[str, float],
    feedback_metadata: dict[str, Any] | None,
) -> AgentLoopState:
    step = LoopStep(
        sequence=len(state.steps) + 1,
        input_summary={
            "owner_response_outcome": owner_response.outcome.value,
            "source_id": owner_response.source_id,
        },
        action=LoopAction(
            type=LoopActionType.APPLY_OWNER_RESPONSE,
            label="Apply owner response",
            reason="Owner response was provided, but the current loop action is not ask_owner.",
            source_ids=[owner_response.source_id],
            claim_ids=owner_response.validated_claim_ids,
            metadata={
                "accepted": "false",
                "reason": "owner_response_not_applicable",
            },
        ),
        output_summary={
            "state_changed": False,
            "stop_reason": state.stop_reason.value if state.stop_reason else None,
        },
        reason="Owner responses only apply after an ask_owner action.",
        stop_reason=state.stop_reason,
        metadata={"validation_errors": ["Owner response is not applicable to this run."]},
    )
    return _append_audit_event(
        state.model_copy(
            update={
                "iteration_count": state.iteration_count + 1,
                "steps": [*state.steps, step],
                "owner_responses": [*state.owner_responses, owner_response],
                "metadata": _metadata(
                    as_of,
                    max_iterations,
                    OWNER_RESPONSE_REJECTED_EXECUTION_MODE,
                    reliability_defaults,
                    feedback_metadata,
                ),
            }
        ),
        AuditEvent(
            sequence=len(state.audit_trace.events) + 1,
            event_type="owner_response_rejected",
            title="Owner response not applicable",
            detail="Owner response was provided for a run that is not waiting on an owner.",
            level=AuditEventLevel.WARNING,
            action_type="apply_owner_response",
            source_ids=[owner_response.source_id],
            claim_ids=owner_response.validated_claim_ids,
            metadata={"reason": "owner_response_not_applicable"},
        ),
    )


def _append_owner_response_audit_events(
    state: AgentLoopState,
    result: OwnerResponseResult,
) -> AgentLoopState:
    updated = state
    for event in result.audit_events:
        updated = _append_audit_event(
            updated,
            event.model_copy(update={"sequence": len(updated.audit_trace.events) + 1}),
        )
    return updated


def _append_audit_event(state: AgentLoopState, event: AuditEvent) -> AgentLoopState:
    return state.model_copy(
        update={
            "audit_trace": AuditTrace(events=[*state.audit_trace.events, event]),
        }
    )


def _select_next_action(decision: AutomationDecision) -> tuple[LoopAction, StopReason]:
    action_type = _loop_action_type(decision.next_action.type)
    stop_reason = _stop_reason_for_action(action_type)
    return (
        LoopAction(
            type=action_type,
            label=decision.next_action.label,
            reason=decision.next_action.description,
            source_ids=decision.selected_sources,
            claim_ids=[claim.claim_id for claim in decision.selected_claims],
            metadata=_action_metadata(decision),
        ),
        stop_reason,
    )


def _guarded_stop_reason(
    state: AgentLoopState,
    action: LoopAction,
    selected_stop_reason: StopReason,
    max_iterations: int,
) -> StopReason:
    if state.iteration_count >= max_iterations:
        return StopReason.MAX_ITERATIONS_REACHED
    if _has_repeated_action(state, action):
        return StopReason.REPEATED_ACTION_DETECTED
    if state.pending_context_request and action.type is LoopActionType.ASK_OWNER:
        return StopReason.PENDING_OWNER_RESPONSE
    if state.pending_approval_prompt and action.type is LoopActionType.ASK_USER_REVIEW:
        return StopReason.PENDING_USER_REVIEW
    return selected_stop_reason


def _has_repeated_action(state: AgentLoopState, action: LoopAction) -> bool:
    signature = _action_signature(action)
    return any(_action_signature(step.action) == signature for step in state.steps)


def _action_signature(action: LoopAction) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    return (
        action.type.value,
        tuple(sorted(action.source_ids)),
        tuple(sorted(action.claim_ids)),
    )


def _loop_action_type(next_action_type: NextActionType) -> LoopActionType:
    if next_action_type is NextActionType.PREPARE_HANDOFF:
        return LoopActionType.STOP_AUTO_HANDOFF
    if next_action_type is NextActionType.ASK_OWNER:
        return LoopActionType.ASK_OWNER
    if next_action_type in {NextActionType.ASK_USER, NextActionType.MANUAL_REVIEW}:
        return LoopActionType.ASK_USER_REVIEW
    return LoopActionType.STOP_BLOCKED


def _stop_reason_for_action(action_type: LoopActionType) -> StopReason:
    if action_type is LoopActionType.STOP_AUTO_HANDOFF:
        return StopReason.FINAL_DECISION_READY
    if action_type is LoopActionType.ASK_OWNER:
        return StopReason.PENDING_OWNER_RESPONSE
    if action_type is LoopActionType.ASK_USER_REVIEW:
        return StopReason.PENDING_USER_REVIEW
    return StopReason.BLOCKED_NO_RELIABLE_PATH


def _action_metadata(decision: AutomationDecision) -> dict[str, str]:
    metadata = {
        "decision": decision.decision.value,
        "next_action_type": decision.next_action.type.value,
    }
    if decision.next_action.question:
        metadata["question"] = decision.next_action.question
    if decision.next_action.owner_id:
        metadata["owner_id"] = decision.next_action.owner_id
    if decision.next_action.owner_name:
        metadata["owner_name"] = decision.next_action.owner_name
    if decision.approval_prompt:
        metadata["approval_prompt_issue_type"] = decision.approval_prompt.issue_type
    return metadata


def _initial_stop_reason(decision: DecisionType) -> StopReason:
    if decision is DecisionType.AUTO_HANDOFF:
        return StopReason.FINAL_DECISION_READY
    if decision is DecisionType.BLOCKED:
        return StopReason.BLOCKED_NO_RELIABLE_PATH
    if decision is DecisionType.GENERATE_CONTEXT_REQUEST:
        return StopReason.PENDING_OWNER_RESPONSE
    return StopReason.PENDING_USER_REVIEW


def _initial_audit_trace(
    bundle: SourceBundle,
    decision: AutomationDecision,
    reliability_defaults: dict[str, float],
    feedback_metadata: dict[str, Any] | None,
) -> AuditTrace:
    events = [
        AuditEvent(
            sequence=1,
            event_type="bundle_loaded",
            title="Bundle loaded",
            detail="Loaded the evidence bundle for the agent run.",
            action_type="load_bundle",
            source_ids=[source.id for source in bundle.sources],
            metadata={
                "bundle_id": bundle.id,
                "source_count": len(bundle.sources),
            },
        )
    ]
    if reliability_defaults:
        events.append(
            AuditEvent(
                sequence=len(events) + 1,
                event_type="feedback_snapshot_applied",
                title="Feedback snapshot applied",
                detail="Learned reliability defaults were applied before ranking sources.",
                action_type="record_feedback",
                metadata={
                    **_feedback_metadata(reliability_defaults, feedback_metadata),
                    "reliability_defaults": reliability_defaults,
                },
            )
        )
    events.extend(
        [
            AuditEvent(
                sequence=len(events) + 1,
                event_type="sources_ranked",
                title="Sources ranked",
                detail="Ranked sources through the deterministic evidence scorer.",
                action_type="rank_sources",
                source_ids=[ranked.source_id for ranked in decision.ranked_bundle.ranked_sources],
                metadata={
                    "ranked_source_count": len(decision.ranked_bundle.ranked_sources),
                    "tiers": {
                        ranked.source_id: ranked.tier.value
                        for ranked in decision.ranked_bundle.ranked_sources
                    },
                },
            ),
            AuditEvent(
                sequence=len(events) + 2,
                event_type="decision_recorded",
                title="Initial decision recorded",
                detail="The deterministic decision engine produced the first loop decision.",
                action_type="decide_automation",
                source_ids=decision.selected_sources,
                policy_gate_ids=[
                    gate.gate for gate in decision.policy_gates if gate.status == "triggered"
                ],
                metadata={"decision": decision.decision.value},
            ),
        ]
    )
    return AuditTrace(events=events)


def _metadata(
    as_of: date,
    max_iterations: int,
    execution_mode: str = EXECUTION_MODE,
    reliability_defaults: dict[str, float] | None = None,
    feedback_metadata: dict[str, Any] | None = None,
) -> dict[str, str | int | bool]:
    learned_defaults = reliability_defaults or {}
    return {
        "agent_loop_version": AGENT_LOOP_VERSION,
        "execution_mode": execution_mode,
        "as_of": as_of.isoformat(),
        "max_iterations": max_iterations,
        **_feedback_metadata(learned_defaults, feedback_metadata),
    }


def _feedback_metadata(
    reliability_defaults: dict[str, float],
    feedback_metadata: dict[str, Any] | None,
) -> dict[str, int | bool | str]:
    metadata = feedback_metadata or {}
    fields: dict[str, int | bool | str] = {
        "uses_learned_feedback": bool(reliability_defaults),
        "reliability_default_count": len(reliability_defaults),
        "feedback_event_count": int(metadata.get("feedback_event_count", 0)),
        "source_outcome_count": int(metadata.get("source_outcome_count", 0)),
    }
    if policy := metadata.get("policy"):
        fields["feedback_policy"] = str(policy)
    return fields
