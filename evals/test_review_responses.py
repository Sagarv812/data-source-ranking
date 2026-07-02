from __future__ import annotations

import pytest
from pydantic import ValidationError

from data_source_ranking.decision_engine import decide
from data_source_ranking.loader import load_source_bundle
from data_source_ranking.models import DecisionType
from data_source_ranking.prompts import (
    CHOOSE_OWNER,
    EXCLUDE_SENSITIVE_SOURCE,
    OLD_PROPOSAL,
    REMOVE_CLAIM,
    REQUEST_VALIDATION,
    SENSITIVE_EVIDENCE_OVERLAP,
    SIMILAR_CLIENT_DIRECTIONAL_CONTEXT,
    SKIP_SOURCE,
    STOP_AUTOMATION,
    UNCLEAR_OWNER,
    UNSUPPORTED_CLAIM,
    USE_CAUTIOUS_WORDING,
    USE_DIRECTIONAL_WITH_LABEL,
    USE_HISTORICAL_CONTEXT,
    USE_WITHOUT_OWNER,
)
from data_source_ranking.review_responses import (
    ReviewResponse,
    ReviewResponseStatus,
    apply_review_response,
    validate_review_response,
)


def test_validate_review_response_accepts_prompt_choice() -> None:
    decision = decide(load_source_bundle("fixtures/bundles/northstar_similar_client_review.json"))
    response = ReviewResponse(
        bundle_id=decision.bundle_id,
        prompt_issue_type=SIMILAR_CLIENT_DIRECTIONAL_CONTEXT,
        selected_choice_id=USE_DIRECTIONAL_WITH_LABEL,
        responder_id="user_priya",
        responder_name="Priya Shah",
    )

    result = validate_review_response(decision, response)

    assert result.accepted is True
    assert result.status is ReviewResponseStatus.ACCEPTED
    assert result.original_decision == decision
    assert result.updated_decision is None
    assert result.validation_errors == []
    assert result.applied_effects == [
        "response_validated",
        f"choice:{USE_DIRECTIONAL_WITH_LABEL}",
    ]
    assert result.audit_events[0].event == "review_response_validated"
    assert result.metadata == {
        "validation_only": True,
        "decision": "needs_user_review",
        "has_approval_prompt": True,
    }


def test_apply_review_response_records_directional_caveat() -> None:
    decision = decide(load_source_bundle("fixtures/bundles/northstar_similar_client_review.json"))
    response = ReviewResponse(
        bundle_id=decision.bundle_id,
        prompt_issue_type=SIMILAR_CLIENT_DIRECTIONAL_CONTEXT,
        selected_choice_id=USE_DIRECTIONAL_WITH_LABEL,
    )

    result = apply_review_response(decision, response)

    assert result.accepted is True
    assert result.updated_decision is not None
    assert result.applied_effects == [
        "response_validated",
        f"choice:{USE_DIRECTIONAL_WITH_LABEL}",
        "caveat_accepted",
    ]
    assert result.metadata["validation_only"] is False
    assert result.metadata["affected_source_ids"] == [
        "src_northstar_similar_client_proposal"
    ]
    assert result.metadata["accepted_caveat"] == "similar_client_directional_context"
    assert result.metadata["next_step"] == "rerun_decision"
    assert result.updated_decision.decision is DecisionType.NEEDS_USER_REVIEW
    assert result.updated_decision.approval_prompt is None
    assert result.updated_decision.selected_claims == decision.selected_claims
    assert result.updated_decision.selected_sources == decision.selected_sources
    assert result.updated_decision.source_citations == decision.source_citations
    assert result.updated_decision.next_action.type.value == "manual_review"
    assert result.updated_decision.next_action.metadata == {
        "review_response_choice": USE_DIRECTIONAL_WITH_LABEL,
        "review_response_applied": True,
        "next_step": "rerun_decision",
        "accepted_caveat": "similar_client_directional_context",
    }
    assert result.updated_decision.metadata["review_response_applied"] is True
    assert result.updated_decision.metadata["accepted_caveat"] == (
        "similar_client_directional_context"
    )
    assert [event.event for event in result.audit_events] == [
        "review_response_validated",
        "review_response_applied",
    ]


