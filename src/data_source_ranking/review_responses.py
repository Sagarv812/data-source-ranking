from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from data_source_ranking.decisions import (
    ApprovalPrompt,
    AutomationDecision,
    BlockedOutput,
    ContextRequest,
    DecisionAuditEvent,
    DecisionConfidence,
    DecisionConfidenceLabel,
    NextAction,
    NextActionType,
    PromptChoice,
    SelectedClaim,
    SourceCitation,
)
from data_source_ranking.models import DecisionType, StrictModel
from data_source_ranking.prompts import (
    CHOOSE_OWNER,
    EXCLUDE_SENSITIVE_SOURCE,
    OLD_PROPOSAL,
    REMOVE_CLAIM,
    REQUEST_VALIDATION,
    SENSITIVE_EVIDENCE_OVERLAP,
    SENSITIVE_PARTNER_MATERIAL,
    SKIP_SOURCE,
    STOP_AUTOMATION,
    USE_CAUTIOUS_WORDING,
    USE_DIRECTIONAL_WITH_LABEL,
    USE_HISTORICAL_CONTEXT,
    USE_WITHOUT_OWNER,
)


class ReviewResponseStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ReviewResponse(StrictModel):
    bundle_id: str = Field(min_length=1)
    prompt_issue_type: str = Field(min_length=1)
    selected_choice_id: str = Field(min_length=1)
    responder_id: str | None = None
    responder_name: str | None = None
    selected_owner_id: str | None = None
    selected_owner_name: str | None = None
    user_accepts_risk: bool = False
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReviewResponseFixture(StrictModel):
    bundle_path: str = Field(min_length=1)
    as_of: str | None = None
    response: ReviewResponse
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReviewResponseResult(StrictModel):
    original_decision: AutomationDecision
    response: ReviewResponse
    status: ReviewResponseStatus
    accepted: bool
    applied_effects: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
    audit_events: list[DecisionAuditEvent] = Field(default_factory=list)
    updated_decision: AutomationDecision | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def validate_review_response(
    decision: AutomationDecision,
    response: ReviewResponse,
) -> ReviewResponseResult:
    errors: list[str] = []
    prompt = decision.approval_prompt

    if response.bundle_id != decision.bundle_id:
        errors.append("Response bundle_id does not match the decision bundle_id.")
    if prompt is None:
        errors.append("Decision does not have an approval prompt to answer.")
    else:
        errors.extend(_prompt_response_errors(prompt, response))

    accepted = not errors
    return ReviewResponseResult(
        original_decision=decision,
        response=response,
        status=ReviewResponseStatus.ACCEPTED if accepted else ReviewResponseStatus.REJECTED,
        accepted=accepted,
        applied_effects=_validation_effects(prompt, response) if accepted and prompt else [],
        validation_errors=errors,
        audit_events=[_audit_event(response, accepted, errors)],
        updated_decision=None,
        metadata={
            "validation_only": True,
            "decision": decision.decision.value,
            "has_approval_prompt": prompt is not None,
        },
    )


def apply_review_response(
    decision: AutomationDecision,
    response: ReviewResponse,
) -> ReviewResponseResult:
    validation_result = validate_review_response(decision, response)
    if not validation_result.accepted or decision.approval_prompt is None:
        return validation_result

    prompt = decision.approval_prompt
    effects = _applied_effects(prompt, response)
    metadata = {
        **validation_result.metadata,
        "validation_only": False,
        **_effect_metadata(prompt, response),
    }
    updated_decision = _updated_decision(decision, response, metadata)
    return ReviewResponseResult(
        original_decision=decision,
        response=response,
        status=ReviewResponseStatus.ACCEPTED,
        accepted=True,
        applied_effects=effects,
        validation_errors=[],
        audit_events=[
            *validation_result.audit_events,
            _applied_audit_event(response, effects, metadata),
        ],
        updated_decision=updated_decision,
        metadata=metadata,
    )


