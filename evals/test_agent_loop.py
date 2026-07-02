from __future__ import annotations

from datetime import date

import pytest

from data_source_ranking.agents.loop import (
    AGENT_LOOP_VERSION,
    EXECUTION_MODE,
    _action_signature,
    _guarded_stop_reason,
    run_agent,
)
from data_source_ranking.agents.state import LoopAction, StopReason
from data_source_ranking.loader import (
    load_owner_response_fixture,
    load_simulated_retrieval_fixture,
    load_simulated_retrieval_sources,
    load_source_bundle,
)


def test_run_agent_returns_public_agent_run_result_for_loaded_bundle() -> None:
    bundle = load_source_bundle("fixtures/bundles/beta_needs_owner_validation.json")

    result = run_agent(bundle, as_of=date(2026, 6, 21), max_iterations=3)
    payload = result.model_dump(mode="json")

    assert payload["bundle_id"] == bundle.id
    assert payload["initial_decision"]["decision"] == "generate_context_request"
    assert payload["final_decision"]["decision"] == "generate_context_request"
    assert payload["state"]["automation_decision"]["bundle_id"] == bundle.id
    assert payload["state"]["pending_context_request"] is not None
    assert payload["state"]["pending_approval_prompt"] is None
    assert payload["state"]["current_sources"][0]["id"] == bundle.sources[0].id
    assert payload["state"]["ranked_sources"]
    assert payload["state"]["candidate_claims"]
    assert payload["state"]["owner_candidates"]
    assert payload["state"]["iteration_count"] == 1
    assert payload["state"]["steps"] == payload["steps"]
    assert payload["steps"][0]["sequence"] == 1
    assert payload["steps"][0]["input_summary"] == {
        "decision": "generate_context_request",
        "next_action_type": "ask_owner",
    }
    assert payload["steps"][0]["action"]["type"] == "ask_owner"
    assert payload["steps"][0]["action"]["label"] == "Ask owner for validation"
    assert payload["steps"][0]["action"]["source_ids"] == payload["initial_decision"][
        "selected_sources"
    ]
    assert payload["steps"][0]["action"]["claim_ids"] == [
        claim["claim_id"] for claim in payload["initial_decision"]["selected_claims"]
    ]
    assert payload["steps"][0]["action"]["metadata"]["decision"] == (
        "generate_context_request"
    )
    assert payload["steps"][0]["action"]["metadata"]["next_action_type"] == "ask_owner"
    assert payload["steps"][0]["action"]["metadata"]["owner_id"]
    assert payload["steps"][0]["action"]["metadata"]["owner_name"]
    assert payload["steps"][0]["output_summary"] == {
        "state_changed": False,
        "stop_reason": "pending_owner_response",
    }
    assert payload["steps"][0]["stop_reason"] == "pending_owner_response"
    assert payload["stop_reason"] == "pending_owner_response"
    assert [event["event_type"] for event in payload["audit_trace"]["events"]] == [
        "bundle_loaded",
        "sources_ranked",
        "decision_recorded",
        "action_selected",
    ]
    assert [event["sequence"] for event in payload["audit_trace"]["events"]] == [1, 2, 3, 4]
    assert payload["audit_trace"]["events"][0]["action_type"] == "load_bundle"
    assert payload["audit_trace"]["events"][0]["metadata"] == {
        "bundle_id": bundle.id,
        "source_count": len(bundle.sources),
    }
    assert payload["audit_trace"]["events"][1]["action_type"] == "rank_sources"
    assert payload["audit_trace"]["events"][1]["metadata"]["ranked_source_count"] == len(
        bundle.sources
    )
    assert payload["audit_trace"]["events"][2]["action_type"] == "decide_automation"
    assert payload["audit_trace"]["events"][2]["metadata"] == {
        "decision": "generate_context_request"
    }
    assert payload["audit_trace"]["events"][3]["action_type"] == "ask_owner"
    assert payload["audit_trace"]["events"][3]["metadata"]["stop_reason"] == (
        "pending_owner_response"
    )
    assert payload["metadata"] == {
        "agent_loop_version": AGENT_LOOP_VERSION,
        "execution_mode": EXECUTION_MODE,
        "as_of": "2026-06-21",
        "max_iterations": 3,
        "uses_learned_feedback": False,
        "reliability_default_count": 0,
        "feedback_event_count": 0,
        "source_outcome_count": 0,
    }
    assert payload["state"]["metadata"] == payload["metadata"]