def test_validate_review_response_rejects_invalid_choice() -> None:
    decision = decide(load_source_bundle("fixtures/bundles/northstar_similar_client_review.json"))
    response = ReviewResponse(
        bundle_id=decision.bundle_id,
        prompt_issue_type=SIMILAR_CLIENT_DIRECTIONAL_CONTEXT,
        selected_choice_id="approve_everything",
    )

    result = validate_review_response(decision, response)

    assert result.accepted is False
    assert result.status is ReviewResponseStatus.REJECTED
    assert result.applied_effects == []
    assert result.validation_errors == [
        "Response selected_choice_id is not valid for the approval prompt."
    ]
    assert result.audit_events[0].event == "review_response_rejected"


def test_apply_review_response_returns_rejection_when_invalid() -> None:
    decision = decide(load_source_bundle("fixtures/bundles/northstar_similar_client_review.json"))
    response = ReviewResponse(
        bundle_id=decision.bundle_id,
        prompt_issue_type=SIMILAR_CLIENT_DIRECTIONAL_CONTEXT,
        selected_choice_id="approve_everything",
    )

    result = apply_review_response(decision, response)

    assert result.accepted is False
    assert result.updated_decision is None
    assert result.applied_effects == []
    assert result.audit_events[0].event == "review_response_rejected"
    assert result.metadata["validation_only"] is True


def test_validate_review_response_rejects_bundle_mismatch() -> None:
    decision = decide(load_source_bundle("fixtures/bundles/northstar_similar_client_review.json"))
    response = ReviewResponse(
        bundle_id="other_bundle",
        prompt_issue_type=SIMILAR_CLIENT_DIRECTIONAL_CONTEXT,
        selected_choice_id=USE_DIRECTIONAL_WITH_LABEL,
    )

    result = validate_review_response(decision, response)

    assert result.accepted is False
    assert result.validation_errors == [
        "Response bundle_id does not match the decision bundle_id."
    ]


def test_validate_review_response_rejects_prompt_type_mismatch() -> None:
    decision = decide(load_source_bundle("fixtures/bundles/northstar_similar_client_review.json"))
    response = ReviewResponse(
        bundle_id=decision.bundle_id,
        prompt_issue_type=UNCLEAR_OWNER,
        selected_choice_id=USE_DIRECTIONAL_WITH_LABEL,
    )

    result = validate_review_response(decision, response)

    assert result.accepted is False
    assert result.validation_errors == [
        "Response prompt_issue_type does not match the approval prompt."
    ]


def test_validate_review_response_requires_owner_for_choose_owner() -> None:
    decision = decide(load_source_bundle("fixtures/bundles/gammahealth_unclear_owner_review.json"))
    response = ReviewResponse(
        bundle_id=decision.bundle_id,
        prompt_issue_type=UNCLEAR_OWNER,
        selected_choice_id=CHOOSE_OWNER,
    )

    result = validate_review_response(decision, response)

    assert result.accepted is False
    assert result.validation_errors == [
        "Choosing an owner requires selected_owner_id and selected_owner_name."
    ]


def test_validate_review_response_accepts_owner_selection() -> None:
    decision = decide(load_source_bundle("fixtures/bundles/gammahealth_unclear_owner_review.json"))
    response = ReviewResponse(
        bundle_id=decision.bundle_id,
        prompt_issue_type=UNCLEAR_OWNER,
        selected_choice_id=CHOOSE_OWNER,
        selected_owner_id="user_priya",
        selected_owner_name="Priya Shah",
    )

    result = validate_review_response(decision, response)

    assert result.accepted is True
    assert result.applied_effects == [
        "response_validated",
        f"choice:{CHOOSE_OWNER}",
        "owner_selected",
    ]


