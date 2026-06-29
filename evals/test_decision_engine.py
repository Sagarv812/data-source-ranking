from __future__ import annotations

import pytest

from data_source_ranking.decision_engine import decide, select_final_decision
from data_source_ranking.decisions import (
    DecisionConfidenceLabel,
    NextActionType,
    PolicyGateEffect,
    PolicyGateResult,
    PolicyGateStatus,
)
from data_source_ranking.loader import load_source_bundle, load_source_fixture
from data_source_ranking.models import DecisionType, SourceBundle


def test_decide_returns_auto_handoff_decision() -> None:
    bundle = load_source_bundle("fixtures/bundles/acme_auto_handoff.json")

    decision = decide(bundle)

    assert decision.bundle_id == "bundle_acme_auto_handoff"
    assert decision.decision is DecisionType.AUTO_HANDOFF
    assert decision.confidence.label is DecisionConfidenceLabel.HIGH
    assert decision.next_action.type is NextActionType.PREPARE_HANDOFF
    assert decision.draft_handoff is not None
    assert decision.approval_prompt is None
    assert decision.context_request is None
    assert decision.selected_sources == [
        "src_acme_recent_crm_note",
        "src_acme_recent_meeting_notes_clear_attendees",
    ]
    assert {claim.needed_claim_id for claim in decision.selected_claims} == {
        "need_claim_current_concern"
    }
    assert {gate.status for gate in decision.policy_gates} == {PolicyGateStatus.PASSED}
    assert decision.metadata["decision_engine"] == "rule_based_v1"


def test_decide_returns_context_request_decision() -> None:
    bundle = load_source_bundle("fixtures/bundles/beta_needs_owner_validation.json")

    decision = decide(bundle)
    gates = {gate.gate: gate for gate in decision.policy_gates}

    assert decision.decision is DecisionType.GENERATE_CONTEXT_REQUEST
    assert decision.confidence.label is DecisionConfidenceLabel.MEDIUM
    assert decision.next_action.type is NextActionType.ASK_OWNER
    assert decision.next_action.owner_id == "user_lina"
    assert decision.next_action.owner_name == "Lina Rao"
    assert decision.next_action.question is not None
    assert decision.context_request is not None
    assert decision.context_request.recipient_id == "user_lina"
    assert decision.context_request.source_ids == ["src_betaworks_old_proposal_with_owner"]
    assert decision.selected_sources == ["src_betaworks_old_proposal_with_owner"]
    assert {claim.needed_claim_id for claim in decision.selected_claims} == {
        "need_claim_current_concern",
        "need_claim_prior_work",
    }
    assert gates["required_claims_have_strong_coverage"].status is PolicyGateStatus.TRIGGERED
    assert gates["stale_unvalidated_source_absent"].status is PolicyGateStatus.TRIGGERED


def test_decide_returns_user_review_decision() -> None:
    bundle = load_source_bundle("fixtures/bundles/delta_contradictory_sources.json")

    decision = decide(bundle)
    gates = {gate.gate: gate for gate in decision.policy_gates}

    assert decision.decision is DecisionType.NEEDS_USER_REVIEW
    assert decision.confidence.label is DecisionConfidenceLabel.MEDIUM
    assert decision.next_action.type is NextActionType.ASK_USER
    assert decision.approval_prompt is not None
    assert decision.approval_prompt.issue_type == "sensitive_evidence_overlap"
    assert decision.next_action.question == decision.approval_prompt.question
    assert decision.selected_sources == ["src_deltabank_recent_meeting_notes_clear_attendees"]
    assert {claim.needed_claim_id for claim in decision.selected_claims} == {
        "need_claim_current_concern",
        "need_claim_next_step",
    }
    assert gates["sensitivity_allows_automation"].status is PolicyGateStatus.TRIGGERED
    assert gates["sensitive_evidence_overlap_absent"].status is PolicyGateStatus.TRIGGERED
    assert decision.draft_handoff is None


def test_decide_returns_blocked_decision() -> None:
    bundle = load_source_bundle("fixtures/bundles/gamma_blocked.json")

    decision = decide(bundle)
    gates = {gate.gate: gate for gate in decision.policy_gates}

    assert decision.decision is DecisionType.BLOCKED
    assert decision.confidence.label is DecisionConfidenceLabel.HIGH
    assert decision.next_action.type is NextActionType.STOP
    assert decision.selected_claims == []
    assert decision.selected_sources == []
    assert decision.source_citations == []
    assert gates["required_claims_have_usable_coverage"].status is PolicyGateStatus.TRIGGERED
    assert gates["owner_signal_available"].status is PolicyGateStatus.TRIGGERED