def test_run_agent_applies_feedback_snapshot_to_initial_decision_and_audit() -> None:
    bundle = load_source_bundle("fixtures/bundles/acme_auto_handoff.json")
    reliability_defaults = {
        "source_system:salesforce": 0.05,
        "source_type:crm_note": 0.81,
    }

    result = run_agent(
        bundle,
        as_of=date(2026, 6, 21),
        reliability_defaults=reliability_defaults,
        feedback_metadata={
            "feedback_event_count": 1,
            "source_outcome_count": 1,
            "policy": "conservative_feedback_v1",
        },
    )
    payload = result.model_dump(mode="json")
    ranked_crm = next(
        source
        for source in payload["initial_decision"]["ranked_bundle"]["ranked_sources"]
        if source["source_id"] == "src_acme_recent_crm_note"
    )
    feedback_event = payload["audit_trace"]["events"][1]

    assert ranked_crm["scores"]["historical_reliability"]["score"] == 0.86
    assert ranked_crm["scores"]["historical_reliability"]["metadata"][
        "uses_learned_feedback"
    ] is True
    assert payload["metadata"]["uses_learned_feedback"] is True
    assert payload["metadata"]["reliability_default_count"] == 2
    assert payload["metadata"]["feedback_event_count"] == 1
    assert [event["event_type"] for event in payload["audit_trace"]["events"]] == [
        "bundle_loaded",
        "feedback_snapshot_applied",
        "sources_ranked",
        "decision_recorded",
        "action_selected",
    ]
    assert feedback_event["action_type"] == "record_feedback"
    assert feedback_event["metadata"]["reliability_defaults"] == reliability_defaults
    assert feedback_event["metadata"]["feedback_policy"] == "conservative_feedback_v1"


def test_run_agent_preserves_feedback_defaults_across_simulated_retrieval_rerun() -> None:
    fixture = load_simulated_retrieval_fixture(
        "fixtures/simulated_retrieval/gammahealth_retrieves_validated_context.json"
    )
    retrieved_sources = load_simulated_retrieval_sources(
        "fixtures/simulated_retrieval/gammahealth_retrieves_validated_context.json"
    )
    bundle = load_source_bundle("fixtures/bundles/gamma_blocked.json")

    result = run_agent(
        bundle,
        as_of=date.fromisoformat(fixture.as_of or "2026-06-21"),
        simulated_retrieval=fixture,
        retrieved_sources=retrieved_sources,
        reliability_defaults={"source_system:human": 0.08},
        feedback_metadata={
            "feedback_event_count": 3,
            "source_outcome_count": 7,
        },
    )
    payload = result.model_dump(mode="json")
    retrieved_ranked = next(
        source
        for source in payload["final_decision"]["ranked_bundle"]["ranked_sources"]
        if source["source_id"] == "src_gammahealth_human_validated_context"
    )
    reliability = retrieved_ranked["scores"]["historical_reliability"]

    assert payload["final_decision"]["decision"] == "auto_handoff"
    assert payload["metadata"]["execution_mode"] == "simulated_retrieval_rerun"
    assert payload["metadata"]["uses_learned_feedback"] is True
    assert payload["metadata"]["feedback_event_count"] == 3
    assert reliability["score"] == 0.98
    assert reliability["metadata"]["system_modifier_source"] == "override"
    assert reliability["metadata"]["uses_learned_feedback"] is True


def test_run_agent_uses_agent_result_wrapper_without_parallel_decision_shape() -> None:
    bundle = load_source_bundle("fixtures/bundles/acme_auto_handoff.json")

    result = run_agent(bundle)
    payload = result.model_dump(mode="json")

    assert payload["initial_decision"]["decision"] == "auto_handoff"
    assert payload["final_decision"] == payload["initial_decision"]
    assert payload["state"]["final_decision"] == payload["initial_decision"]
    assert "decision" not in payload["state"]
    assert payload["steps"][0]["action"]["type"] == "stop_auto_handoff"
    assert payload["steps"][0]["input_summary"]["next_action_type"] == "prepare_handoff"
    assert payload["stop_reason"] == "final_decision_ready"


