from __future__ import annotations

import pytest
from pydantic import ValidationError

from data_source_ranking.agents.state import (
    AgentLoopState,
    AgentRunResult,
    AuditEvent,
    AuditTrace,
    LoopAction,
    LoopStep,
    OwnerResponseFixture,
    StopReason,
)
from data_source_ranking.decision_engine import decide
from data_source_ranking.loader import load_source_bundle


def test_agent_loop_state_serializes_with_embedded_automation_decision() -> None:
    bundle = load_source_bundle("fixtures/bundles/beta_needs_owner_validation.json")
    decision = decide(bundle)
    state = AgentLoopState(
        bundle_id=bundle.id,
        context_need=bundle.context_need,
        current_sources=bundle.sources,
        ranked_sources=decision.ranked_bundle.ranked_sources,
        automation_decision=decision,
        candidate_claims=[claim for source in bundle.sources for claim in source.claims],
        weak_points=decision.weak_points,
        owner_candidates=[
            candidate
            for source in bundle.sources
            for candidate in source.owner_candidates
        ],
        pending_context_request=decision.context_request,
        iteration_count=1,
        steps=[
            LoopStep(
                sequence=1,
                input_summary={
                    "source_count": len(bundle.sources),
                    "decision": decision.decision.value,
                },
                action=LoopAction(
                    type="ask_owner",
                    label="Ask owner for validation",
                    reason="The current decision needs owner validation before automation.",
                    source_ids=decision.selected_sources,
                ),
                output_summary={
                    "pending_context_request": decision.context_request is not None,
                },
                reason="The deterministic decision selected an owner-validation next action.",
                stop_reason=StopReason.PENDING_OWNER_RESPONSE,
            )
        ],
        audit_trace=AuditTrace(
            events=[
                AuditEvent(
                    sequence=1,
                    event_type="decision_recorded",
                    title="Decision recorded",
                    detail="The core decision requires owner validation.",
                    action_type="decide_automation",
                    source_ids=decision.selected_sources,
                    policy_gate_ids=[
                        gate.gate for gate in decision.policy_gates if gate.status == "triggered"
                    ],
                ),
                AuditEvent(
                    sequence=2,
                    event_type="loop_stopped",
                    title="Waiting on owner",
                    detail="The loop stopped with one pending owner question.",
                    action_type="ask_owner",
                    source_ids=decision.selected_sources,
                ),
            ]
        ),
        stop_reason=StopReason.PENDING_OWNER_RESPONSE,
    )

    payload = state.model_dump(mode="json")

    assert payload["bundle_id"] == bundle.id
    assert payload["automation_decision"]["bundle_id"] == bundle.id
    assert payload["automation_decision"]["decision"] == "generate_context_request"
    assert "decision" not in payload
    assert payload["pending_context_request"] is not None
    assert payload["pending_approval_prompt"] is None
    assert payload["steps"][0]["action"]["type"] == "ask_owner"
    assert payload["steps"][0]["input_summary"]["source_count"] == len(bundle.sources)
    assert payload["steps"][0]["output_summary"]["pending_context_request"] is True
    assert payload["audit_trace"]["events"][0]["sequence"] == 1
    assert payload["stop_reason"] == "pending_owner_response"


def test_agent_run_result_wraps_initial_and_final_decisions() -> None:
    bundle = load_source_bundle("fixtures/bundles/acme_auto_handoff.json")
    decision = decide(bundle)
    state = AgentLoopState(
        bundle_id=bundle.id,
        context_need=bundle.context_need,
        current_sources=bundle.sources,
        ranked_sources=decision.ranked_bundle.ranked_sources,
        automation_decision=decision,
        candidate_claims=[claim for source in bundle.sources for claim in source.claims],
        final_decision=decision,
        stop_reason=StopReason.FINAL_DECISION_READY,
        audit_trace=AuditTrace(
            events=[
                AuditEvent(
                    sequence=1,
                    event_type="loop_stopped",
                    title="Final decision ready",
                    detail="The core decision is ready for auto handoff.",
                    action_type="stop_auto_handoff",
                    source_ids=decision.selected_sources,
                )
            ]
        ),
    )

    result = AgentRunResult(
        bundle_id=bundle.id,
        initial_decision=decision,
        final_decision=decision,
        state=state,
        audit_trace=state.audit_trace,
        stop_reason=StopReason.FINAL_DECISION_READY,
    )

    payload = result.model_dump(mode="json")

    assert payload["initial_decision"]["decision"] == "auto_handoff"
    assert payload["final_decision"]["decision"] == "auto_handoff"
    assert payload["state"]["automation_decision"]["ranked_bundle"]["id"] == bundle.id
    assert payload["audit_trace"]["events"][0]["title"] == "Final decision ready"
    assert payload["stop_reason"] == "final_decision_ready"


