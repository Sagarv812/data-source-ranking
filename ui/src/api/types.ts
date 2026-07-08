export type HealthResponse = {
  status: string
  service: string
}

export type FixtureKind =
  | 'source'
  | 'bundle'
  | 'review'
  | 'owner_response'
  | 'simulated_retrieval'
  | 'feedback'

export type FixtureSummary = {
  id: string
  kind: FixtureKind
  path: string
  title: string
  object_id: string | null
  bundle_id: string | null
  source_id: string | null
  expected_decision: string | null
  expected_tier: string | null
}

export type FixtureListResponse = {
  fixtures: FixtureSummary[]
  groups: Record<string, FixtureSummary[]>
  counts: Record<string, number>
}

export type ApiRunSummary = {
  run_id: string
  kind: 'decision' | 'agent'
  bundle_id: string
  fixture_id: string
  title: string | null
  created_at: string
  decision: string | null
  final_decision: string | null
}

export type ApiRunReviewEvent = {
  review_event_id: string
  run_id: string
  bundle_id: string
  fixture_id: string
  created_at: string
  request: Record<string, unknown>
  result: Record<string, unknown>
}

export type ApiRunRecord = {
  run_id: string
  kind: 'decision' | 'agent'
  bundle_id: string
  fixture_id: string
  created_at: string
  request: Record<string, unknown>
  result: Record<string, unknown>
  review_events: ApiRunReviewEvent[]
}

export type ApiRunListResponse = {
  runs: ApiRunSummary[]
}

export type FixtureRunRequest = {
  fixture_id: string
}

export type AgentRunRequest = FixtureRunRequest & {
  max_iterations?: number
  owner_response_fixture_id?: string | null
  simulated_retrieval_fixture_id?: string | null
}

export type RiskTolerance = 'low' | 'normal' | 'high'

export type NeededClaimType =
  | 'current_client_concern'
  | 'validated_prior_work'
  | 'likely_account_owner'
  | 'implementation_risk'
  | 'similar_client_context'
  | 'decision_feedback'
  | 'next_step'
  | 'other'

export type SourceType =
  | 'crm_note'
  | 'salesforce_opportunity_note'
  | 'meeting_event'
  | 'meeting_notes'
  | 'proposal'
  | 'deck'
  | 'flowcase_match'
  | 'partner_material'
  | 'human_validated_context'
  | 'prior_handoff'
  | 'other'

export type DirectnessRelation =
  | 'same_client_same_opportunity'
  | 'same_client_adjacent_opportunity'
  | 'same_account_group'
  | 'closely_related_stakeholder'
  | 'similar_client'
  | 'generic_industry'
  | 'weak_match'
  | 'unknown'

export type SourceSystem =
  | 'salesforce'
  | 'calendar'
  | 'drive'
  | 'flowcase'
  | 'human'
  | 'partner_portal'
  | 'local_fixture'
  | 'other'

export type ClaimType =
  | 'client_concern'
  | 'prior_work'
  | 'owner_signal'
  | 'program_signal'
  | 'similar_client_context'
  | 'implementation_risk'
  | 'decision_feedback'
  | 'next_step'
  | 'unsupported_inference'
  | 'other'

export type SensitivityLabel =
  | 'internal_only'
  | 'confidential'
  | 'partner_channel'
  | 'stale_data'
  | 'unsupported_inference'
  | 'none'
  | 'other'

export type Person = {
  id: string
  name: string
  role?: string | null
  role_title?: string | null
  email?: string | null
}

export type OwnerCandidate = {
  id: string
  name: string
  role?: string | null
  role_title?: string | null
  reason: string
  confidence: number
}

export type CustomNeededClaim = {
  id: string
  type: NeededClaimType
  description: string
  required: boolean
  metadata?: Record<string, unknown>
}

export type CustomClaim = {
  id: string
  text: string
  claim_type: ClaimType
  is_inferred?: boolean
  supports_needed_claim_ids?: string[]
  source_ids?: string[]
  metadata?: Record<string, unknown>
}

export type CustomContextNeed = {
  id: string
  client_id: string
  account_id?: string | null
  opportunity_id?: string | null
  email_goal: string
  needed_claims: CustomNeededClaim[]
  risk_tolerance: RiskTolerance
  metadata?: Record<string, unknown>
}