def test_apply_review_response_records_owner_selection() -> None:
    decision = decide(load_source_bundle("fixtures/bundles/gammahealth_unclear_owner_review.json"))
    response = ReviewResponse(
        bundle_id=decision.bundle_id,
        prompt_issue_type=UNCLEAR_OWNER,
        selected_choice_id=CHOOSE_OWNER,
        selected_owner_id="user_priya",
        selected_owner_name="Priya Shah",
    )

    result = apply_review_response(decision, response)

    assert result.accepted is True
    assert result.applied_effects == [
        "response_validated",
        f"choice:{CHOOSE_OWNER}",
        "owner_selected",
    ]
    assert result.metadata["selected_owner"] == {
        "id": "user_priya",
        "name": "Priya Shah",
    }
    assert result.metadata["validation_source_ids"] == [
        "src_gammahealth_useful_document_unclear_owner"
    ]
    assert result.metadata["next_step"] == "rerun_decision"
    assert result.updated_decision is not None
    assert result.updated_decision.decision is DecisionType.GENERATE_CONTEXT_REQUEST
    assert result.updated_decision.summary == (
        "User selected an owner for validation before automation continues."
    )
    assert result.updated_decision.confidence.score == 0.74
    assert result.updated_decision.confidence.reasons == [
        "User selected an owner who can validate the source before automation."
    ]
    assert result.updated_decision.approval_prompt is None
    assert result.updated_decision.draft_handoff is None
    assert result.updated_decision.blocked_output is None
    assert result.updated_decision.selected_sources == [
        "src_gammahealth_useful_document_unclear_owner"
    ]
    assert result.updated_decision.context_request is not None
    assert result.updated_decision.context_request.recipient_id == "user_priya"
    assert result.updated_decision.context_request.recipient_name == "Priya Shah"
    assert result.updated_decision.context_request.recipient_reason == (
        "User selected this owner during review."
    )
    assert result.updated_decision.context_request.question == (
        "Can you validate whether 'GammaHealth referral intake workflow notes' can be "
        "used for this automation context?"
    )
    assert result.updated_decision.context_request.source_ids == [
        "src_gammahealth_useful_document_unclear_owner"
    ]
    assert result.updated_decision.next_action.type.value == "ask_owner"
    assert result.updated_decision.next_action.owner_id == "user_priya"
    assert result.updated_decision.next_action.owner_name == "Priya Shah"
    assert result.updated_decision.next_action.question == (
        result.updated_decision.context_request.question
    )
    assert result.updated_decision.next_action.metadata == {
        "review_response_choice": CHOOSE_OWNER,
        "selected_owner": {"id": "user_priya", "name": "Priya Shah"},
        "requires_owner_validation": True,
    }
    assert result.updated_decision.metadata["updated_from_decision"] == "needs_user_review"
    assert result.updated_decision.metadata["review_response_choice"] == CHOOSE_OWNER
    assert result.updated_decision.metadata["selected_owner"] == {
        "id": "user_priya",
        "name": "Priya Shah",
    }
    assert result.updated_decision.metadata["requires_owner_validation"] is True
    assert result.updated_decision.audit_trace[-1].event == "review_response_updated_decision"


def test_validate_review_response_requires_risk_acceptance_for_override() -> None:
    decision = decide(load_source_bundle("fixtures/bundles/gammahealth_unclear_owner_review.json"))
    response = ReviewResponse(
        bundle_id=decision.bundle_id,
        prompt_issue_type=UNCLEAR_OWNER,
        selected_choice_id=USE_WITHOUT_OWNER,
    )

    result = validate_review_response(decision, response)

    assert result.accepted is False
    assert result.validation_errors == [
        "This choice requires explicit user risk acceptance."
    ]


def test_validate_review_response_accepts_explicit_risk_acceptance() -> None:
    decision = decide(load_source_bundle("fixtures/bundles/gammahealth_unclear_owner_review.json"))
    response = ReviewResponse(
        bundle_id=decision.bundle_id,
        prompt_issue_type=UNCLEAR_OWNER,
        selected_choice_id=USE_WITHOUT_OWNER,
        user_accepts_risk=True,
        notes="Use only as internal directional context.",
    )

    result = validate_review_response(decision, response)

    assert result.accepted is True
    assert result.applied_effects == [
        "response_validated",
        f"choice:{USE_WITHOUT_OWNER}",
        "risk_accepted",
    ]