def test_decide_requests_context_for_meeting_title_without_notes() -> None:
    fixture = load_source_fixture("fixtures/medium/deltabank_meeting_title_without_notes.json")
    bundle = SourceBundle(
        id="bundle_deltabank_meeting_title_probe",
        title="DeltaBank meeting title probe",
        context_need=fixture.context_need,
        sources=[fixture.source],
    )

    decision = decide(bundle)
    gates = {gate.gate: gate for gate in decision.policy_gates}

    assert decision.decision is DecisionType.GENERATE_CONTEXT_REQUEST
    assert decision.next_action.type is NextActionType.ASK_OWNER
    assert decision.context_request is not None
    assert decision.context_request.recipient_id == "user_mateo"
    assert decision.context_request.source_ids == ["src_deltabank_meeting_title_without_notes"]
    assert decision.selected_sources == ["src_deltabank_meeting_title_without_notes"]
    assert "What client concern, decision, or next step" in decision.context_request.question
    assert gates["required_claims_have_usable_coverage"].effect is (
        PolicyGateEffect.REQUIRES_CONTEXT_REQUEST
    )


def test_decide_reviews_unsupported_claim() -> None:
    bundle = load_source_bundle("fixtures/bundles/acme_unsupported_claim_review.json")

    decision = decide(bundle)
    gates = {gate.gate: gate for gate in decision.policy_gates}

    assert decision.decision is DecisionType.NEEDS_USER_REVIEW
    assert decision.next_action.type is NextActionType.ASK_USER
    assert decision.context_request is None
    assert decision.approval_prompt is not None
    assert decision.approval_prompt.issue_type == "unsupported_claim"
    assert decision.next_action.question == decision.approval_prompt.question
    assert decision.selected_sources == ["src_acme_same_client_adjacent_work"]
    assert gates["unsupported_inference_absent"].status is PolicyGateStatus.TRIGGERED
    assert gates["unsupported_inference_absent"].effect is PolicyGateEffect.REQUIRES_USER_REVIEW


def test_decide_reviews_sensitive_partner_material_without_overlap() -> None:
    bundle = load_source_bundle(
        "fixtures/bundles/deltabank_sensitive_partner_material_review.json"
    )

    decision = decide(bundle)
    gates = {gate.gate: gate for gate in decision.policy_gates}

    assert decision.decision is DecisionType.NEEDS_USER_REVIEW
    assert decision.next_action.type is NextActionType.ASK_USER
    assert decision.approval_prompt is not None
    assert decision.approval_prompt.issue_type == "sensitive_partner_material"
    assert decision.next_action.question == decision.approval_prompt.question
    assert decision.selected_sources == ["src_deltabank_recent_meeting_notes_clear_attendees"]
    assert {claim.needed_claim_id for claim in decision.selected_claims} == {
        "need_claim_next_step"
    }
    assert gates["sensitivity_allows_automation"].status is PolicyGateStatus.TRIGGERED
    assert gates["sensitive_evidence_overlap_absent"].status is PolicyGateStatus.PASSED


def test_decide_reviews_old_proposal_when_strong_required_coverage_exists() -> None:
    bundle = load_source_bundle("fixtures/bundles/betaworks_old_proposal_review.json")

    decision = decide(bundle)
    gates = {gate.gate: gate for gate in decision.policy_gates}

    assert decision.decision is DecisionType.NEEDS_USER_REVIEW
    assert decision.next_action.type is NextActionType.ASK_USER
    assert decision.context_request is None
    assert decision.approval_prompt is not None
    assert decision.approval_prompt.issue_type == "old_proposal"
    assert decision.next_action.question == decision.approval_prompt.question
    assert decision.selected_sources == [
        "src_betaworks_current_opportunity_owner_note",
        "src_betaworks_old_proposal_with_owner",
    ]
    assert gates["old_proposal_review_absent"].status is PolicyGateStatus.TRIGGERED
    assert gates["stale_unvalidated_source_absent"].status is PolicyGateStatus.PASSED


def test_decide_reviews_similar_client_directional_source() -> None:
    bundle = load_source_bundle("fixtures/bundles/northstar_similar_client_review.json")

    decision = decide(bundle)
    gates = {gate.gate: gate for gate in decision.policy_gates}

    assert decision.decision is DecisionType.NEEDS_USER_REVIEW
    assert decision.next_action.type is NextActionType.ASK_USER
    assert decision.context_request is None
    assert decision.approval_prompt is not None
    assert decision.next_action.question == decision.approval_prompt.question
    assert decision.selected_sources == ["src_northstar_similar_client_proposal"]
    assert gates["directional_context_review_absent"].status is PolicyGateStatus.TRIGGERED
    assert gates["directional_context_review_absent"].effect is (
        PolicyGateEffect.REQUIRES_USER_REVIEW
    )


def test_decide_reviews_useful_document_with_unclear_owner() -> None:
    bundle = load_source_bundle("fixtures/bundles/gammahealth_unclear_owner_review.json")

    decision = decide(bundle)
    gates = {gate.gate: gate for gate in decision.policy_gates}

    assert decision.decision is DecisionType.NEEDS_USER_REVIEW
    assert decision.next_action.type is NextActionType.ASK_USER
    assert decision.context_request is None
    assert decision.approval_prompt is not None
    assert decision.next_action.question == decision.approval_prompt.question
    assert decision.selected_sources == ["src_gammahealth_useful_document_unclear_owner"]
    assert gates["owner_signal_available"].status is PolicyGateStatus.TRIGGERED
    assert gates["owner_signal_available"].effect is PolicyGateEffect.REQUIRES_USER_REVIEW


