from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import Field

from data_source_ranking.models import (
    ClaimType,
    DecisionType,
    RankedBundle,
    SourceType,
    StrictModel,
    WeakPoint,
)


class DecisionConfidenceLabel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class NextActionType(StrEnum):
    PREPARE_HANDOFF = "prepare_handoff"
    ASK_OWNER = "ask_owner"
    ASK_USER = "ask_user"
    MANUAL_REVIEW = "manual_review"
    STOP = "stop"


class PolicyGateStatus(StrEnum):
    PASSED = "passed"
    TRIGGERED = "triggered"
    NOT_APPLICABLE = "not_applicable"


class PolicyGateEffect(StrEnum):
    ALLOWS_AUTO_HANDOFF = "allows_auto_handoff"
    PREVENTS_AUTO_HANDOFF = "prevents_auto_handoff"
    REQUIRES_CONTEXT_REQUEST = "requires_context_request"
    REQUIRES_USER_REVIEW = "requires_user_review"
    BLOCKS_AUTOMATION = "blocks_automation"
    INFORMATIONAL = "informational"


class DecisionConfidence(StrictModel):
    score: float = Field(ge=0.0, le=1.0)
    label: DecisionConfidenceLabel
    reasons: list[str] = Field(default_factory=list)


class SelectedClaim(StrictModel):
    claim_id: str
    needed_claim_id: str
    text: str = Field(min_length=1)
    claim_type: ClaimType = ClaimType.OTHER
    source_ids: list[str] = Field(default_factory=list)
    is_inferred: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceCitation(StrictModel):
    source_id: str
    title: str = Field(min_length=1)
    source_type: SourceType
    claim_id: str | None = None
    needed_claim_id: str | None = None
    citation_label: str | None = None
    external_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyGateResult(StrictModel):
    gate: str
    status: PolicyGateStatus
    effect: PolicyGateEffect
    message: str
    source_ids: list[str] = Field(default_factory=list)
    needed_claim_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NextAction(StrictModel):
    type: NextActionType
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)
    owner_id: str | None = None
    owner_name: str | None = None
    question: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptChoice(StrictModel):
    id: str
    label: str = Field(min_length=1)
    effect: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalPrompt(StrictModel):
    issue_type: str
    question: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    recommended_action: str
    choices: list[PromptChoice] = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContextRequest(StrictModel):
    recipient_id: str
    recipient_name: str = Field(min_length=1)
    recipient_reason: str = Field(min_length=1)
    question: str = Field(min_length=1)
    missing_information: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    suggested_response_format: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DraftHandoff(StrictModel):
    text: str = Field(min_length=1)
    supported_claim_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BlockedOutput(StrictModel):
    blocking_reason: str = Field(min_length=1)
    missing_evidence: list[str] = Field(default_factory=list)
    sources_considered: list[str] = Field(default_factory=list)
    blocking_policy_gates: list[str] = Field(default_factory=list)
    manual_next_step: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionAuditEvent(StrictModel):
    event: str
    message: str = Field(min_length=1)
    level: Literal["info", "warning", "error"] = "info"
    metadata: dict[str, Any] = Field(default_factory=dict)


class AutomationDecision(StrictModel):
    bundle_id: str
    decision: DecisionType
    confidence: DecisionConfidence
    summary: str = Field(min_length=1)
    ranked_bundle: RankedBundle
    selected_claims: list[SelectedClaim] = Field(default_factory=list)
    selected_sources: list[str] = Field(default_factory=list)
    source_citations: list[SourceCitation] = Field(default_factory=list)
    weak_points: list[WeakPoint] = Field(default_factory=list)
    policy_gates: list[PolicyGateResult] = Field(default_factory=list)
    next_action: NextAction
    approval_prompt: ApprovalPrompt | None = None
    context_request: ContextRequest | None = None
    draft_handoff: DraftHandoff | None = None
    blocked_output: BlockedOutput | None = None
    audit_trace: list[DecisionAuditEvent] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