def test_apply_review_response_records_accepted_risk() -> None:
    decision = decide(load_source_bundle("fixtures/bundles/gammahealth_unclear_owner_review.json"))
    response = ReviewResponse(
        bundle_id=decision.bundle_id,
        prompt_issue_type=UNCLEAR_OWNER,
        selected_choice_id=USE_WITHOUT_OWNER,
        user_accepts_risk=True,
    )

    result = apply_review_response(decision, response)

    assert result.accepted is True
    assert result.applied_effects == [
        "response_validated",
        f"choice:{USE_WITHOUT_OWNER}",
        "risk_accepted",
        "caveat_accepted",
    ]
    assert result.metadata["accepted_risk"] == "owner_unvalidated"
    assert result.metadata["accepted_caveat"] == "owner_unvalidated"
    assert result.metadata["user_accepts_risk"] is True
    assert result.updated_decision is not None
    assert result.updated_decision.decision is DecisionType.NEEDS_USER_REVIEW
    assert result.updated_decision.approval_prompt is None
    assert result.updated_decision.selected_claims == decision.selected_claims
    assert result.updated_decision.selected_sources == decision.selected_sources
    assert result.updated_decision.next_action.type.value == "manual_review"
    assert result.updated_decision.next_action.metadata == {
        "review_response_choice": USE_WITHOUT_OWNER,
        "review_response_applied": True,
        "next_step": "rerun_decision",
        "accepted_caveat": "owner_unvalidated",
        "accepted_risk": "owner_unvalidated",
        "user_accepts_risk": True,
    }
    assert result.updated_decision.metadata["accepted_risk"] == "owner_unvalidated"
    assert result.updated_decision.metadata["accepted_caveat"] == "owner_unvalidated"


def test_apply_review_response_records_sensitive_source_exclusion() -> None:
    decision = decide(load_source_bundle("fixtures/bundles/delta_contradictory_sources.json"))
    response = ReviewResponse(
        bundle_id=decision.bundle_id,
        prompt_issue_type=SENSITIVE_EVIDENCE_OVERLAP,
        selected_choice_id=EXCLUDE_SENSITIVE_SOURCE,
    )

    result = apply_review_response(decision, response)

    assert result.accepted is True
    assert result.applied_effects == [
        "response_validated",
        f"choice:{EXCLUDE_SENSITIVE_SOURCE}",
        "source_excluded",
    ]
    assert result.metadata["excluded_source_ids"] == [
        "src_deltabank_unverified_partner_material"
    ]
    assert result.metadata["next_step"] == "rerun_decision"
    assert result.updated_decision is not None
    assert result.updated_decision.decision is DecisionType.NEEDS_USER_REVIEW
    assert result.updated_decision.approval_prompt is None
    assert result.updated_decision.blocked_output is None
    assert result.updated_decision.selected_sources == [
        "src_deltabank_recent_meeting_notes_clear_attendees"
    ]
    assert [
        citation.source_id for citation in result.updated_decision.source_citations
    ] == [
        "src_deltabank_recent_meeting_notes_clear_attendees",
        "src_deltabank_recent_meeting_notes_clear_attendees",
    ]
    assert result.updated_decision.next_action.type.value == "manual_review"
    assert result.updated_decision.next_action.metadata == {
        "review_response_choice": EXCLUDE_SENSITIVE_SOURCE,
        "review_response_applied": True,
        "next_step": "rerun_decision",
    }
    assert result.updated_decision.metadata["review_response_applied"] is True
    assert result.updated_decision.metadata["excluded_source_ids"] == [
        "src_deltabank_unverified_partner_material"
    ]
    assert result.updated_decision.audit_trace[-1].event == (
        "review_response_updated_decision"
    )


def test_apply_review_response_records_validation_request_intent() -> None:
    decision = decide(load_source_bundle("fixtures/bundles/delta_contradictory_sources.json"))
    response = ReviewResponse(
        bundle_id=decision.bundle_id,
        prompt_issue_type=SENSITIVE_EVIDENCE_OVERLAP,
        selected_choice_id=REQUEST_VALIDATION,
    )

    result = apply_review_response(decision, response)

    assert result.accepted is True
    assert result.applied_effects == [
        "response_validated",
        f"choice:{REQUEST_VALIDATION}",
        "validation_requested",
    ]
    assert result.metadata["validation_source_ids"] == [
        "src_deltabank_unverified_partner_material"
    ]
    assert "owner_candidates" in result.metadata