def _prompt_response_errors(
    prompt: ApprovalPrompt,
    response: ReviewResponse,
) -> list[str]:
    errors: list[str] = []
    choice = _choice_by_id(prompt, response.selected_choice_id)
    if response.prompt_issue_type != prompt.issue_type:
        errors.append("Response prompt_issue_type does not match the approval prompt.")
    if choice is None:
        errors.append("Response selected_choice_id is not valid for the approval prompt.")
        return errors
    if choice.id == CHOOSE_OWNER and (
        not response.selected_owner_id or not response.selected_owner_name
    ):
        errors.append("Choosing an owner requires selected_owner_id and selected_owner_name.")
    if choice.metadata.get("requires_user_acceptance") and not response.user_accepts_risk:
        errors.append("This choice requires explicit user risk acceptance.")
    return errors


def _choice_by_id(prompt: ApprovalPrompt, choice_id: str) -> PromptChoice | None:
    return next((choice for choice in prompt.choices if choice.id == choice_id), None)


def _validation_effects(prompt: ApprovalPrompt, response: ReviewResponse) -> list[str]:
    effects = ["response_validated", f"choice:{response.selected_choice_id}"]
    choice = _choice_by_id(prompt, response.selected_choice_id)
    if choice and choice.id == CHOOSE_OWNER:
        effects.append("owner_selected")
    if choice and choice.metadata.get("requires_user_acceptance"):
        effects.append("risk_accepted")
    return effects


def _applied_effects(prompt: ApprovalPrompt, response: ReviewResponse) -> list[str]:
    effects = _validation_effects(prompt, response)
    if response.selected_choice_id in {SKIP_SOURCE, EXCLUDE_SENSITIVE_SOURCE}:
        effects.append("source_excluded")
    if response.selected_choice_id == REMOVE_CLAIM:
        effects.append("claim_removed")
    if response.selected_choice_id == REQUEST_VALIDATION:
        effects.append("validation_requested")
    if response.selected_choice_id == STOP_AUTOMATION:
        effects.append("automation_stopped")
    if response.selected_choice_id in {
        USE_DIRECTIONAL_WITH_LABEL,
        USE_WITHOUT_OWNER,
        USE_CAUTIOUS_WORDING,
        USE_HISTORICAL_CONTEXT,
    }:
        effects.append("caveat_accepted")
    return effects


def _effect_metadata(prompt: ApprovalPrompt, response: ReviewResponse) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "prompt_issue_type": prompt.issue_type,
        "selected_choice_id": response.selected_choice_id,
        "affected_source_ids": prompt.source_ids,
        "next_step": "rerun_decision",
    }
    if response.selected_choice_id in {SKIP_SOURCE, EXCLUDE_SENSITIVE_SOURCE}:
        metadata["excluded_source_ids"] = prompt.source_ids
    if response.selected_choice_id == REMOVE_CLAIM:
        metadata["removed_claim_ids"] = _unsupported_claim_ids(prompt)
        metadata["affected_source_ids"] = list(prompt.metadata.get("unsupported_claims", {}))
    if response.selected_choice_id == REQUEST_VALIDATION:
        metadata["validation_source_ids"] = prompt.source_ids
        owner_candidates = prompt.metadata.get("owner_candidates", {})
        validation_owner = _first_owner_candidate(owner_candidates, prompt.source_ids)
        metadata["owner_candidates"] = owner_candidates
        if validation_owner is None:
            metadata["missing_owner_for_validation"] = True
            metadata["next_step"] = "choose_owner"
        else:
            metadata["validation_owner"] = validation_owner
            metadata["next_step"] = "send_context_request"
    if response.selected_choice_id == STOP_AUTOMATION:
        metadata["next_step"] = "stop_automation"
    if response.selected_choice_id == CHOOSE_OWNER:
        metadata["selected_owner"] = {
            "id": response.selected_owner_id,
            "name": response.selected_owner_name,
        }
        metadata["validation_source_ids"] = prompt.source_ids
    risk_label = _accepted_risk_label(prompt, response)
    if risk_label:
        metadata["accepted_risk"] = risk_label
        metadata["user_accepts_risk"] = response.user_accepts_risk
    caveat = _accepted_caveat(response.selected_choice_id)
    if caveat:
        metadata["accepted_caveat"] = caveat
    return metadata


