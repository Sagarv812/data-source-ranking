from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    """Base model for fixture-backed objects where unknown fields should fail fast."""

    model_config = ConfigDict(extra="forbid")


class RiskTolerance(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class NeededClaimType(StrEnum):
    CURRENT_CLIENT_CONCERN = "current_client_concern"
    VALIDATED_PRIOR_WORK = "validated_prior_work"
    LIKELY_ACCOUNT_OWNER = "likely_account_owner"
    IMPLEMENTATION_RISK = "implementation_risk"
    SIMILAR_CLIENT_CONTEXT = "similar_client_context"
    DECISION_FEEDBACK = "decision_feedback"
    NEXT_STEP = "next_step"
    OTHER = "other"


class SourceType(StrEnum):
    CRM_NOTE = "crm_note"
    SALESFORCE_OPPORTUNITY_NOTE = "salesforce_opportunity_note"
    MEETING_EVENT = "meeting_event"
    MEETING_NOTES = "meeting_notes"
    PROPOSAL = "proposal"
    DECK = "deck"
    FLOWCASE_MATCH = "flowcase_match"
    PARTNER_MATERIAL = "partner_material"
    HUMAN_VALIDATED_CONTEXT = "human_validated_context"
    PRIOR_HANDOFF = "prior_handoff"
    OTHER = "other"


class DirectnessRelation(StrEnum):
    SAME_CLIENT_SAME_OPPORTUNITY = "same_client_same_opportunity"
    SAME_CLIENT_ADJACENT_OPPORTUNITY = "same_client_adjacent_opportunity"
    SAME_ACCOUNT_GROUP = "same_account_group"
    CLOSELY_RELATED_STAKEHOLDER = "closely_related_stakeholder"
    SIMILAR_CLIENT = "similar_client"
    GENERIC_INDUSTRY = "generic_industry"
    WEAK_MATCH = "weak_match"
    UNKNOWN = "unknown"


class SourceSystem(StrEnum):
    SALESFORCE = "salesforce"
    CALENDAR = "calendar"
    DRIVE = "drive"
    FLOWCASE = "flowcase"
    HUMAN = "human"
    PARTNER_PORTAL = "partner_portal"
    LOCAL_FIXTURE = "local_fixture"
    OTHER = "other"


class PersonRole(StrEnum):
    ACCOUNT_OWNER = "account_owner"
    OPPORTUNITY_OWNER = "opportunity_owner"
    PROPOSAL_OWNER = "proposal_owner"
    DOCUMENT_AUTHOR = "document_author"
    MEETING_ATTENDEE = "meeting_attendee"
    LAST_EDITOR = "last_editor"
    PARTNER_CONTACT = "partner_contact"
    USER = "user"
    UNKNOWN = "unknown"
    OTHER = "other"


class ClaimType(StrEnum):
    CLIENT_CONCERN = "client_concern"
    PRIOR_WORK = "prior_work"
    OWNER_SIGNAL = "owner_signal"
    PROGRAM_SIGNAL = "program_signal"
    SIMILAR_CLIENT_CONTEXT = "similar_client_context"
    IMPLEMENTATION_RISK = "implementation_risk"
    DECISION_FEEDBACK = "decision_feedback"
    NEXT_STEP = "next_step"
    UNSUPPORTED_INFERENCE = "unsupported_inference"
    OTHER = "other"


class SensitivityLabel(StrEnum):
    INTERNAL_ONLY = "internal_only"
    CONFIDENTIAL = "confidential"
    PARTNER_CHANNEL = "partner_channel"
    STALE_DATA = "stale_data"
    UNSUPPORTED_INFERENCE = "unsupported_inference"
    NONE = "none"
    OTHER = "other"


class WeakPointType(StrEnum):
    MISSING_DATE = "missing_date"
    STALE_SOURCE = "stale_source"
    MISSING_OWNER = "missing_owner"
    UNCLEAR_OWNER = "unclear_owner"
    VAGUE_CLAIM = "vague_claim"
    LOW_DIRECTNESS = "low_directness"
    SENSITIVE_SOURCE = "sensitive_source"
    INCOMPLETE_CONTEXT = "incomplete_context"
    LOW_AUTHORITY = "low_authority"
    LOW_CORROBORATION = "low_corroboration"
    UNSUPPORTED_INFERENCE = "unsupported_inference"
    CONTRADICTION = "contradiction"
    OTHER = "other"


class Tier(StrEnum):
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"


class DecisionType(StrEnum):
    AUTO_HANDOFF = "auto_handoff"
    GENERATE_CONTEXT_REQUEST = "generate_context_request"
    NEEDS_USER_REVIEW = "needs_user_review"
    BLOCKED = "blocked"


class RankingDimension(StrEnum):
    FRESHNESS = "freshness"
    DIRECTNESS = "directness"
    AUTHORITY = "authority"
    OWNERSHIP_SIGNAL = "ownership_signal"
    COMPLETENESS = "completeness"
    CORROBORATION = "corroboration"
    SENSITIVITY = "sensitivity"
    SPECIFICITY = "specificity"
    HISTORICAL_RELIABILITY = "historical_reliability"


class Person(StrictModel):
    id: str
    name: str
    role: PersonRole | None = None
    role_title: str | None = None
    email: str | None = None


class OwnerCandidate(StrictModel):
    id: str
    name: str
    role: PersonRole | None = None
    role_title: str | None = None
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)