def test_final_decision_selector_blocks_before_review() -> None:
    decision = select_final_decision(
        [
            gate(
                "required_claims_have_usable_coverage",
                PolicyGateStatus.TRIGGERED,
                PolicyGateEffect.BLOCKS_AUTOMATION,
            ),
            gate(
                "sensitive_evidence_overlap_absent",
                PolicyGateStatus.TRIGGERED,
                PolicyGateEffect.REQUIRES_USER_REVIEW,
            ),
        ]
    )

    assert decision is DecisionType.BLOCKED


def test_final_decision_selector_reviews_before_context_request() -> None:
    decision = select_final_decision(
        [
            gate("required_claims_have_usable_coverage", PolicyGateStatus.PASSED),
            gate("owner_signal_available", PolicyGateStatus.PASSED),
            gate(
                "required_claims_have_strong_coverage",
                PolicyGateStatus.TRIGGERED,
                PolicyGateEffect.PREVENTS_AUTO_HANDOFF,
            ),
            gate(
                "sensitive_evidence_overlap_absent",
                PolicyGateStatus.TRIGGERED,
                PolicyGateEffect.REQUIRES_USER_REVIEW,
            ),
        ]
    )

    assert decision is DecisionType.NEEDS_USER_REVIEW


def test_final_decision_selector_requests_context_for_usable_medium_evidence() -> None:
    decision = select_final_decision(
        [
            gate("required_claims_have_usable_coverage", PolicyGateStatus.PASSED),
            gate("owner_signal_available", PolicyGateStatus.PASSED),
            gate(
                "required_claims_have_strong_coverage",
                PolicyGateStatus.TRIGGERED,
                PolicyGateEffect.PREVENTS_AUTO_HANDOFF,
            ),
            gate(
                "stale_unvalidated_source_absent",
                PolicyGateStatus.TRIGGERED,
                PolicyGateEffect.REQUIRES_CONTEXT_REQUEST,
            ),
        ]
    )

    assert decision is DecisionType.GENERATE_CONTEXT_REQUEST


def test_final_decision_selector_auto_handoff_requires_no_triggered_gates() -> None:
    decision = select_final_decision(
        [
            gate("required_claims_have_usable_coverage", PolicyGateStatus.PASSED),
            gate(
                "required_claims_have_strong_coverage",
                PolicyGateStatus.PASSED,
                PolicyGateEffect.ALLOWS_AUTO_HANDOFF,
            ),
            gate("owner_signal_available", PolicyGateStatus.PASSED),
            gate("sensitivity_allows_automation", PolicyGateStatus.PASSED),
        ]
    )

    assert decision is DecisionType.AUTO_HANDOFF


def test_final_decision_selector_sends_unresolved_auto_prevention_to_review() -> None:
    decision = select_final_decision(
        [
            gate("required_claims_have_usable_coverage", PolicyGateStatus.PASSED),
            gate(
                "required_claims_have_strong_coverage",
                PolicyGateStatus.PASSED,
                PolicyGateEffect.ALLOWS_AUTO_HANDOFF,
            ),
            gate(
                "sensitivity_allows_automation",
                PolicyGateStatus.TRIGGERED,
                PolicyGateEffect.PREVENTS_AUTO_HANDOFF,
            ),
        ]
    )

    assert decision is DecisionType.NEEDS_USER_REVIEW


@pytest.mark.parametrize(
    "path",
    [
        "fixtures/bundles/acme_auto_handoff.json",
        "fixtures/bundles/beta_needs_owner_validation.json",
        "fixtures/bundles/delta_contradictory_sources.json",
        "fixtures/bundles/gamma_blocked.json",
    ],
)
def test_decide_output_is_json_serializable(path: str) -> None:
    bundle = load_source_bundle(path)

    payload = decide(bundle).model_dump(mode="json")

    assert set(payload) == {
        "approval_prompt",
        "audit_trace",
        "bundle_id",
        "confidence",
        "context_request",
        "decision",
        "draft_handoff",
        "metadata",
        "next_action",
        "policy_gates",
        "ranked_bundle",
        "selected_claims",
        "selected_sources",
        "source_citations",
        "summary",
        "weak_points",
    }
    assert payload["ranked_bundle"]["id"] == payload["bundle_id"]
    assert isinstance(payload["policy_gates"], list)
    assert isinstance(payload["audit_trace"], list)


def gate(
    name: str,
    status: PolicyGateStatus,
    effect: PolicyGateEffect = PolicyGateEffect.INFORMATIONAL,
) -> PolicyGateResult:
    return PolicyGateResult(
        gate=name,
        status=status,
        effect=effect,
        message=f"{name} {status.value}",
    )