export type CustomSource = {
  id: string
  type: SourceType
  title: string
  summary?: string | null
  body?: string | null
  client_id?: string | null
  account_id?: string | null
  opportunity_id?: string | null
  directness_relation: DirectnessRelation
  similar_to_client_id?: string | null
  similarity_reason?: string | null
  created_at?: string | null
  updated_at?: string | null
  author?: Person | null
  owner_candidates?: OwnerCandidate[]
  attendees?: Person[]
  sensitivity_labels?: SensitivityLabel[]
  source_system: SourceSystem
  claims?: CustomClaim[]
  metadata?: Record<string, unknown>
}

export type CustomSourceBundle = {
  id: string
  title: string
  context_need: CustomContextNeed
  sources: CustomSource[]
  metadata?: Record<string, unknown>
}

export type CustomDecisionRunRequest = {
  bundle: CustomSourceBundle
  as_of?: string
}

export type CustomRankRequest = CustomDecisionRunRequest

export type RankedSource = {
  source_id: string
  tier: 'strong' | 'medium' | 'weak'
  scores: Record<string, {
    dimension: string
    score: number
    label: string
    reason: string
    weak_points: unknown[]
    metadata: Record<string, unknown>
  }>
  reasons: string[]
  weak_points: Array<Record<string, unknown>>
  metadata: Record<string, unknown>
}

export type RankedBundle = {
  id: string
  decision: string
  ranked_sources: RankedSource[]
  reasons: string[]
  weak_points: Array<Record<string, unknown>>
  metadata: Record<string, unknown>
}

export type RunReviewRequest = {
  selected_choice_id: string
  responder_id?: string
  responder_name?: string
  selected_owner_id?: string | null
  selected_owner_name?: string | null
  user_accepts_risk?: boolean
  notes?: string | null
  metadata?: Record<string, unknown>
}

export type ReviewResponseResult = {
  status: string
  accepted: boolean
  applied_effects: string[]
  validation_errors: string[]
  updated_decision: Record<string, unknown> | null
  response: Record<string, unknown>
  metadata: Record<string, unknown>
}

export type RunReviewResponse = {
  run: ApiRunRecord
  review_event: ApiRunReviewEvent
  review_response_result: ReviewResponseResult
}

export type DecisionFeedbackOutcome =
  | 'accepted'
  | 'rejected'
  | 'corrected'
  | 'blocked_confirmed'
  | 'blocked_overridden'
  | 'unknown'

export type SourceFeedbackOutcome =
  | 'accepted'
  | 'rejected'
  | 'corrected'
  | 'unused'
  | 'unknown'

export type RunSourceFeedbackRequest = {
  source_id: string
  outcome: SourceFeedbackOutcome
  reason?: string | null
  metadata?: Record<string, unknown>
}

export type RunFeedbackRequest = {
  decision_outcome: DecisionFeedbackOutcome
  source_outcomes?: RunSourceFeedbackRequest[]
  owner_response_outcome?: string | null
  generated_handoff_accepted?: boolean | null
  correction_notes?: string | null
  metadata?: Record<string, unknown>
}

export type RunFeedbackResponse = {
  feedback_event: Record<string, unknown>
  feedback_snapshot: ReliabilitySnapshot
}

export type ReviewQueueStatus =
  | 'pending_review'
  | 'needs_learning'
  | 'answered'
  | 'needs_context'
  | 'blocked'

export type ReviewQueueItem = {
  run_id: string
  kind: 'decision' | 'agent'
  bundle_id: string
  fixture_id: string
  created_at: string
  decision: string
  status: ReviewQueueStatus
  issue_type: string | null
  question: string | null
  source_count: number
  review_event_count: number
  latest_review_event_id: string | null
  latest_reviewed_at: string | null
  learning_feedback_count: number
}

export type ReviewQueueResponse = {
  items: ReviewQueueItem[]
  counts: Partial<Record<ReviewQueueStatus, number>>
}

export type ResetLocalDataRequest = {
  runs: boolean
  reviews: boolean
  feedback: boolean
}

export type ResetLocalDataResponse = {
  reset: string[]
  counts_before: Record<string, number>
}

export type ReliabilitySnapshot = {
  reliability_defaults: Record<string, number>
  updates: Array<{
    key: string
    scope: string
    static_value: number
    learned_value: number
    delta: number
    source_outcome_count: number
    reasons: string[]
  }>
  metadata: Record<string, unknown>
}
