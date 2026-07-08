import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  ClipboardCheck,
  FileSearch,
  FileText,
  GitBranch,
  ListChecks,
  MessageSquareText,
  PencilLine,
  Route,
  ShieldCheck,
  XCircle,
} from 'lucide-react'
import type { FormEvent, ReactNode } from 'react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { useHealthQuery, useRunQuery, useSubmitRunFeedbackMutation } from '../api/queries'
import type {
  ApiRunRecord,
  DecisionFeedbackOutcome,
  RunFeedbackRequest,
  SourceFeedbackOutcome,
} from '../api/types'
import { AppShell } from '../components/AppShell'
import { DecisionBadge } from '../components/DecisionBadge'
import { StatusBadge } from '../components/StatusBadge'

type ScoreRow = {
  dimension: string
  label: string
  reason: string
  score: number | null
}

export function RunDetailPage() {
  const { runId } = useParams()
  const health = useHealthQuery()
  const run = useRunQuery(runId)
  const submitFeedback = useSubmitRunFeedbackMutation(runId)
  const refreshAll = () => {
    void health.refetch()
    void run.refetch()
  }

  const record = run.data
  const decision = record ? decisionObjectFromRunRecord(record) : null
  const title = record ? recordTitle(record) : ''
  const decisionName = stringField(decision, 'decision')
  const rankedSources = rankedSourcesFromDecision(decision)
  const selectedClaims = uniqueClaims(arrayOfRecords(decision, 'selected_claims'))
  const policyGates = arrayOfRecords(decision, 'policy_gates')
  const decisionAudit = arrayOfRecords(decision, 'audit_trace')
  const approvalPrompt = objectField(decision, 'approval_prompt')
  const loopAudit = arrayOfRecords(objectField(record?.result ?? {}, 'audit_trace'), 'events')
  const auditEvents = loopAudit.length ? loopAudit : decisionAudit
  const citationTitleBySourceId = Object.fromEntries(
    arrayOfRecords(decision, 'source_citations').flatMap((citation) => {
      const sourceId = stringField(citation, 'source_id')
      const title = stringField(citation, 'title')
      return sourceId && title ? [[sourceId, title]] : []
    }),
  )

  return (
    <AppShell apiConnected={health.isSuccess} onRefresh={refreshAll}>
      <div className="space-y-5">
        <Link to="/" className="focus-ring inline-flex min-h-11 items-center gap-2 rounded-lg px-3 text-sm font-semibold text-ink-muted hover:bg-[var(--surface-hover)] hover:text-ink">
          <ArrowLeft size={17} />
          Back to console
        </Link>

        {run.isLoading ? (
          <RunDetailEmpty title="Loading check" text="Fetching the saved evidence decision." />
        ) : run.isError || !record ? (
          <RunDetailEmpty title="Check not found" text="The saved check could not be loaded from the local API." />
        ) : (
          <>
            <section className="workspace-surface overflow-hidden">
              <div className="run-detail-hero">
                <div className="min-w-0">
                  <p className="section-label">Evidence review</p>
                  <h1 className="mt-3 max-w-4xl text-4xl font-bold leading-[1.02] text-ink sm:text-5xl">
                    {title}
                  </h1>
                  <p className="mt-4 max-w-3xl text-base leading-7 text-ink-muted">
                    Review the evidence quality, safety checks, and audit trail for this saved {record.kind === 'agent' ? 'guided check' : 'quick check'}.
                  </p>
                </div>

                <div className="run-detail-verdict">
                  <div className="flex flex-wrap items-center gap-2">
                    {decisionName ? <DecisionBadge decision={decisionName} /> : <StatusBadge tone="neutral">No outcome</StatusBadge>}
                    <StatusBadge tone="neutral">{record.kind === 'agent' ? 'Guided check' : 'Quick check'}</StatusBadge>
                  </div>
                  <div className="mt-5 grid grid-cols-3 gap-2">
                    <DetailMetric label="Confidence" value={confidenceText(decision)} />
                    <DetailMetric label="Evidence" value={String(selectedSourceCount(decision))} />
                    <DetailMetric label="Checks" value={String(policyGates.length)} />
                  </div>
                  {approvalPrompt ? (
                    <Link className="button-primary mt-5 w-full" to={`/review/${record.run_id}`}>
                      Open review
                    </Link>
                  ) : null}
                  <Link className="button-secondary mt-2 w-full" to={`/runs/${record.run_id}/report`}>
                    <FileText size={17} />
                    Open report
                  </Link>
                </div>
              </div>
            </section>

            <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
              <div className="space-y-5">
                <DetailSection icon={<ShieldCheck size={20} />} label="Decision" title="Decision summary">
                  <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(260px,0.55fr)]">
                    <div className="detail-narrative">
                      <p>{detailText(stringField(decision, 'summary')) ?? 'No decision summary was saved for this check.'}</p>
                    </div>
                    <div className="space-y-3">
                      <FactRow label="Next action" value={nextActionLabel(decision)} />
                      <FactRow label="Review state" value={reviewStateText(decision)} />
                      <FactRow label="Created" value={formatRunTime(record.created_at)} />
                    </div>
                  </div>
                </DetailSection>

                <DetailSection icon={<FileSearch size={20} />} label="Selected evidence" title="Supported claims">
                  {selectedClaims.length === 0 ? (
                    <EmptyDetail text="No supported claims were captured." />
                  ) : (
                    <div className="grid gap-3">
                      {selectedClaims.map((claim, index) => (
                        <article className="claim-card" key={`${stringField(claim, 'claim_id') ?? 'claim'}-${index}`}>
                          <p className="claim-card-text">{stringField(claim, 'text') ?? 'Untitled claim'}</p>
                          <div className="mt-3 flex flex-wrap gap-2">
                            <StatusBadge tone="neutral">{humanize(stringField(claim, 'claim_type') ?? 'claim')}</StatusBadge>
                            {arrayField(claim, 'source_ids')?.map((sourceId) => (
                              <span className="source-id-chip" key={String(sourceId)}>
                                {sourceLabel(citationTitleBySourceId, String(sourceId))}
                              </span>
                            ))}
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </DetailSection>

                <DetailSection icon={<GitBranch size={20} />} label="Evidence quality" title="Why each source was trusted">
                  {rankedSources.length === 0 ? (
                    <EmptyDetail text="No source scores were captured." />
                  ) : (
                    <div className="space-y-4">
                      {rankedSources.map((source) => (
                        <SourceEvidenceCard
                          key={stringField(source, 'source_id') ?? JSON.stringify(source)}
                          source={source}
                          sourceTitle={citationTitleBySourceId[stringField(source, 'source_id') ?? '']}
                        />
                      ))}
                    </div>
                  )}
                </DetailSection>
              </div>

              <aside className="space-y-5">
                <DetailSection icon={<ListChecks size={20} />} label="Safety" title="Safety checks" compact>
                  <div className="space-y-2">
                    {policyGates.length ? (
                      policyGates.map((gate) => (
                        <PolicyGateRow gate={gate} key={stringField(gate, 'gate') ?? JSON.stringify(gate)} />
                      ))
                    ) : (
                      <EmptyDetail text="No safety checks were captured." compact />
                    )}
                  </div>
                </DetailSection>

                <PromptPanel decision={decision} />

                {record ? (
                  <FeedbackPanel
                    decision={decision}
                    error={submitFeedback.error}
                    isPending={submitFeedback.isPending}
                    onSubmit={(request) => submitFeedback.mutateAsync(request)}
                    submitted={Boolean(submitFeedback.data)}
                  />
                ) : null}

                <DetailSection icon={<Route size={20} />} label="Audit" title={loopAudit.length ? 'Guided check timeline' : 'Check timeline'} compact>
                  {auditEvents.length ? (
                    <div className="detail-audit-list">
                      {auditEvents.slice(0, 8).map((event, index) => (
                        <AuditEventItem event={event} index={index + 1} key={`${index}-${stringField(event, 'event') ?? stringField(event, 'event_type') ?? 'event'}`} />
                      ))}
                    </div>
                  ) : (
                    <EmptyDetail text="No audit events were captured." compact />
                  )}
                </DetailSection>
              </aside>
            </section>
          </>
        )}
      </div>
    </AppShell>
  )
}

function DetailSection({
  children,
  compact = false,
  icon,
  label,
  title,
}: {
  children: ReactNode
  compact?: boolean
  icon: ReactNode
  label: string
  title: string
}) {
  return (
    <section className="workspace-surface overflow-hidden">
      <div className={compact ? 'detail-section-header-compact' : 'detail-section-header'}>
        <span className="detail-section-icon">{icon}</span>
        <div className="min-w-0">
          <p className="section-label">{label}</p>
          <h2 className="mt-1 text-2xl font-bold leading-tight text-ink">{title}</h2>
        </div>
      </div>
      <div className={compact ? 'p-4 sm:p-5' : 'p-5 sm:p-6'}>{children}</div>
    </section>
  )
}

function DetailMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="detail-metric">
      <p>{label}</p>
      <strong>{value}</strong>
    </div>
  )
}

function FactRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="fact-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function SourceEvidenceCard({
  source,
  sourceTitle,
}: {
  source: Record<string, unknown>
  sourceTitle: string | undefined
}) {
  const tier = stringField(source, 'tier') ?? 'unscored'
  const reasons = stringArrayField(source, 'reasons').slice(0, 3)
  const scores = scoreRows(source).slice(0, 6)

  return (
    <article className="source-evidence-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="break-words text-xl font-bold leading-tight text-ink">{sourceTitle ?? sourceDisplayName(source)}</h3>
          <p className="mt-1 text-sm leading-5 text-ink-muted">{sourceSubtitle(source)}</p>
          <p className="mt-2 text-sm leading-6 text-ink-muted">{detailText(reasons[0]) ?? 'No ranking reason was recorded.'}</p>
        </div>
        <span className="tier-token">{humanize(tier)}</span>
      </div>

      {scores.length ? (
        <div className="mt-5 grid gap-3 md:grid-cols-2">
          {scores.map((score) => (
            <ScoreBar key={score.dimension} score={score} />
          ))}
        </div>
      ) : null}

      {reasons.length > 1 ? (
        <ul className="mt-5 space-y-2">
          {reasons.slice(1).map((reason) => (
            <li className="detail-reason" key={reason}>{detailText(reason)}</li>
          ))}
        </ul>
      ) : null}
    </article>
  )
}