def _unsupported_claim_ids(prompt: ApprovalPrompt) -> list[str]:
    return [
        claim["id"]
        for claims in prompt.metadata.get("unsupported_claims", {}).values()
        for claim in claims
        if "id" in claim
    ]


def _accepted_risk_label(prompt: ApprovalPrompt, response: ReviewResponse) -> str | None:
    choice = _choice_by_id(prompt, response.selected_choice_id)
    if choice is None:
        return None
    risk = choice.metadata.get("risk")
    return risk if isinstance(risk, str) else None


def _accepted_caveat(choice_id: str) -> str | None:
    return {
        USE_DIRECTIONAL_WITH_LABEL: "similar_client_directional_context",
        USE_WITHOUT_OWNER: "owner_unvalidated",
        USE_CAUTIOUS_WORDING: "unsupported_inference_cautious_wording",
        USE_HISTORICAL_CONTEXT: "historical_context_only",
    }.get(choice_id)


def _applied_audit_event(
    response: ReviewResponse,
    effects: list[str],
    metadata: dict[str, Any],
) -> DecisionAuditEvent:
    return DecisionAuditEvent(
        event="review_response_applied",
        message="Review response effects were recorded.",
        metadata={
            "bundle_id": response.bundle_id,
            "selected_choice_id": response.selected_choice_id,
            "applied_effects": effects,
            "next_step": metadata["next_step"],
        },
    )


def _updated_decision(
    decision: AutomationDecision,
    response: ReviewResponse,
    metadata: dict[str, Any],
) -> AutomationDecision | None:
    if response.selected_choice_id in {SKIP_SOURCE, EXCLUDE_SENSITIVE_SOURCE}:
        return _source_exclusion_decision(decision, response, metadata)
    if response.selected_choice_id == REMOVE_CLAIM:
        return _claim_removal_decision(decision, response, metadata)
    if response.selected_choice_id == STOP_AUTOMATION:
        return _stopped_decision(decision, response, metadata)
    if response.selected_choice_id == CHOOSE_OWNER:
        return _owner_context_request_decision(decision, response, metadata)
    if response.selected_choice_id == REQUEST_VALIDATION:
        return _request_validation_context_request_decision(decision, response, metadata)
    if response.selected_choice_id in {
        USE_DIRECTIONAL_WITH_LABEL,
        USE_WITHOUT_OWNER,
        USE_CAUTIOUS_WORDING,
        USE_HISTORICAL_CONTEXT,
    }:
        return _caveat_acceptance_review_decision(decision, response, metadata)
    return None


def _caveat_acceptance_review_decision(
    decision: AutomationDecision,
    response: ReviewResponse,
    metadata: dict[str, Any],
) -> AutomationDecision:
    transition_metadata = _review_transition_metadata(decision, response, metadata)
    next_action_metadata: dict[str, Any] = {
        "review_response_choice": response.selected_choice_id,
        "review_response_applied": True,
        "next_step": "rerun_decision",
        "accepted_caveat": metadata.get("accepted_caveat"),
    }
    if metadata.get("accepted_risk"):
        next_action_metadata["accepted_risk"] = metadata["accepted_risk"]
        next_action_metadata["user_accepts_risk"] = metadata.get("user_accepts_risk")

    return decision.model_copy(
        update={
            "decision": DecisionType.NEEDS_USER_REVIEW,
            "summary": (
                "Review response accepted a constrained-use caveat; rerun the decision "
                "to determine the next automation outcome."
            ),
            "next_action": NextAction(
                type=NextActionType.MANUAL_REVIEW,
                label="Rerun decision",
                description=(
                    "Review response accepted a constrained-use caveat; rerun the "
                    "decision before continuing automation."
                ),
                metadata=next_action_metadata,
            ),
            "approval_prompt": None,
            "context_request": None,
            "draft_handoff": None,
            "blocked_output": None,
            "audit_trace": [
                *decision.audit_trace,
                DecisionAuditEvent(
                    event="review_response_updated_decision",
                    message=(
                        "Review response accepted a constrained-use caveat without "
                        "recomputing the final decision."
                    ),
                    metadata={
                        "previous_decision": decision.decision.value,
                        "new_decision": DecisionType.NEEDS_USER_REVIEW.value,
                        "selected_choice_id": response.selected_choice_id,
                        "accepted_caveat": metadata.get("accepted_caveat"),
                    },
                ),
            ],
            "metadata": transition_metadata,
        }
    )