def test_run_agent_initial_stop_reason_matches_pending_user_review() -> None:
    bundle = load_source_bundle("fixtures/bundles/northstar_similar_client_review.json")

    result = run_agent(bundle)
    payload = result.model_dump(mode="json")

    assert payload["initial_decision"]["decision"] == "needs_user_review"
    assert payload["state"]["pending_approval_prompt"] is not None
    assert payload["state"]["pending_context_request"] is None
    assert payload["steps"][0]["action"]["type"] == "ask_user_review"
    assert payload["steps"][0]["action"]["metadata"]["approval_prompt_issue_type"] == (
        payload["state"]["pending_approval_prompt"]["issue_type"]
    )
    assert payload["stop_reason"] == "pending_user_review"


def test_run_agent_initial_stop_reason_matches_blocked_decision() -> None:
    bundle = load_source_bundle("fixtures/bundles/gamma_blocked.json")

    result = run_agent(bundle)
    payload = result.model_dump(mode="json")

    assert payload["initial_decision"]["decision"] == "blocked"
    assert payload["state"]["pending_approval_prompt"] is None
    assert payload["state"]["pending_context_request"] is None
    assert payload["steps"][0]["action"]["type"] == "stop_blocked"
    assert payload["steps"][0]["input_summary"]["next_action_type"] == "stop"
    assert payload["stop_reason"] == "blocked_no_reliable_path"


def test_run_agent_rejects_invalid_max_iterations() -> None:
    bundle = load_source_bundle("fixtures/bundles/acme_auto_handoff.json")

    with pytest.raises(ValueError, match="max_iterations must be at least 1"):
        run_agent(bundle, max_iterations=0)


def test_run_agent_allows_first_selected_action_at_max_iterations_one() -> None:
    bundle = load_source_bundle("fixtures/bundles/beta_needs_owner_validation.json")

    result = run_agent(bundle, max_iterations=1)

    assert result.state.iteration_count == 1
    assert result.stop_reason is StopReason.PENDING_OWNER_RESPONSE


def test_run_agent_applies_owner_response_and_reruns_decision() -> None:
    fixture = load_owner_response_fixture(
        "fixtures/owner_responses/beta_lina_validates_old_proposal.json"
    )
    bundle = load_source_bundle(fixture.bundle_path)

    result = run_agent(
        bundle,
        as_of=date.fromisoformat(fixture.as_of or "2026-06-21"),
        owner_response=fixture.response,
    )
    payload = result.model_dump(mode="json")

    assert payload["initial_decision"]["decision"] == "generate_context_request"
    assert payload["final_decision"]["decision"] == "auto_handoff"
    assert payload["stop_reason"] == "final_decision_ready"
    assert payload["metadata"]["execution_mode"] == "owner_response_rerun"
    assert payload["state"]["metadata"] == payload["metadata"]
    assert payload["state"]["owner_response_result"]["accepted"] is True
    assert payload["state"]["owner_responses"][0]["source_id"] == (
        "src_betaworks_old_proposal_with_owner"
    )
    assert [step["action"]["type"] for step in payload["steps"]] == [
        "ask_owner",
        "apply_owner_response",
        "stop_auto_handoff",
    ]
    assert [step["sequence"] for step in payload["steps"]] == [1, 2, 3]
    assert payload["steps"][1]["output_summary"] == {
        "state_changed": True,
        "stop_reason": "pending_owner_response",
    }
    assert payload["steps"][2]["input_summary"] == {
        "decision": "auto_handoff",
        "next_action_type": "prepare_handoff",
    }
    assert [event["event_type"] for event in payload["audit_trace"]["events"]] == [
        "bundle_loaded",
        "sources_ranked",
        "decision_recorded",
        "action_selected",
        "owner_response_applied",
        "decision_recorded",
        "action_selected",
    ]
    assert payload["audit_trace"]["events"][5]["metadata"] == {
        "decision": "auto_handoff"
    }

    validated_source = next(
        source
        for source in payload["state"]["current_sources"]
        if source["id"] == "src_betaworks_old_proposal_with_owner"
    )
    assert validated_source["validation_history"][0]["validated_at"] == "2026-06-21"
    assert validated_source["validation_history"][0]["outcome"] == "accepted"