function ScoreBar({ score }: { score: ScoreRow }) {
  const percent = score.score === null ? 0 : Math.round(score.score * 100)

  return (
    <div className="score-row">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="score-row-title">{humanize(score.dimension)}</p>
          <p className="score-row-label">{humanize(score.label)}</p>
        </div>
        <strong>{score.score === null ? 'Not scored' : `${percent}%`}</strong>
      </div>
      <div className="score-track" aria-hidden="true">
        <span style={{ width: `${percent}%` }} />
      </div>
    </div>
  )
}

function PolicyGateRow({ gate }: { gate: Record<string, unknown> }) {
  const status = stringField(gate, 'status') ?? 'unknown'
  const effect = stringField(gate, 'effect') ?? 'informational'

  return (
    <article className="policy-gate-row">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <h3>{safetyCheckLabel(stringField(gate, 'gate') ?? 'safety_check')}</h3>
          <p>{stringField(gate, 'message') ?? effect}</p>
        </div>
        <span className={status === 'triggered' ? 'gate-status gate-status-triggered' : 'gate-status'}>
          {humanize(status)}
        </span>
      </div>
    </article>
  )
}

function PromptPanel({ decision }: { decision: Record<string, unknown> | null }) {
  const approvalPrompt = objectField(decision ?? {}, 'approval_prompt')
  const contextRequest = objectField(decision ?? {}, 'context_request')
  const prompt = approvalPrompt ?? contextRequest

  return (
    <DetailSection icon={<MessageSquareText size={20} />} label="Human input" title={approvalPrompt ? 'Review question' : 'Context needed'} compact>
      {prompt ? (
        <div className="detail-callout">
          <p className="font-bold leading-6 text-ink">{stringField(prompt, 'question') ?? stringField(prompt, 'explanation') ?? 'Human input required.'}</p>
          <p className="mt-2 text-sm leading-6 text-ink-muted">
            {stringField(prompt, 'explanation') ?? stringField(prompt, 'recipient_reason') ?? 'This check produced a human-facing request.'}
          </p>
          {arrayOfRecords(prompt, 'choices').length ? (
            <div className="mt-4 space-y-2">
              {arrayOfRecords(prompt, 'choices').map((choice) => (
                <div className="prompt-choice-row" key={stringField(choice, 'id') ?? JSON.stringify(choice)}>
                  <strong>{stringField(choice, 'label') ?? 'Choice'}</strong>
                  <span>{stringField(choice, 'effect') ?? 'Available response'}</span>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : (
        <EmptyDetail text="No review question or extra context was needed." compact />
      )}
    </DetailSection>
  )
}

type FeedbackChoice = {
  description: string
  icon: ReactNode
  label: string
  outcome: DecisionFeedbackOutcome
  sourceOutcome: SourceFeedbackOutcome
}

const feedbackChoices: FeedbackChoice[] = [
  {
    description: 'The decision and selected evidence were useful as shown.',
    icon: <CheckCircle2 size={18} />,
    label: 'Looks right',
    outcome: 'accepted',
    sourceOutcome: 'accepted',
  },
  {
    description: 'The check helped, but the result needs adjustment.',
    icon: <PencilLine size={18} />,
    label: 'Needs correction',
    outcome: 'corrected',
    sourceOutcome: 'corrected',
  },
  {
    description: 'The decision should not be trusted for this case.',
    icon: <XCircle size={18} />,
    label: 'Wrong result',
    outcome: 'rejected',
    sourceOutcome: 'rejected',
  },
]

function FeedbackPanel({
  decision,
  error,
  isPending,
  onSubmit,
  submitted,
}: {
  decision: Record<string, unknown> | null
  error: unknown
  isPending: boolean
  onSubmit: (request: RunFeedbackRequest) => Promise<unknown>
  submitted: boolean
}) {
  const [selectedOutcome, setSelectedOutcome] = useState<DecisionFeedbackOutcome>('accepted')
  const [notes, setNotes] = useState('')
  const selectedChoice = feedbackChoices.find((choice) => choice.outcome === selectedOutcome) ?? feedbackChoices[0]
  const selectedSources = stringArrayField(decision, 'selected_sources')
  const decisionName = stringField(decision, 'decision')

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const sourceOutcomes = selectedSources.map((sourceId) => ({
      source_id: sourceId,
      outcome: selectedChoice.sourceOutcome,
      reason: `${selectedChoice.label} feedback from run detail.`,
      metadata: {
        submitted_from: 'run_detail_feedback',
      },
    }))
    await onSubmit({
      decision_outcome: selectedOutcome,
      source_outcomes: sourceOutcomes,
      generated_handoff_accepted: decisionName === 'auto_handoff' ? selectedOutcome === 'accepted' : null,
      correction_notes: notes.trim() || null,
      metadata: {
        submitted_from: 'run_detail_feedback',
        selected_source_count: selectedSources.length,
      },
    })
  }

  return (
    <DetailSection icon={<ClipboardCheck size={20} />} label="Feedback" title="Outcome feedback" compact>
      <form className="space-y-4" onSubmit={(event) => void handleSubmit(event)}>
        <div className="feedback-choice-grid">
          {feedbackChoices.map((choice) => {
            const selected = choice.outcome === selectedOutcome
            return (
              <button
                className={selected ? 'feedback-choice feedback-choice-selected' : 'feedback-choice'}
                key={choice.outcome}
                type="button"
                onClick={() => setSelectedOutcome(choice.outcome)}
              >
                <span className="feedback-choice-icon">{choice.icon}</span>
                <span>
                  <strong>{choice.label}</strong>
                  <small>{choice.description}</small>
                </span>
              </button>
            )
          })}
        </div>

        <div className="feedback-impact">
          <p className="section-label">Reliability impact</p>
          <p>
            {selectedSources.length
              ? `${selectedSources.length} selected evidence source${selectedSources.length === 1 ? '' : 's'} will be marked ${selectedChoice.sourceOutcome}.`
              : 'No selected evidence sources will be changed.'}
          </p>
        </div>

        <label className="block">
          <span className="field-label">Notes</span>
          <textarea
            className="field mt-2 min-h-24 py-3 leading-6"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="What should future checks learn from this?"
          />
        </label>

        {submitted ? (
          <div className="feedback-saved">
            <CheckCircle2 size={17} />
            <span>Feedback saved. Reliability signals will use it on future checks.</span>
          </div>
        ) : null}

        {error ? (
          <div className="feedback-error">
            <AlertCircle size={17} />
            <span>{errorText(error)}</span>
          </div>
        ) : null}

        <button className="button-primary w-full" type="submit" disabled={isPending}>
          {isPending ? 'Saving feedback...' : 'Save feedback'}
        </button>
      </form>
    </DetailSection>
  )
}

function AuditEventItem({ event, index }: { event: Record<string, unknown>; index: number }) {
  return (
    <article className="audit-event-item">
      <span>{String(index).padStart(2, '0')}</span>
      <div className="min-w-0">
        <h3>{auditEventTitle(event)}</h3>
        <p>{detailText(stringField(event, 'message') ?? stringField(event, 'detail')) ?? 'Check event recorded.'}</p>
      </div>
    </article>
  )
}

function EmptyDetail({ compact = false, text }: { compact?: boolean; text: string }) {
  return (
    <div className={compact ? 'empty-detail empty-detail-compact' : 'empty-detail'}>
      <ClipboardCheck size={18} />
      <span>{text}</span>
    </div>
  )
}

function RunDetailEmpty({ text, title }: { text: string; title: string }) {
  return (
    <section className="workspace-surface p-6">
      <p className="section-label">Evidence review</p>
      <h1 className="mt-3 text-3xl font-bold text-ink">{title}</h1>
      <p className="mt-3 text-sm leading-6 text-ink-muted">{text}</p>
    </section>
  )
}

function decisionObjectFromRunRecord(run: ApiRunRecord) {
  const finalDecision = objectField(run.result, 'final_decision')
  const initialDecision = objectField(run.result, 'initial_decision')
  if (finalDecision) return finalDecision
  if (stringField(run.result, 'decision')) return run.result
  return initialDecision
}

function recordTitle(record: ApiRunRecord) {
  const scenarioTitle = stringField(record.request, 'scenario_title')
  const bundle = objectField(record.request, 'bundle')
  return scenarioTitle ?? stringField(bundle, 'title') ?? compactFixtureId(record.fixture_id)
}

function rankedSourcesFromDecision(decision: Record<string, unknown> | null) {
  return arrayOfRecords(objectField(decision ?? {}, 'ranked_bundle'), 'ranked_sources')
}

function scoreRows(source: Record<string, unknown>): ScoreRow[] {
  const scores = objectField(source, 'scores')
  if (!scores) return []
  return Object.entries(scores).flatMap(([dimension, value]) => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return []
    const record = value as Record<string, unknown>
    return [{
      dimension,
      label: stringField(record, 'label') ?? 'recorded',
      reason: stringField(record, 'reason') ?? '',
      score: numberField(record, 'score'),
    }]
  })
}

function confidenceText(decision: Record<string, unknown> | null) {
  const confidence = objectField(decision ?? {}, 'confidence')
  const label = stringField(confidence, 'label')
  const score = numberField(confidence, 'score')
  if (label && typeof score === 'number') return `${humanize(label)} · ${Math.round(score * 100)}%`
  if (label) return humanize(label)
  return 'Not scored'
}

function selectedSourceCount(decision: Record<string, unknown> | null) {
  return arrayField(decision ?? {}, 'selected_sources')?.length ?? 0
}

function uniqueClaims(claims: Record<string, unknown>[]) {
  const seen = new Set<string>()
  return claims.filter((claim) => {
    const key = stringField(claim, 'claim_id') ?? stringField(claim, 'text') ?? JSON.stringify(claim)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function nextActionLabel(decision: Record<string, unknown> | null) {
  const label = stringField(objectField(decision ?? {}, 'next_action'), 'label')
  const labels: Record<string, string> = {
    'ask user to review': 'Ask for review',
    ask_user_to_review: 'Ask for review',
    auto_handoff: 'Send handoff',
    block_output: 'Stop check',
    generate_context_request: 'Request context',
  }
  const key = label?.toLowerCase().replaceAll('_', ' ')
  return key ? labels[key] ?? humanize(label ?? key) : 'No next action'
}

function reviewStateText(decision: Record<string, unknown> | null) {
  if (objectField(decision ?? {}, 'approval_prompt')) return 'Prompt open'
  if (objectField(decision ?? {}, 'context_request')) return 'Needs context'
  if (objectField(decision ?? {}, 'blocked_output')) return 'Blocked'
  return 'Clear'
}

function objectField(value: Record<string, unknown> | null | undefined, key: string) {
  const field = value?.[key]
  return field && typeof field === 'object' && !Array.isArray(field)
    ? (field as Record<string, unknown>)
    : null
}

function arrayField(value: Record<string, unknown> | null | undefined, key: string) {
  const field = value?.[key]
  return Array.isArray(field) ? field : null
}

function arrayOfRecords(value: Record<string, unknown> | null | undefined, key: string) {
  return (arrayField(value, key) ?? []).filter(
    (item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object' && !Array.isArray(item),
  )
}

function stringArrayField(value: Record<string, unknown> | null | undefined, key: string) {
  return (arrayField(value, key) ?? []).filter((item): item is string => typeof item === 'string')
}

function stringField(value: Record<string, unknown> | null | undefined, key: string) {
  const field = value?.[key]
  return typeof field === 'string' ? field : null
}

function numberField(value: Record<string, unknown> | null | undefined, key: string) {
  const field = value?.[key]
  return typeof field === 'number' ? field : null
}

function errorText(error: unknown) {
  return error instanceof Error ? error.message : 'Feedback could not be saved.'
}

function compactFixtureId(fixtureId: string) {
  return fixtureId
    .split('/')
    .at(-1)
    ?.replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase()) ?? fixtureId
}

function compactSourceId(sourceId: string) {
  return sourceId
    .replace(/^src_/, '')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function sourceDisplayName(source: Record<string, unknown>) {
  const metadata = objectField(source, 'metadata')
  const sourceType = stringField(metadata, 'source_type')
  if (sourceType) return `${humanize(sourceType)} evidence`
  return compactSourceId(stringField(source, 'source_id') ?? 'source evidence')
}

function sourceSubtitle(source: Record<string, unknown>) {
  const metadata = objectField(source, 'metadata')
  const sourceType = stringField(metadata, 'source_type')
  if (sourceType) return humanize(sourceType)
  return 'Evidence source'
}

function sourceLabel(citationTitleBySourceId: Record<string, string>, sourceId: string) {
  return citationTitleBySourceId[sourceId] ?? compactSourceId(sourceId)
}

function safetyCheckLabel(gate: string) {
  const labels: Record<string, string> = {
    required_claims_have_usable_coverage: 'Required claims have evidence',
    required_claims_have_strong_coverage: 'Required claims are strongly supported',
    sensitivity_allows_automation: 'Sensitivity allows automation',
    sensitive_evidence_overlap_absent: 'No sensitive overlap',
    directional_context_review_absent: 'No directional context review needed',
    old_proposal_review_absent: 'No stale proposal review needed',
    stale_unvalidated_source_absent: 'No stale unvalidated source',
    unsupported_inference_absent: 'No unsupported inference',
    owner_signal_available: 'Owner signal available',
  }
  return labels[gate] ?? humanize(gate)
}

function auditEventTitle(event: Record<string, unknown>) {
  const labels: Record<string, string> = {
    action_selected: 'Next action selected',
    bundle_loaded: 'Evidence set loaded',
    final_decision_recorded: 'Final decision recorded',
    initial_decision_recorded: 'First decision recorded',
    sources_ranked: 'Evidence scored',
  }

  const explicitTitle = stringField(event, 'title')
  if (explicitTitle) {
    const titleKey = explicitTitle.toLowerCase().replaceAll(' ', '_')
    return labels[titleKey] ?? explicitTitle
  }

  const eventName = stringField(event, 'event') ?? stringField(event, 'event_type') ?? 'audit_event'
  return labels[eventName] ?? humanize(eventName)
}

function detailText(value: string | null | undefined) {
  if (!value) return null

  const dimensionMatch = value.match(/^([a-z_]+):\s*(.+)$/)
  const withoutScore = (dimensionMatch ? dimensionMatch[2] : value)
    .replace(/\bAuthority score is [\d.]+\.?/gi, '')
    .replace(/\bauto_handoff\b/gi, 'ready to send')
    .replace(/\bgenerate_context_request\b/gi, 'needs more context')
    .replace(/\bneeds_user_review\b/gi, 'review required')
    .replace(/\bpolicy gates\b/gi, 'safety checks')
    .replace(/\bstarter decision\b/gi, 'recommendation')
    .replace(/\bthrough the deterministic evidence scorer\b/gi, 'for quality and fit')
    .replace(/\bthe deterministic decision engine\b/gi, 'the decision engine')
    .replace(/\bevidence bundle\b/gi, 'evidence set')
    .replace(/\bagent run\b/gi, 'guided check')
    .replace(/\bfirst loop decision\b/gi, 'first decision')
    .replace(/\bdecision next action\b/gi, 'recommended next action')
    .replace(/\bthe loop selected\b/gi, 'the guided check selected')
    .replace(/\branked sources\b/gi, 'scored evidence')
    .replace(/\brequired needed claims\b/gi, 'required claims')
    .replace(/\s{2,}/g, ' ')
    .trim()

  const sentence = capitalizeFirst(withoutScore.endsWith('.') ? withoutScore : `${withoutScore}.`)
  if (!dimensionMatch) return sentence
  return `${humanize(dimensionMatch[1])}: ${sentence}`
}

function capitalizeFirst(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

function formatRunTime(createdAt: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(createdAt))
}

function humanize(value: string) {
  return value
    .replaceAll('_', ' ')
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .replace(/\bApi\b/g, 'API')
    .replace(/\bCrm\b/g, 'CRM')
    .replace(/\bQbr\b/g, 'QBR')
}