def test_apply_review_response_request_validation_creates_context_request() -> None:
    decision = decide(load_source_bundle("fixtures/bundles/betaworks_old_proposal_review.json"))
    response = ReviewResponse(
        bundle_id=decision.bundle_id,
        prompt_issue_type=OLD_PROPOSAL,
        selected_choice_id=REQUEST_VALIDATION,
    )

    result = apply_review_response(decision, response)

    assert result.accepted is True
    assert result.applied_effects == [
        "response_validated",
        f"choice:{REQUEST_VALIDATION}",
        "validation_requested",
    ]
    assert result.metadata["next_step"] == "send_context_request"
    assert result.metadata["validation_owner"]["id"] == "user_lina"
    assert result.updated_decision is not None
    assert result.updated_decision.decision is DecisionType.GENERATE_CONTEXT_REQUEST
    assert result.updated_decision.summary == (
        "Review response requested owner validation before automation continues."
    )
    assert result.updated_decision.confidence.score == 0.74
    assert result.updated_decision.confidence.reasons == [
        "A responsible owner can validate the source before automation."
    ]
    assert result.updated_decision.selected_sources == [
        "src_betaworks_old_proposal_with_owner"
    ]
    assert result.updated_decision.approval_prompt is None
    assert result.updated_decision.context_request is not None
    assert result.updated_decision.context_request.recipient_id == "user_lina"
    assert result.updated_decision.context_request.recipient_name == "Lina Rao"
    assert result.updated_decision.context_request.recipient_reason == (
        "Proposal owner for the 2025 pilot proposal."
    )
    assert result.updated_decision.context_request.question == (
        "Can you validate whether this proposal still applies to the current client situation?"
    )
    assert result.updated_decision.context_request.source_ids == [
        "src_betaworks_old_proposal_with_owner"
    ]
    assert result.updated_decision.next_action.type.value == "ask_owner"
    assert result.updated_decision.next_action.owner_id == "user_lina"
    assert result.updated_decision.next_action.owner_name == "Lina Rao"
    assert result.updated_decision.next_action.question == (
        result.updated_decision.context_request.question
    )
    assert result.updated_decision.metadata["updated_from_decision"] == "needs_user_review"
    assert result.updated_decision.metadata["review_response_choice"] == REQUEST_VALIDATION
    assert result.updated_decision.metadata["requires_owner_validation"] is True
    assert result.updated_decision.audit_trace[-1].event == "review_response_updated_decision"


def test_apply_review_response_request_validation_without_owner_stays_effect_only() -> None:
    decision = decide(load_source_bundle("fixtures/bundles/betaworks_old_proposal_review.json"))
    assert decision.approval_prompt is not None
    decision = decision.model_copy(
        update={
            "approval_prompt": decision.approval_prompt.model_copy(
                update={"metadata": {**decision.approval_prompt.metadata, "owner_candidates": {}}}
            )
        }
    )
    response = ReviewResponse(
        bundle_id=decision.bundle_id,
        prompt_issue_type=OLD_PROPOSAL,
        selected_choice_id=REQUEST_VALIDATION,
    )

    result = apply_review_response(decision, response)

    assert result.accepted is True
    assert result.updated_decision is None
    assert result.metadata["missing_owner_for_validation"] is True
    assert result.metadata["next_step"] == "choose_owner"
    assert result.metadata["validation_source_ids"] == [
        "src_betaworks_old_proposal_with_owner"
    ]


def test_apply_review_response_records_stop_intent() -> None:
    decision = decide(load_source_bundle("fixtures/bundles/delta_contradictory_sources.json"))
    response = ReviewResponse(
        bundle_id=decision.bundle_id,
        prompt_issue_type=SENSITIVE_EVIDENCE_OVERLAP,
        selected_choice_id=STOP_AUTOMATION,
    )

    result = apply_review_response(decision, response)

    assert result.accepted is True
    assert result.applied_effects == [
        "response_validated",
        f"choice:{STOP_AUTOMATION}",
        "automation_stopped",
    ]
    assert result.metadata["next_step"] == "stop_automation"
    assert result.updated_decision is not None
    assert result.updated_decision.decision is DecisionType.BLOCKED
    assert result.updated_decision.summary == "Automation was stopped by user review response."
    assert result.updated_decision.confidence.score == 0.95
    assert result.updated_decision.confidence.reasons == [
        "User chose to stop automation from the approval prompt."
    ]
    assert result.updated_decision.selected_claims == []
    assert result.updated_decision.selected_sources == []
    assert result.updated_decision.source_citations == []
    assert result.updated_decision.approval_prompt is None
    assert result.updated_decision.context_request is None
    assert result.updated_decision.draft_handoff is None
    assert result.updated_decision.blocked_output is not None
    assert result.updated_decision.blocked_output.blocking_reason == (
        "User chose to stop automation during review."
    )
    assert result.updated_decision.blocked_output.sources_considered == [
        "src_deltabank_unverified_partner_material"
    ]
    assert result.updated_decision.next_action.type.value == "stop"
    assert result.updated_decision.next_action.metadata == {
        "review_response_choice": STOP_AUTOMATION,
        "user_requested_stop": True,
    }
    assert result.updated_decision.metadata["updated_from_decision"] == "needs_user_review"
    assert result.updated_decision.metadata["review_response_choice"] == STOP_AUTOMATION
    assert result.updated_decision.metadata["user_requested_stop"] is True
    assert result.updated_decision.audit_trace[-1].event == "review_response_updated_decision"