def _source_exclusion_decision(
    decision: AutomationDecision,
    response: ReviewResponse,
    metadata: dict[str, Any],
) -> AutomationDecision:
    excluded_source_ids = set(metadata.get("excluded_source_ids", []))
    selected_claims = _selected_claims_without_sources(
        decision.selected_claims,
        excluded_source_ids,
    )
    selected_sources = _selected_source_ids(selected_claims)
    source_citations = _source_citations_for_selected_claims(
        decision.source_citations,
        selected_claims,
    )
    if not selected_claims or not selected_sources:
        return _evidence_removed_blocked_decision(
            decision,
            response,
            metadata,
            "Review response excluded all selected source evidence.",
        )
    return _evidence_updated_review_decision(
        decision,
        response,
        metadata,
        selected_claims,
        selected_sources,
        source_citations,
        "Review response excluded selected source evidence without recomputing the final decision.",
    )


def _claim_removal_decision(
    decision: AutomationDecision,
    response: ReviewResponse,
    metadata: dict[str, Any],
) -> AutomationDecision:
    removed_claim_ids = set(metadata.get("removed_claim_ids", []))
    selected_claims = [
        claim for claim in decision.selected_claims if claim.claim_id not in removed_claim_ids
    ]
    selected_sources = _selected_source_ids(selected_claims)
    source_citations = _source_citations_for_selected_claims(
        decision.source_citations,
        selected_claims,
    )
    if not selected_claims or not selected_sources:
        return _evidence_removed_blocked_decision(
            decision,
            response,
            metadata,
            "Review response removed all selected claim evidence.",
        )
    return _evidence_updated_review_decision(
        decision,
        response,
        metadata,
        selected_claims,
        selected_sources,
        source_citations,
        "Review response removed selected claim evidence without recomputing the final decision.",
    )


def _selected_claims_without_sources(
    selected_claims: list[SelectedClaim],
    excluded_source_ids: set[str],
) -> list[SelectedClaim]:
    filtered: list[SelectedClaim] = []
    for claim in selected_claims:
        remaining_source_ids = [
            source_id for source_id in claim.source_ids if source_id not in excluded_source_ids
        ]
        if remaining_source_ids:
            filtered.append(claim.model_copy(update={"source_ids": remaining_source_ids}))
    return filtered


def _selected_source_ids(selected_claims: list[SelectedClaim]) -> list[str]:
    selected_source_ids: list[str] = []
    for claim in selected_claims:
        for source_id in claim.source_ids:
            if source_id not in selected_source_ids:
                selected_source_ids.append(source_id)
    return selected_source_ids


def _source_citations_for_selected_claims(
    source_citations: list[SourceCitation],
    selected_claims: list[SelectedClaim],
) -> list[SourceCitation]:
    selected_keys = {
        (claim.claim_id, claim.needed_claim_id, source_id)
        for claim in selected_claims
        for source_id in claim.source_ids
    }
    return [
        citation
        for citation in source_citations
        if (
            citation.claim_id,
            citation.needed_claim_id,
            citation.source_id,
        )
        in selected_keys
    ]


def _evidence_updated_review_decision(
    decision: AutomationDecision,
    response: ReviewResponse,
    metadata: dict[str, Any],
    selected_claims: list[SelectedClaim],
    selected_sources: list[str],
    source_citations: list[SourceCitation],
    audit_message: str,
) -> AutomationDecision:
    transition_metadata = _review_transition_metadata(decision, response, metadata)
    return decision.model_copy(
        update={
            "selected_claims": selected_claims,
            "selected_sources": selected_sources,
            "source_citations": source_citations,
            "summary": (
                "Review response was applied; rerun the decision to determine the next "
                "automation outcome."
            ),
            "next_action": NextAction(
                type=NextActionType.MANUAL_REVIEW,
                label="Rerun decision",
                description=(
                    "Review response changed the selected evidence; rerun the decision "
                    "before continuing automation."
                ),
                metadata={
                    "review_response_choice": response.selected_choice_id,
                    "review_response_applied": True,
                    "next_step": "rerun_decision",
                },
            ),
            "approval_prompt": None,
            "context_request": None,
            "draft_handoff": None,
            "blocked_output": None,
            "audit_trace": [
                *decision.audit_trace,
                DecisionAuditEvent(
                    event="review_response_updated_decision",
                    message=audit_message,
                    metadata={
                        "previous_decision": decision.decision.value,
                        "new_decision": decision.decision.value,
                        "selected_choice_id": response.selected_choice_id,
                        "selected_sources": selected_sources,
                    },
                ),
            ],
            "metadata": transition_metadata,
        }
    )