class NeededClaim(StrictModel):
    id: str
    type: NeededClaimType = NeededClaimType.OTHER
    description: str = Field(min_length=1)
    required: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class Claim(StrictModel):
    id: str
    text: str = Field(min_length=1)
    claim_type: ClaimType = ClaimType.OTHER
    is_inferred: bool = False
    supports_needed_claim_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("supports_needed_claim_ids", "source_ids")
    @classmethod
    def no_empty_strings(cls, values: list[str]) -> list[str]:
        return [value for value in values if value]


class ValidationRecord(StrictModel):
    validated_by: Person | None = None
    validated_at: date | None = None
    validated_claim_ids: list[str] = Field(default_factory=list)
    outcome: Literal["accepted", "rejected", "corrected", "unknown"] = "unknown"
    notes: str | None = None

    @field_validator("validated_claim_ids")
    @classmethod
    def no_empty_claim_ids(cls, values: list[str]) -> list[str]:
        return [value for value in values if value]


class ContextNeed(StrictModel):
    id: str
    client_id: str
    account_id: str | None = None
    opportunity_id: str | None = None
    email_goal: str = Field(min_length=1)
    needed_claims: list[NeededClaim] = Field(min_length=1)
    risk_tolerance: RiskTolerance = RiskTolerance.NORMAL
    metadata: dict[str, Any] = Field(default_factory=dict)


class Source(StrictModel):
    id: str
    type: SourceType
    title: str = Field(min_length=1)
    summary: str | None = None
    body: str | None = None
    client_id: str | None = None
    account_id: str | None = None
    opportunity_id: str | None = None
    directness_relation: DirectnessRelation = DirectnessRelation.UNKNOWN
    similar_to_client_id: str | None = None
    similarity_reason: str | None = None
    created_at: date | None = None
    updated_at: date | None = None
    author: Person | None = None
    owner_candidates: list[OwnerCandidate] = Field(default_factory=list)
    attendees: list[Person] = Field(default_factory=list)
    sensitivity_labels: list[SensitivityLabel] = Field(default_factory=list)
    source_system: SourceSystem = SourceSystem.LOCAL_FIXTURE
    validation_history: list[ValidationRecord] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_summary_or_body(self) -> Source:
        if not self.summary and not self.body:
            raise ValueError("source requires either summary or body")
        return self

    @model_validator(mode="after")
    def require_similarity_reason_for_similar_client(self) -> Source:
        is_similar_client = self.directness_relation is DirectnessRelation.SIMILAR_CLIENT
        if (self.similar_to_client_id or is_similar_client) and not self.similarity_reason:
            raise ValueError("similar-client sources require similarity_reason")
        return self


class WeakPoint(StrictModel):
    type: WeakPointType
    message: str
    source_id: str | None = None
    claim_id: str | None = None
    severity: Literal["low", "medium", "high"] = "medium"
    metadata: dict[str, Any] = Field(default_factory=dict)


class DimensionScore(StrictModel):
    dimension: RankingDimension
    score: float = Field(ge=0.0, le=1.0)
    label: str
    reason: str
    weak_points: list[WeakPoint] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RankedSource(StrictModel):
    source_id: str
    tier: Tier
    scores: dict[str, DimensionScore]
    reasons: list[str] = Field(default_factory=list)
    weak_points: list[WeakPoint] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExpectedOutcome(StrictModel):
    tier: Tier | None = None
    decision: DecisionType | None = None
    weak_points: list[WeakPointType] = Field(default_factory=list)


class SourceFixture(StrictModel):
    context_need: ContextNeed
    source: Source
    expected: ExpectedOutcome | None = None


class SourceBundle(StrictModel):
    id: str
    title: str
    context_need: ContextNeed
    sources: list[Source] = Field(min_length=1)
    expected: ExpectedOutcome | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