def test_apply_review_response_records_unsupported_claim_removal() -> None:
    decision = decide(load_source_bundle("fixtures/bundles/acme_unsupported_claim_review.json"))
    response = ReviewResponse(
        bundle_id=decision.bundle_id,
        prompt_issue_type=UNSUPPORTED_CLAIM,
        selected_choice_id=REMOVE_CLAIM,
    )

    result = apply_review_response(decision, response)

    assert result.accepted is True
    assert result.applied_effects == [
        "response_validated",
        f"choice:{REMOVE_CLAIM}",
        "claim_removed",
    ]
    assert result.metadata["removed_claim_ids"] == [
        "claim_acme_inferred_implementation_risk"
    ]
    assert result.metadata["affected_source_ids"] == [
        "src_acme_unsupported_inferred_claim"
    ]
    assert result.updated_decision is not None
    assert result.updated_decision.decision is DecisionType.NEEDS_USER_REVIEW
    assert result.updated_decision.approval_prompt is None
    assert result.updated_decision.blocked_output is None
    assert result.updated_decision.selected_sources == [
        "src_acme_same_client_adjacent_work"
    ]
    assert [
        claim.claim_id for claim in result.updated_decision.selected_claims
    ] == [
        "claim_acme_rollout_ownership_gap",
    ]
    assert result.updated_decision.next_action.type.value == "manual_review"
    assert result.updated_decision.metadata["review_response_applied"] is True
    assert result.updated_decision.metadata["removed_claim_ids"] == [
        "claim_acme_inferred_implementation_risk"
    ]


def test_apply_review_response_skip_source_blocks_without_selected_evidence() -> None:
    decision = decide(load_source_bundle("fixtures/bundles/northstar_similar_client_review.json"))
    response = ReviewResponse(
        bundle_id=decision.bundle_id,
        prompt_issue_type=SIMILAR_CLIENT_DIRECTIONAL_CONTEXT,
        selected_choice_id=SKIP_SOURCE,
    )

    result = apply_review_response(decision, response)

    assert result.accepted is True
    assert result.applied_effects == [
        "response_validated",
        f"choice:{SKIP_SOURCE}",
        "source_excluded",
    ]
    assert result.metadata["excluded_source_ids"] == [
        "src_northstar_similar_client_proposal"
    ]
    assert result.updated_decision is not None
    assert result.updated_decision.decision is DecisionType.BLOCKED
    assert result.updated_decision.summary == (
        "Review response excluded all selected source evidence."
    )
    assert result.updated_decision.selected_claims == []
    assert result.updated_decision.selected_sources == []
    assert result.updated_decision.source_citations == []
    assert result.updated_decision.approval_prompt is None
    assert result.updated_decision.blocked_output is not None
    assert result.updated_decision.blocked_output.blocking_reason == (
        "Review response excluded all selected source evidence."
    )
    assert result.updated_decision.blocked_output.sources_considered == [
        "src_northstar_similar_client_proposal"
    ]
    assert result.updated_decision.next_action.type.value == "stop"
    assert result.updated_decision.metadata["review_response_applied"] is True
    assert result.updated_decision.metadata["review_response_choice"] == SKIP_SOURCE