def _evidence_removed_blocked_decision(
    decision: AutomationDecision,
    response: ReviewResponse,
    metadata: dict[str, Any],
    blocking_reason: str,
) -> AutomationDecision:
    transition_metadata = {
        **_review_transition_metadata(decision, response, metadata),
        "next_step": "stop_automation",
    }
    return decision.model_copy(
        update={
            "decision": DecisionType.BLOCKED,
            "confidence": DecisionConfidence(
                score=0.9,
                label=DecisionConfidenceLabel.HIGH,
                reasons=[
                    "Review response removed the selected evidence needed to continue automation."
                ],
            ),
            "summary": blocking_reason,
            "selected_claims": [],
            "selected_sources": [],
            "source_citations": [],
            "next_action": NextAction(
                type=NextActionType.STOP,
                label="Stop automation",
                description=(
                    "Review response removed the selected evidence needed to continue "
                    "automation."
                ),
                metadata={
                    "review_response_choice": response.selected_choice_id,
                    "review_response_applied": True,
                    "next_step": "stop_automation",
                },
            ),
            "approval_prompt": None,
            "context_request": None,
            "draft_handoff": None,
            "blocked_output": BlockedOutput(
                blocking_reason=blocking_reason,
                missing_evidence=[],
                sources_considered=metadata.get("affected_source_ids", []),
                blocking_policy_gates=[],
                manual_next_step=(
                    "Add or validate source-backed evidence before restarting automation."
                ),
                metadata={
                    "review_response_choice": response.selected_choice_id,
                    "review_response_applied": True,
                },
            ),
            "audit_trace": [
                *decision.audit_trace,
                DecisionAuditEvent(
                    event="review_response_updated_decision",
                    message="Review response changed the top-level decision to blocked.",
                    metadata={
                        "previous_decision": decision.decision.value,
                        "new_decision": DecisionType.BLOCKED.value,
                        "selected_choice_id": response.selected_choice_id,
                    },
                ),
            ],
            "metadata": transition_metadata,
        }
    )


def _review_transition_metadata(
    decision: AutomationDecision,
    response: ReviewResponse,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        **decision.metadata,
        "updated_from_decision": decision.decision.value,
        "review_response_choice": response.selected_choice_id,
        "review_response_applied": True,
        **{
            key: value
            for key, value in metadata.items()
            if key
            in {
                "affected_source_ids",
                "excluded_source_ids",
                "removed_claim_ids",
                "next_step",
                "prompt_issue_type",
                "accepted_caveat",
                "accepted_risk",
                "user_accepts_risk",
            }
        },
    }