def test_run_agent_records_rejected_owner_response_without_rerun() -> None:
    fixture = load_owner_response_fixture(
        "fixtures/owner_responses/beta_lina_validates_old_proposal.json"
    )
    bundle = load_source_bundle(fixture.bundle_path)
    response = fixture.response.model_copy(update={"owner_id": "user_wrong"})

    result = run_agent(
        bundle,
        as_of=date.fromisoformat(fixture.as_of or "2026-06-21"),
        owner_response=response,
    )
    payload = result.model_dump(mode="json")

    assert payload["initial_decision"]["decision"] == "generate_context_request"
    assert payload["final_decision"]["decision"] == "generate_context_request"
    assert payload["stop_reason"] == "pending_owner_response"
    assert payload["metadata"]["execution_mode"] == "owner_response_rejected"
    assert payload["state"]["owner_response_result"]["accepted"] is False
    assert payload["state"]["owner_response_result"]["validation_errors"] == [
        "Owner response owner_id and owner_name do not match a source owner candidate."
    ]
    assert [step["action"]["type"] for step in payload["steps"]] == [
        "ask_owner",
        "apply_owner_response",
    ]
    assert payload["steps"][1]["output_summary"] == {
        "state_changed": False,
        "stop_reason": "pending_owner_response",
    }
    assert payload["audit_trace"]["events"][-1]["event_type"] == "owner_response_rejected"


def test_run_agent_records_owner_response_not_applicable() -> None:
    fixture = load_owner_response_fixture(
        "fixtures/owner_responses/beta_lina_validates_old_proposal.json"
    )
    bundle = load_source_bundle("fixtures/bundles/acme_auto_handoff.json")

    result = run_agent(
        bundle,
        as_of=date.fromisoformat(fixture.as_of or "2026-06-21"),
        owner_response=fixture.response,
    )
    payload = result.model_dump(mode="json")

    assert payload["initial_decision"]["decision"] == "auto_handoff"
    assert payload["final_decision"]["decision"] == "auto_handoff"
    assert payload["stop_reason"] == "final_decision_ready"
    assert payload["metadata"]["execution_mode"] == "owner_response_rejected"
    assert payload["state"]["owner_response_result"] is None
    assert [step["action"]["type"] for step in payload["steps"]] == [
        "stop_auto_handoff",
        "apply_owner_response",
    ]
    assert payload["steps"][1]["action"]["metadata"]["reason"] == (
        "owner_response_not_applicable"
    )
    assert payload["audit_trace"]["events"][-1]["event_type"] == "owner_response_rejected"


def test_run_agent_applies_simulated_retrieval_and_reruns_decision() -> None:
    fixture = load_simulated_retrieval_fixture(
        "fixtures/simulated_retrieval/gammahealth_retrieves_validated_context.json"
    )
    retrieved_sources = load_simulated_retrieval_sources(
        "fixtures/simulated_retrieval/gammahealth_retrieves_validated_context.json"
    )
    bundle = load_source_bundle("fixtures/bundles/gamma_blocked.json")

    result = run_agent(
        bundle,
        as_of=date.fromisoformat(fixture.as_of or "2026-06-21"),
        simulated_retrieval=fixture,
        retrieved_sources=retrieved_sources,
    )
    payload = result.model_dump(mode="json")

    assert payload["initial_decision"]["decision"] == "blocked"
    assert payload["final_decision"]["decision"] == "auto_handoff"
    assert payload["stop_reason"] == "final_decision_ready"
    assert payload["metadata"]["execution_mode"] == "simulated_retrieval_rerun"
    assert payload["state"]["metadata"] == payload["metadata"]
    assert payload["state"]["simulated_retrieval_result"]["accepted"] is True
    assert payload["state"]["simulated_retrieval_result"]["added_source_ids"] == [
        "src_gammahealth_human_validated_context"
    ]
    assert [source["id"] for source in payload["state"]["current_sources"]] == [
        "src_gammahealth_vague_crm_note",
        "src_gammahealth_old_generic_deck",
        "src_gammahealth_human_validated_context",
    ]
    assert [step["action"]["type"] for step in payload["steps"]] == [
        "stop_blocked",
        "retrieve_more_context",
        "stop_auto_handoff",
    ]
    assert payload["steps"][1]["output_summary"] == {
        "state_changed": True,
        "stop_reason": "blocked_no_reliable_path",
    }
    assert [event["event_type"] for event in payload["audit_trace"]["events"]] == [
        "bundle_loaded",
        "sources_ranked",
        "decision_recorded",
        "action_selected",
        "simulated_retrieval_applied",
        "decision_recorded",
        "action_selected",
    ]
    assert payload["audit_trace"]["events"][5]["metadata"] == {
        "decision": "auto_handoff"
    }