def test_apply_review_response_records_cautious_wording() -> None:
    decision = decide(load_source_bundle("fixtures/bundles/acme_unsupported_claim_review.json"))
    response = ReviewResponse(
        bundle_id=decision.bundle_id,
        prompt_issue_type=UNSUPPORTED_CLAIM,
        selected_choice_id=USE_CAUTIOUS_WORDING,
        user_accepts_risk=True,
    )

    result = apply_review_response(decision, response)

    assert result.accepted is True
    assert result.applied_effects == [
        "response_validated",
        f"choice:{USE_CAUTIOUS_WORDING}",
        "risk_accepted",
        "caveat_accepted",
    ]
    assert result.metadata["accepted_risk"] == "unsupported_inference"
    assert result.metadata["accepted_caveat"] == "unsupported_inference_cautious_wording"
    assert result.updated_decision is not None
    assert result.updated_decision.decision is DecisionType.NEEDS_USER_REVIEW
    assert result.updated_decision.approval_prompt is None
    assert result.updated_decision.selected_claims == decision.selected_claims
    assert result.updated_decision.selected_sources == decision.selected_sources
    assert result.updated_decision.next_action.type.value == "manual_review"
    assert result.updated_decision.next_action.metadata == {
        "review_response_choice": USE_CAUTIOUS_WORDING,
        "review_response_applied": True,
        "next_step": "rerun_decision",
        "accepted_caveat": "unsupported_inference_cautious_wording",
        "accepted_risk": "unsupported_inference",
        "user_accepts_risk": True,
    }
    assert result.updated_decision.metadata["accepted_risk"] == "unsupported_inference"
    assert result.updated_decision.metadata["accepted_caveat"] == (
        "unsupported_inference_cautious_wording"
    )


def test_apply_review_response_records_historical_context_caveat() -> None:
    decision = decide(load_source_bundle("fixtures/bundles/betaworks_old_proposal_review.json"))
    response = ReviewResponse(
        bundle_id=decision.bundle_id,
        prompt_issue_type=OLD_PROPOSAL,
        selected_choice_id=USE_HISTORICAL_CONTEXT,
        user_accepts_risk=True,
    )

    result = apply_review_response(decision, response)

    assert result.accepted is True
    assert result.applied_effects == [
        "response_validated",
        f"choice:{USE_HISTORICAL_CONTEXT}",
        "risk_accepted",
        "caveat_accepted",
    ]
    assert result.metadata["accepted_risk"] == "stale_proposal"
    assert result.metadata["accepted_caveat"] == "historical_context_only"
    assert result.updated_decision is not None
    assert result.updated_decision.decision is DecisionType.NEEDS_USER_REVIEW
    assert result.updated_decision.approval_prompt is None
    assert result.updated_decision.selected_claims == decision.selected_claims
    assert result.updated_decision.selected_sources == decision.selected_sources
    assert result.updated_decision.source_citations == decision.source_citations
    assert result.updated_decision.next_action.type.value == "manual_review"
    assert result.updated_decision.next_action.metadata == {
        "review_response_choice": USE_HISTORICAL_CONTEXT,
        "review_response_applied": True,
        "next_step": "rerun_decision",
        "accepted_caveat": "historical_context_only",
        "accepted_risk": "stale_proposal",
        "user_accepts_risk": True,
    }
    assert result.updated_decision.metadata["accepted_risk"] == "stale_proposal"
    assert result.updated_decision.metadata["accepted_caveat"] == "historical_context_only"


def test_validate_review_response_rejects_decision_without_prompt() -> None:
    decision = decide(load_source_bundle("fixtures/bundles/acme_auto_handoff.json"))
    response = ReviewResponse(
        bundle_id=decision.bundle_id,
        prompt_issue_type=SIMILAR_CLIENT_DIRECTIONAL_CONTEXT,
        selected_choice_id=USE_DIRECTIONAL_WITH_LABEL,
    )

    result = validate_review_response(decision, response)

    assert result.accepted is False
    assert result.validation_errors == [
        "Decision does not have an approval prompt to answer."
    ]


def test_review_response_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ReviewResponse(
            bundle_id="bundle",
            prompt_issue_type=UNCLEAR_OWNER,
            selected_choice_id=CHOOSE_OWNER,
            unexpected=True,
        )
