from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from data_source_ranking.agents.retrieval import SimulatedRetrievalResult
from data_source_ranking.decisions import (
    ApprovalPrompt,
    AutomationDecision,
    ContextRequest,
)
from data_source_ranking.models import (
    Claim,
    ContextNeed,
    OwnerCandidate,
    RankedSource,
    Source,
    SourceBundle,
    StrictModel,
    WeakPoint,
)
from data_source_ranking.review_responses import ReviewResponseResult


class LoopActionType(StrEnum):
    LOAD_BUNDLE = "load_bundle"
    RANK_SOURCES = "rank_sources"
    DECIDE_AUTOMATION = "decide_automation"
    INSPECT_WEAK_POINTS = "inspect_weak_points"
    RETRIEVE_MORE_CONTEXT = "retrieve_more_context"
    ASK_OWNER = "ask_owner"
    ASK_USER_REVIEW = "ask_user_review"
    APPLY_OWNER_RESPONSE = "apply_owner_response"
    APPLY_USER_REVIEW = "apply_user_review"
    RECORD_FEEDBACK = "record_feedback"
    STOP_AUTO_HANDOFF = "stop_auto_handoff"
    STOP_BLOCKED = "stop_blocked"


class StopReason(StrEnum):
    FINAL_DECISION_READY = "final_decision_ready"
    BLOCKED_NO_RELIABLE_PATH = "blocked_no_reliable_path"
    PENDING_OWNER_RESPONSE = "pending_owner_response"
    PENDING_USER_REVIEW = "pending_user_review"
    MAX_ITERATIONS_REACHED = "max_iterations_reached"
    REPEATED_ACTION_DETECTED = "repeated_action_detected"


class AuditEventType(StrEnum):
    BUNDLE_LOADED = "bundle_loaded"
    SOURCES_RANKED = "sources_ranked"
    DECISION_RECORDED = "decision_recorded"
    WEAK_POINTS_INSPECTED = "weak_points_inspected"
    ACTION_SELECTED = "action_selected"
    REVIEW_RESPONSE_APPLIED = "review_response_applied"
    OWNER_RESPONSE_APPLIED = "owner_response_applied"
    OWNER_RESPONSE_REJECTED = "owner_response_rejected"
    SIMULATED_RETRIEVAL_APPLIED = "simulated_retrieval_applied"
    SIMULATED_RETRIEVAL_REJECTED = "simulated_retrieval_rejected"
    LOOP_STOPPED = "loop_stopped"


class AuditEventLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class OwnerResponseOutcome(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CORRECTED = "corrected"
    NO_RESPONSE = "no_response"


class LoopAction(StrictModel):
    type: LoopActionType
    label: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LoopStep(StrictModel):
    sequence: int = Field(ge=1)
    input_summary: dict[str, Any] = Field(default_factory=dict)
    action: LoopAction
    output_summary: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(min_length=1)
    stop_reason: StopReason | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditEvent(StrictModel):
    sequence: int = Field(ge=1)
    event_type: AuditEventType
    title: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    level: AuditEventLevel = AuditEventLevel.INFO
    action_type: LoopActionType | None = None
    source_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    policy_gate_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditTrace(StrictModel):
    events: list[AuditEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_ordered_unique_sequences(self) -> AuditTrace:
        sequences = [event.sequence for event in self.events]
        if sequences != sorted(sequences):
            raise ValueError("audit events must be ordered by sequence")
        if len(sequences) != len(set(sequences)):
            raise ValueError("audit events must use unique sequence values")
        return self


class OwnerResponse(StrictModel):
    bundle_id: str
    source_id: str
    owner_id: str
    owner_name: str = Field(min_length=1)
    outcome: OwnerResponseOutcome
    validated_claim_ids: list[str] = Field(default_factory=list)
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OwnerResponseFixture(StrictModel):
    bundle_path: str
    as_of: str | None = None
    response: OwnerResponse


class OwnerResponseResult(StrictModel):
    accepted: bool
    response: OwnerResponse
    original_bundle: SourceBundle
    updated_bundle: SourceBundle | None = None
    validation_errors: list[str] = Field(default_factory=list)
    applied_effects: list[str] = Field(default_factory=list)
    audit_events: list[AuditEvent] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentLoopState(StrictModel):
    bundle_id: str
    context_need: ContextNeed
    current_sources: list[Source] = Field(default_factory=list)
    ranked_sources: list[RankedSource] = Field(default_factory=list)
    automation_decision: AutomationDecision
    candidate_claims: list[Claim] = Field(default_factory=list)
    weak_points: list[WeakPoint] = Field(default_factory=list)
    owner_candidates: list[OwnerCandidate] = Field(default_factory=list)
    pending_approval_prompt: ApprovalPrompt | None = None
    pending_context_request: ContextRequest | None = None
    review_response_result: ReviewResponseResult | None = None
    owner_response_result: OwnerResponseResult | None = None
    simulated_retrieval_result: SimulatedRetrievalResult | None = None
    owner_responses: list[OwnerResponse] = Field(default_factory=list)
    iteration_count: int = Field(ge=0, default=0)
    steps: list[LoopStep] = Field(default_factory=list)
    audit_trace: AuditTrace = Field(default_factory=AuditTrace)
    final_decision: AutomationDecision | None = None
    stop_reason: StopReason | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_matching_decision_bundle(self) -> AgentLoopState:
        if self.automation_decision.bundle_id != self.bundle_id:
            raise ValueError("automation_decision bundle_id must match loop state bundle_id")
        if self.final_decision and self.final_decision.bundle_id != self.bundle_id:
            raise ValueError("final_decision bundle_id must match loop state bundle_id")
        return self


class AgentRunResult(StrictModel):
    bundle_id: str
    initial_decision: AutomationDecision
    final_decision: AutomationDecision
    state: AgentLoopState
    steps: list[LoopStep] = Field(default_factory=list)
    audit_trace: AuditTrace = Field(default_factory=AuditTrace)
    stop_reason: StopReason
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_consistent_bundle_ids(self) -> AgentRunResult:
        bundle_ids = {
            self.bundle_id,
            self.initial_decision.bundle_id,
            self.final_decision.bundle_id,
            self.state.bundle_id,
        }
        if len(bundle_ids) != 1:
            raise ValueError("agent run result bundle ids must match")
        return self