def _owner_context_request_decision(
    decision: AutomationDecision,
    response: ReviewResponse,
    metadata: dict[str, Any],
) -> AutomationDecision:
    question = _owner_validation_question(decision.approval_prompt)
    context_request = ContextRequest(
        recipient_id=response.selected_owner_id or "",
        recipient_name=response.selected_owner_name or "",
        recipient_reason="User selected this owner during review.",
        question=question,
        missing_information=[
            "Owner validation for whether this source can be used in automation."
        ],
        source_ids=metadata.get("validation_source_ids", []),
        suggested_response_format=(
            "Reply with whether the source can be used, any corrected context, and any "
            "caveats the generated outreach should preserve."
        ),
        metadata={
            "selected_by_review_response": True,
            "review_response_choice": response.selected_choice_id,
        },
    )
    return decision.model_copy(
        update={
            "decision": DecisionType.GENERATE_CONTEXT_REQUEST,
            "confidence": DecisionConfidence(
                score=0.74,
                label=DecisionConfidenceLabel.MEDIUM,
                reasons=[
                    "User selected an owner who can validate the source before automation."
                ],
            ),
            "summary": "User selected an owner for validation before automation continues.",
            "selected_sources": metadata.get("validation_source_ids", []),
            "next_action": NextAction(
                type=NextActionType.ASK_OWNER,
                label="Ask owner for validation",
                description="Ask the user-selected owner to validate this source.",
                owner_id=response.selected_owner_id,
                owner_name=response.selected_owner_name,
                question=question,
                metadata={
                    "review_response_choice": response.selected_choice_id,
                    "selected_owner": metadata.get("selected_owner"),
                    "requires_owner_validation": True,
                },
            ),
            "approval_prompt": None,
            "context_request": context_request,
            "draft_handoff": None,
            "blocked_output": None,
            "audit_trace": [
                *decision.audit_trace,
                DecisionAuditEvent(
                    event="review_response_updated_decision",
                    message=(
                        "Review response changed the top-level decision to generate "
                        "context request."
                    ),
                    metadata={
                        "previous_decision": decision.decision.value,
                        "new_decision": DecisionType.GENERATE_CONTEXT_REQUEST.value,
                        "selected_choice_id": response.selected_choice_id,
                        "selected_owner": metadata.get("selected_owner"),
                    },
                ),
            ],
            "metadata": {
                **decision.metadata,
                "updated_from_decision": decision.decision.value,
                "review_response_choice": response.selected_choice_id,
                "selected_owner": metadata.get("selected_owner"),
                "requires_owner_validation": True,
            },
        }
    )


def _request_validation_context_request_decision(
    decision: AutomationDecision,
    response: ReviewResponse,
    metadata: dict[str, Any],
) -> AutomationDecision | None:
    owner = metadata.get("validation_owner")
    if not isinstance(owner, dict):
        return None

    question = _request_validation_question(decision.approval_prompt)
    context_request = ContextRequest(
        recipient_id=str(owner["id"]),
        recipient_name=str(owner["name"]),
        recipient_reason=str(owner.get("reason", "Likely owner from source metadata.")),
        question=question,
        missing_information=[
            "Owner validation for whether this source can be used in automation."
        ],
        source_ids=metadata.get("validation_source_ids", []),
        suggested_response_format=(
            "Reply with whether the source can be used, any corrected context, and any "
            "caveats the generated outreach should preserve."
        ),
        metadata={
            "selected_from_prompt_owner_candidates": True,
            "review_response_choice": response.selected_choice_id,
        },
    )
    return decision.model_copy(
        update={
            "decision": DecisionType.GENERATE_CONTEXT_REQUEST,
            "confidence": DecisionConfidence(
                score=0.74,
                label=DecisionConfidenceLabel.MEDIUM,
                reasons=[
                    "A responsible owner can validate the source before automation."
                ],
            ),
            "summary": "Review response requested owner validation before automation continues.",
            "selected_sources": metadata.get("validation_source_ids", []),
            "next_action": NextAction(
                type=NextActionType.ASK_OWNER,
                label="Ask owner for validation",
                description="Ask the likely owner to validate this source.",
                owner_id=str(owner["id"]),
                owner_name=str(owner["name"]),
                question=question,
                metadata={
                    "review_response_choice": response.selected_choice_id,
                    "validation_owner": owner,
                    "requires_owner_validation": True,
                },
            ),
            "approval_prompt": None,
            "context_request": context_request,
            "draft_handoff": None,
            "blocked_output": None,
            "audit_trace": [
                *decision.audit_trace,
                DecisionAuditEvent(
                    event="review_response_updated_decision",
                    message=(
                        "Review response changed the top-level decision to generate "
                        "context request."
                    ),
                    metadata={
                        "previous_decision": decision.decision.value,
                        "new_decision": DecisionType.GENERATE_CONTEXT_REQUEST.value,
                        "selected_choice_id": response.selected_choice_id,
                        "validation_owner": owner,
                    },
                ),
            ],
            "metadata": {
                **decision.metadata,
                "updated_from_decision": decision.decision.value,
                "review_response_choice": response.selected_choice_id,
                "validation_owner": owner,
                "requires_owner_validation": True,
            },
        }
    )


