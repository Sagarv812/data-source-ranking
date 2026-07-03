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