def test_loop_step_records_input_action_output_and_reason() -> None:
    step = LoopStep(
        sequence=1,
        input_summary={"decision": "needs_user_review"},
        action=LoopAction(
            type="ask_user_review",
            label="Ask user",
            reason="A focused approval prompt is pending.",
        ),
        output_summary={"pending_user_review": True},
        reason="Only one pending human question is allowed.",
        stop_reason=StopReason.PENDING_USER_REVIEW,
    )

    payload = step.model_dump(mode="json")

    assert payload["input_summary"] == {"decision": "needs_user_review"}
    assert payload["action"]["type"] == "ask_user_review"
    assert payload["output_summary"] == {"pending_user_review": True}
    assert payload["reason"] == "Only one pending human question is allowed."
    assert payload["stop_reason"] == "pending_user_review"


def test_audit_trace_requires_ordered_unique_sequences() -> None:
    with pytest.raises(ValidationError, match="audit events must be ordered by sequence"):
        AuditTrace(
            events=[
                AuditEvent(
                    sequence=2,
                    event_type="bundle_loaded",
                    title="Loaded",
                    detail="Loaded bundle.",
                ),
                AuditEvent(
                    sequence=1,
                    event_type="sources_ranked",
                    title="Ranked",
                    detail="Ranked sources.",
                ),
            ]
        )

    with pytest.raises(ValidationError, match="audit events must use unique sequence values"):
        AuditTrace(
            events=[
                AuditEvent(
                    sequence=1,
                    event_type="bundle_loaded",
                    title="Loaded",
                    detail="Loaded bundle.",
                ),
                AuditEvent(
                    sequence=1,
                    event_type="sources_ranked",
                    title="Ranked",
                    detail="Ranked sources.",
                ),
            ]
        )


def test_agent_state_rejects_parallel_decision_fields_and_bundle_mismatch() -> None:
    bundle = load_source_bundle("fixtures/bundles/acme_auto_handoff.json")
    decision = decide(bundle)

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AgentLoopState(
            bundle_id=bundle.id,
            context_need=bundle.context_need,
            automation_decision=decision,
            decision=decision.decision,
        )

    with pytest.raises(
        ValidationError,
        match="automation_decision bundle_id must match loop state bundle_id",
    ):
        AgentLoopState(
            bundle_id="other_bundle",
            context_need=bundle.context_need,
            automation_decision=decision,
        )


def test_owner_response_fixture_serializes_contract() -> None:
    fixture = OwnerResponseFixture(
        bundle_path="fixtures/bundles/beta_needs_owner_validation.json",
        as_of="2026-06-21",
        response={
            "bundle_id": "bundle_beta_needs_owner_validation",
            "source_id": "src_betaworks_old_proposal_with_owner",
            "owner_id": "user_lina",
            "owner_name": "Lina Rao",
            "outcome": "accepted",
            "validated_claim_ids": [
                "claim_betaworks_prior_pilot",
                "claim_betaworks_disruption_concern",
            ],
            "notes": "The proposal context is still valid.",
        },
    )

    payload = fixture.model_dump(mode="json")

    assert payload["bundle_path"] == "fixtures/bundles/beta_needs_owner_validation.json"
    assert payload["as_of"] == "2026-06-21"
    assert payload["response"]["source_id"] == "src_betaworks_old_proposal_with_owner"
    assert payload["response"]["outcome"] == "accepted"
    assert payload["response"]["validated_claim_ids"] == [
        "claim_betaworks_prior_pilot",
        "claim_betaworks_disruption_concern",
    ]