def test_run_agent_simulated_retrieval_rerun_respects_max_iterations() -> None:
    fixture = load_simulated_retrieval_fixture(
        "fixtures/simulated_retrieval/gammahealth_retrieves_validated_context.json"
    )
    bundle = load_source_bundle("fixtures/bundles/gamma_blocked.json")

    result = run_agent(
        bundle,
        as_of=date.fromisoformat(fixture.as_of or "2026-06-21"),
        max_iterations=2,
        simulated_retrieval=fixture,
        retrieved_sources=load_simulated_retrieval_sources(
            "fixtures/simulated_retrieval/gammahealth_retrieves_validated_context.json"
        ),
    )

    assert result.final_decision.decision.value == "auto_handoff"
    assert result.stop_reason is StopReason.MAX_ITERATIONS_REACHED
    assert [step.action.type.value for step in result.steps] == [
        "stop_blocked",
        "retrieve_more_context",
        "stop_auto_handoff",
    ]
    assert result.steps[-1].stop_reason is StopReason.MAX_ITERATIONS_REACHED


def test_run_agent_no_hit_simulated_retrieval_remains_blocked() -> None:
    fixture = load_simulated_retrieval_fixture(
        "fixtures/simulated_retrieval/gammahealth_no_retrieval_hit.json"
    )
    bundle = load_source_bundle("fixtures/bundles/gamma_blocked.json")

    result = run_agent(
        bundle,
        as_of=date.fromisoformat(fixture.as_of or "2026-06-21"),
        simulated_retrieval=fixture,
        retrieved_sources=load_simulated_retrieval_sources(
            "fixtures/simulated_retrieval/gammahealth_no_retrieval_hit.json"
        ),
    )
    payload = result.model_dump(mode="json")

    assert payload["initial_decision"]["decision"] == "blocked"
    assert payload["final_decision"]["decision"] == "blocked"
    assert payload["stop_reason"] == "blocked_no_reliable_path"
    assert payload["metadata"]["execution_mode"] == "simulated_retrieval_rerun"
    assert payload["state"]["simulated_retrieval_result"]["accepted"] is True
    assert payload["state"]["simulated_retrieval_result"]["added_source_ids"] == []
    assert payload["state"]["simulated_retrieval_result"]["applied_effects"] == [
        "retrieval_fixture_validated",
        "no_new_sources",
    ]
    assert [step["action"]["type"] for step in payload["steps"]] == [
        "stop_blocked",
        "retrieve_more_context",
    ]
    assert payload["steps"][1]["output_summary"] == {
        "state_changed": False,
        "stop_reason": "blocked_no_reliable_path",
    }
    assert [event["event_type"] for event in payload["audit_trace"]["events"]] == [
        "bundle_loaded",
        "sources_ranked",
        "decision_recorded",
        "action_selected",
        "simulated_retrieval_applied",
    ]


def test_run_agent_rejects_combined_owner_response_and_simulated_retrieval() -> None:
    owner_fixture = load_owner_response_fixture(
        "fixtures/owner_responses/beta_lina_validates_old_proposal.json"
    )
    retrieval_fixture = load_simulated_retrieval_fixture(
        "fixtures/simulated_retrieval/gammahealth_retrieves_validated_context.json"
    )
    bundle = load_source_bundle("fixtures/bundles/beta_needs_owner_validation.json")

    with pytest.raises(ValueError, match="cannot be combined"):
        run_agent(
            bundle,
            owner_response=owner_fixture.response,
            simulated_retrieval=retrieval_fixture,
            retrieved_sources=[],
        )