def _owner_validation_question(prompt: ApprovalPrompt | None) -> str:
    source_titles = prompt.metadata.get("source_titles", {}) if prompt else {}
    title = next(iter(source_titles.values()), None)
    if title:
        return (
            f"Can you validate whether '{title}' can be used for this automation context?"
        )
    return "Can you validate whether this source can be used for this automation context?"


def _request_validation_question(prompt: ApprovalPrompt | None) -> str:
    if prompt is None:
        return "Can you validate whether this source can be used for this automation context?"
    if prompt.issue_type == OLD_PROPOSAL:
        return (
            "Can you validate whether this proposal still applies to the current client "
            "situation?"
        )
    if prompt.issue_type == SENSITIVE_PARTNER_MATERIAL:
        return (
            "Can you confirm whether this sensitive partner material can be used for this "
            "automation context?"
        )
    if prompt.issue_type == SENSITIVE_EVIDENCE_OVERLAP:
        return "Can you confirm whether this sensitive source can be used, or should we exclude it?"
    return "Can you validate whether this source can be used for this automation context?"


def _first_owner_candidate(
    owner_candidates: Any,
    source_ids: list[str],
) -> dict[str, Any] | None:
    if not isinstance(owner_candidates, dict):
        return None
    for source_id in source_ids:
        candidates = owner_candidates.get(source_id, [])
        if not candidates:
            continue
        candidate = candidates[0]
        if isinstance(candidate, dict) and candidate.get("id") and candidate.get("name"):
            return candidate
    return None


def _stopped_decision(
    decision: AutomationDecision,
    response: ReviewResponse,
    metadata: dict[str, Any],
) -> AutomationDecision:
    return decision.model_copy(
        update={
            "decision": DecisionType.BLOCKED,
            "confidence": DecisionConfidence(
                score=0.95,
                label=DecisionConfidenceLabel.HIGH,
                reasons=["User chose to stop automation from the approval prompt."],
            ),
            "summary": "Automation was stopped by user review response.",
            "selected_claims": [],
            "selected_sources": [],
            "source_citations": [],
            "next_action": NextAction(
                type=NextActionType.STOP,
                label="Stop automation",
                description="User chose to stop automation from the review prompt.",
                metadata={
                    "review_response_choice": response.selected_choice_id,
                    "user_requested_stop": True,
                },
            ),
            "approval_prompt": None,
            "context_request": None,
            "draft_handoff": None,
            "blocked_output": BlockedOutput(
                blocking_reason="User chose to stop automation during review.",
                missing_evidence=[],
                sources_considered=metadata.get("affected_source_ids", []),
                blocking_policy_gates=[],
                manual_next_step=(
                    "Do not continue automated context generation unless a new review "
                    "response or new evidence is supplied."
                ),
                metadata={
                    "review_response_choice": response.selected_choice_id,
                    "user_requested_stop": True,
                },
            ),
            "audit_trace": [
                *decision.audit_trace,
                DecisionAuditEvent(
                    event="review_response_updated_decision",
                    message="Review response changed the top-level decision to blocked.",
                    metadata={
                        "previous_decision": decision.decision.value,
                        "new_decision": DecisionType.BLOCKED.value,
                        "selected_choice_id": response.selected_choice_id,
                    },
                ),
            ],
            "metadata": {
                **decision.metadata,
                "updated_from_decision": decision.decision.value,
                "review_response_choice": response.selected_choice_id,
                "user_requested_stop": True,
            },
        }
    )


def _audit_event(
    response: ReviewResponse,
    accepted: bool,
    errors: list[str],
) -> DecisionAuditEvent:
    return DecisionAuditEvent(
        event="review_response_validated" if accepted else "review_response_rejected",
        level="info" if accepted else "warning",
        message=(
            "Review response passed validation."
            if accepted
            else "Review response failed validation."
        ),
        metadata={
            "bundle_id": response.bundle_id,
            "prompt_issue_type": response.prompt_issue_type,
            "selected_choice_id": response.selected_choice_id,
            "validation_errors": errors,
        },
    )