def test_run_agent_requires_sources_with_simulated_retrieval() -> None:
    fixture = load_simulated_retrieval_fixture(
        "fixtures/simulated_retrieval/gammahealth_retrieves_validated_context.json"
    )
    bundle = load_source_bundle("fixtures/bundles/gamma_blocked.json")

    with pytest.raises(ValueError, match="retrieved_sources are required"):
        run_agent(bundle, simulated_retrieval=fixture)


def test_run_agent_owner_response_rerun_respects_max_iterations() -> None:
    fixture = load_owner_response_fixture(
        "fixtures/owner_responses/beta_lina_validates_old_proposal.json"
    )
    bundle = load_source_bundle(fixture.bundle_path)

    result = run_agent(
        bundle,
        as_of=date.fromisoformat(fixture.as_of or "2026-06-21"),
        max_iterations=2,
        owner_response=fixture.response,
    )

    assert result.final_decision.decision.value == "auto_handoff"
    assert result.stop_reason is StopReason.MAX_ITERATIONS_REACHED
    assert [step.action.type.value for step in result.steps] == [
        "ask_owner",
        "apply_owner_response",
        "stop_auto_handoff",
    ]
    assert result.steps[-1].stop_reason is StopReason.MAX_ITERATIONS_REACHED


def test_guarded_stop_reason_blocks_future_step_after_max_iterations() -> None:
    bundle = load_source_bundle("fixtures/bundles/acme_auto_handoff.json")
    result = run_agent(bundle, max_iterations=1)
    action = result.steps[0].action

    stop_reason = _guarded_stop_reason(
        result.state,
        action,
        StopReason.FINAL_DECISION_READY,
        max_iterations=1,
    )

    assert stop_reason is StopReason.MAX_ITERATIONS_REACHED


def test_guarded_stop_reason_detects_repeated_action_signature() -> None:
    bundle = load_source_bundle("fixtures/bundles/northstar_similar_client_review.json")
    result = run_agent(bundle, max_iterations=3)
    repeated_action = result.steps[0].action.model_copy(
        update={
            "label": "Ask user again",
            "reason": "The label changed, but the action targets stayed the same.",
            "metadata": {"changed": "yes"},
        }
    )

    stop_reason = _guarded_stop_reason(
        result.state,
        repeated_action,
        StopReason.PENDING_USER_REVIEW,
        max_iterations=3,
    )

    assert stop_reason is StopReason.REPEATED_ACTION_DETECTED


def test_guarded_stop_reason_preserves_pending_owner_question() -> None:
    bundle = load_source_bundle("fixtures/bundles/beta_needs_owner_validation.json")
    result = run_agent(bundle, max_iterations=3)
    state_without_steps = result.state.model_copy(
        update={
            "iteration_count": 1,
            "steps": [],
        }
    )

    stop_reason = _guarded_stop_reason(
        state_without_steps,
        result.steps[0].action,
        StopReason.FINAL_DECISION_READY,
        max_iterations=3,
    )

    assert stop_reason is StopReason.PENDING_OWNER_RESPONSE


def test_action_signature_uses_type_sources_and_claims_only() -> None:
    first = LoopAction(
        type="ask_user_review",
        label="Ask user",
        reason="Review is needed.",
        source_ids=["source_b", "source_a"],
        claim_ids=["claim_b", "claim_a"],
        metadata={"question": "Should we use this?"},
    )
    second = LoopAction(
        type="ask_user_review",
        label="Ask reviewer",
        reason="A different label does not change the action target.",
        source_ids=["source_a", "source_b"],
        claim_ids=["claim_a", "claim_b"],
        metadata={"question": "Different wording."},
    )

    assert _action_signature(first) == _action_signature(second)
    assert _action_signature(first) == (
        "ask_user_review",
        ("source_a", "source_b"),
        ("claim_a", "claim_b"),
    )
