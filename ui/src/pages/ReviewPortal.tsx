import {
  ArrowLeft,
  CheckCircle2,
  ClipboardCheck,
  FileSearch,
  MessageSquareText,
  ShieldAlert,
  UserCheck,
} from 'lucide-react'
import type { FormEvent, ReactNode } from 'react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { useHealthQuery, useRunQuery, useSubmitRunReviewMutation } from '../api/queries'
import type { ApiRunRecord } from '../api/types'
import { AppShell } from '../components/AppShell'
import { DecisionBadge } from '../components/DecisionBadge'
import { StatusBadge } from '../components/StatusBadge'

type OwnerOption = {
  id: string
  name: string
  role: string
  reason: string
  sourceTitle: string
}

export function ReviewPortal() {
  const { runId } = useParams()
  const health = useHealthQuery()
  const isLanding = !runId || runId === 'local'
  const run = useRunQuery(isLanding ? undefined : runId)
  const submitReview = useSubmitRunReviewMutation(isLanding ? undefined : runId)
  const [selectedChoiceId, setSelectedChoiceId] = useState('')
  const [selectedOwnerId, setSelectedOwnerId] = useState('')
  const [manualOwnerName, setManualOwnerName] = useState('')
  const [acceptsRisk, setAcceptsRisk] = useState(false)
  const [notes, setNotes] = useState('')

  const record = run.data
  const decision = record ? decisionObjectFromRunRecord(record) : null
  const approvalPrompt = objectField(decision, 'approval_prompt')
  const contextRequest = objectField(decision, 'context_request')
  const choices = useMemo(() => arrayOfRecords(approvalPrompt, 'choices'), [approvalPrompt])
  const selectedChoice = choices.find((choice) => stringField(choice, 'id') === selectedChoiceId) ?? null
  const ownerOptions = useMemo(() => ownerOptionsFromPrompt(approvalPrompt), [approvalPrompt])
  const latestResult = latestReviewResult(record)
  const promptSourceIds = stringArrayField(approvalPrompt, 'source_ids')
  const sourceTitles = sourceTitlesFromPrompt(approvalPrompt)
  const reviewable = Boolean(approvalPrompt)
  const completed = Boolean(latestResult)
  const ownerRequired = selectedChoiceId === 'choose_owner'
  const riskRequired = Boolean(objectField(selectedChoice, 'metadata')?.requires_user_acceptance)
  const selectedOwner = ownerOptions.find((owner) => owner.id === selectedOwnerId) ?? null
  const canSubmit = reviewable
    && selectedChoiceId
    && (!ownerRequired || Boolean(selectedOwnerId || manualOwnerName.trim()))
    && (!riskRequired || acceptsRisk)
    && !submitReview.isPending

  useEffect(() => {
    if (!approvalPrompt) {
      setSelectedChoiceId('')
      return
    }
    const recommended = stringField(approvalPrompt, 'recommended_action')
    const defaultChoice = choices.find((choice) => stringField(choice, 'id') === recommended) ?? choices[0]
    setSelectedChoiceId(stringField(defaultChoice, 'id') ?? '')
    setSelectedOwnerId('')
    setManualOwnerName('')
    setAcceptsRisk(false)
    setNotes('')
  }, [approvalPrompt, choices])

  const refreshAll = () => {
    void health.refetch()
    void run.refetch()
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canSubmit) return
    const ownerName = selectedOwner?.name ?? (manualOwnerName.trim() || null)
    await submitReview.mutateAsync({
      selected_choice_id: selectedChoiceId,
      responder_id: 'local_user',
      responder_name: 'Local User',
      selected_owner_id: ownerRequired ? selectedOwnerId || ownerName : null,
      selected_owner_name: ownerRequired ? ownerName : null,
      user_accepts_risk: acceptsRisk,
      notes: notes.trim() || null,
      metadata: {
        submitted_from: 'review_portal',
      },
    })
  }

  return (
    <AppShell apiConnected={health.isSuccess} onRefresh={refreshAll}>
      <div className="space-y-5">
        <Link to="/" className="focus-ring inline-flex min-h-11 items-center gap-2 rounded-lg px-3 text-sm font-semibold text-ink-muted hover:bg-[var(--surface-hover)] hover:text-ink">
          <ArrowLeft size={17} />
          Back to console
        </Link>

        {isLanding ? (
          <ReviewLanding />
        ) : run.isLoading ? (
          <ReviewEmpty title="Loading review" text="Fetching the saved check and reviewer question." />
        ) : run.isError || !record ? (
          <ReviewEmpty title="Review not found" text="Open a saved check from history to review it." />
        ) : (
          <>
            <section className="workspace-surface overflow-hidden">
              <div className="review-hero">
                <div className="min-w-0">
                  <p className="section-label">Review workspace</p>
                  <h1 className="mt-3 max-w-4xl text-4xl font-bold leading-[1.02] text-ink sm:text-5xl">
                    {compactFixtureId(record.fixture_id)}
                  </h1>
                  <p className="mt-4 max-w-3xl text-base leading-7 text-ink-muted">
                    Answer the smallest human question needed before this evidence can move forward.
                  </p>
                </div>
                <div className="review-state-card">
                  <div className="flex flex-wrap items-center gap-2">
                    <DecisionBadge decision={decisionName(decision) ?? 'needs_user_review'} />
                    <StatusBadge tone={completed ? 'mint' : reviewable ? 'apricot' : 'neutral'}>
                      {completed ? 'Review saved' : reviewable ? 'Awaiting answer' : 'Read only'}
                    </StatusBadge>
                  </div>
                  <p className="mt-4 text-sm leading-6 text-ink-muted">
                    {completed
                      ? 'The latest reviewer answer is stored with this check.'
                      : reviewable
                        ? 'Choose one response, add the required context, and save the reviewer decision.'
                        : 'This check does not have an approval question to answer.'}
                  </p>
                </div>
              </div>
            </section>

            <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
              <div className="space-y-5">
                {reviewable ? (
                  <form className="workspace-surface overflow-hidden" onSubmit={(event) => void handleSubmit(event)}>
                    <ReviewSectionHeader icon={<MessageSquareText size={20} />} label="Reviewer question" title={stringField(approvalPrompt, 'question') ?? 'Review needed'} />
                    <div className="p-5 sm:p-6">
                      <div className="review-question-panel">
                        <p className="text-base font-bold leading-7 text-ink">
                          {stringField(approvalPrompt, 'explanation') ?? 'Review this evidence before continuing.'}
                        </p>
                        <div className="mt-4 flex flex-wrap gap-2">
                          <StatusBadge tone="apricot">Recommended: {choiceLabel(choices, stringField(approvalPrompt, 'recommended_action'))}</StatusBadge>
                          <StatusBadge tone="neutral">{humanize(stringField(approvalPrompt, 'issue_type') ?? 'review')}</StatusBadge>
                        </div>
                      </div>

                      <div className="mt-5 grid gap-3">
                        {choices.map((choice) => {
                          const choiceId = stringField(choice, 'id') ?? ''
                          const selected = choiceId === selectedChoiceId
                          return (
                            <button
                              className={selected ? 'review-choice-card review-choice-card-selected' : 'review-choice-card'}
                              key={choiceId || JSON.stringify(choice)}
                              type="button"
                              onClick={() => {
                                setSelectedChoiceId(choiceId)
                                setAcceptsRisk(false)
                              }}
                            >
                              <span className="review-choice-mark" aria-hidden="true">
                                {selected ? <CheckCircle2 size={18} /> : null}
                              </span>
                              <span className="min-w-0">
                                <strong>{stringField(choice, 'label') ?? 'Choice'}</strong>
                                <span>{stringField(choice, 'effect') ?? 'Use this reviewer response.'}</span>
                              </span>
                            </button>
                          )
                        })}
                      </div>

                      {ownerRequired ? (
                        <div className="review-followup-panel mt-5">
                          <p className="section-label">Owner validation</p>
                          <h2 className="mt-2 text-xl font-bold leading-tight text-ink">Who should own this context?</h2>
                          {ownerOptions.length ? (
                            <div className="mt-4 grid gap-2">
                              {ownerOptions.map((owner) => (
                                <button
                                  className={owner.id === selectedOwnerId ? 'owner-option owner-option-selected' : 'owner-option'}
                                  key={`${owner.id}-${owner.sourceTitle}`}
                                  type="button"
                                  onClick={() => {
                                    setSelectedOwnerId(owner.id)
                                    setManualOwnerName('')
                                  }}
                                >
                                  <span className="font-bold text-ink">{owner.name}</span>
                                  <span>{owner.role}</span>
                                  <small>{owner.reason}</small>
                                </button>
                              ))}
                            </div>
                          ) : (
                            <label className="mt-4 block">
                              <span className="field-label">Owner name</span>
                              <input
                                className="field mt-2"
                                value={manualOwnerName}
                                onChange={(event) => setManualOwnerName(event.target.value)}
                                placeholder="Name the person who should validate this context"
                              />
                            </label>
                          )}
                        </div>
                      ) : null}

                      {riskRequired ? (
                        <label className="review-risk-check mt-5">
                          <input
                            type="checkbox"
                            checked={acceptsRisk}
                            onChange={(event) => setAcceptsRisk(event.target.checked)}
                          />
                          <span>
                            <strong>I accept this review risk.</strong>
                            <small>This choice will be saved with the reviewer decision and audit trail.</small>
                          </span>
                        </label>
                      ) : null}

                      <label className="mt-5 block">
                        <span className="field-label">Reviewer notes</span>
                        <textarea
                          className="field mt-2 min-h-28 py-3 leading-6"
                          value={notes}
                          onChange={(event) => setNotes(event.target.value)}
                          placeholder="Add context for future reviewers"
                        />
                      </label>

                      {submitReview.error ? (
                        <div className="mt-4 flex items-start gap-3 rounded-lg border border-rose-300 bg-rose-100/70 p-3 text-sm leading-6 text-rose-900">
                          <ShieldAlert className="mt-0.5 shrink-0" size={17} />
                          <span>{errorText(submitReview.error)}</span>
                        </div>
                      ) : null}

                      <div className="mt-5 flex flex-wrap items-center justify-end gap-3 border-t border-border-soft/80 pt-5">
                        <Link className="button-secondary" to={`/runs/${record.run_id}`}>
                          View check
                        </Link>
                        <button className="button-primary" type="submit" disabled={!canSubmit}>
                          {submitReview.isPending ? 'Saving...' : 'Save review'}
                        </button>
                      </div>
                    </div>
                  </form>
                ) : (
                  <ReadOnlyReviewState contextRequest={contextRequest} />
                )}

                {latestResult ? <ReviewResult result={latestResult} /> : null}
              </div>

              <aside className="space-y-5">
                <ReviewEvidencePanel
                  decision={decision}
                  promptSourceIds={promptSourceIds}
                  sourceTitles={sourceTitles}
                />
                <ReviewBlock icon={<UserCheck size={20} />} title="Reviewer identity">
                  Local User is recorded as the reviewer for this repo-contained workflow.
                </ReviewBlock>
              </aside>
            </section>
          </>
        )}
      </div>
    </AppShell>
  )
}

function ReviewLanding() {
  return (
    <section className="workspace-surface p-6">
      <p className="section-label">Review workspace</p>
      <h1 className="mt-3 max-w-3xl text-4xl font-bold leading-[1.02] text-ink sm:text-5xl">
        Open a saved check that needs reviewer input.
      </h1>
      <p className="mt-4 max-w-2xl text-base leading-7 text-ink-muted">
        Review tasks appear from the console history when a check has an approval question.
      </p>
      <Link className="button-primary mt-6" to="/">
        Go to console
      </Link>
    </section>
  )
}

function ReadOnlyReviewState({ contextRequest }: { contextRequest: Record<string, unknown> | null }) {
  return (
    <section className="workspace-surface overflow-hidden">
      <ReviewSectionHeader icon={<ClipboardCheck size={20} />} label="Review status" title="No approval question" />
      <div className="p-5 sm:p-6">
        {contextRequest ? (
          <div className="detail-callout">
            <p className="font-bold leading-6 text-ink">{stringField(contextRequest, 'question') ?? 'Context needed.'}</p>
            <p className="mt-2 text-sm leading-6 text-ink-muted">
              {stringField(contextRequest, 'recipient_reason') ?? 'This check needs more information before review can continue.'}
            </p>
          </div>
        ) : (
          <div className="empty-detail">
            <ClipboardCheck size={18} />
            <span>This check has no approval question to answer.</span>
          </div>
        )}
      </div>
    </section>
  )
}

function ReviewEvidencePanel({
  decision,
  promptSourceIds,
  sourceTitles,
}: {
  decision: Record<string, unknown> | null
  promptSourceIds: string[]
  sourceTitles: Record<string, string>
}) {
  const selectedClaims = arrayOfRecords(decision, 'selected_claims')
  const citations = arrayOfRecords(decision, 'source_citations')
  const promptSources = promptSourceIds.length
    ? promptSourceIds
    : citations.slice(0, 4).flatMap((citation) => stringField(citation, 'source_id') ?? [])
  const promptSourceSet = new Set(promptSources)
  const relevantClaims = uniqueClaims(selectedClaims.filter((claim) => {
    const sourceIds = stringArrayField(claim, 'source_ids')
    return promptSourceSet.size === 0 || sourceIds.some((sourceId) => promptSourceSet.has(sourceId))
  }))

  return (
    <section className="workspace-surface overflow-hidden">
      <ReviewSectionHeader icon={<FileSearch size={20} />} label="Evidence context" title="What reviewer sees" compact />
      <div className="space-y-4 p-4 sm:p-5">
        <div className="space-y-2">
          <p className="section-label">Sources in question</p>
          {promptSources.length ? (
            <div className="flex flex-wrap gap-2">
              {promptSources.map((sourceId) => (
                <span className="source-id-chip" key={sourceId}>
                  {sourceTitles[sourceId] ?? sourceLabel(citations, sourceId)}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-sm leading-6 text-ink-muted">No specific source was attached to this prompt.</p>
          )}
        </div>

        <div className="space-y-2">
          <p className="section-label">Supported claims</p>
          {relevantClaims.length ? (
            <div className="grid gap-2">
              {relevantClaims.slice(0, 4).map((claim, index) => (
                <article className="review-mini-claim" key={`${stringField(claim, 'claim_id') ?? 'claim'}-${index}`}>
                  <p>{stringField(claim, 'text') ?? 'Untitled claim'}</p>
                  <span>{humanize(stringField(claim, 'claim_type') ?? 'claim')}</span>
                </article>
              ))}
            </div>
          ) : (
            <p className="text-sm leading-6 text-ink-muted">No selected claim is attached to this review question yet.</p>
          )}
        </div>
      </div>
    </section>
  )
}

function ReviewResult({ result }: { result: Record<string, unknown> }) {
  const accepted = booleanField(result, 'accepted')
  const updatedDecision = objectField(result, 'updated_decision')
  const effects = stringArrayField(result, 'applied_effects')
  const errors = stringArrayField(result, 'validation_errors')

  return (
    <section className="workspace-surface overflow-hidden">
      <ReviewSectionHeader icon={<CheckCircle2 size={20} />} label="Saved answer" title={accepted ? 'Review accepted' : 'Review needs correction'} />
      <div className="grid gap-4 p-5 sm:p-6 lg:grid-cols-[minmax(0,1fr)_minmax(220px,0.42fr)]">
        <div className="detail-narrative">
          <p>
            {accepted
              ? 'The reviewer answer was validated and attached to this check.'
              : errors.join(' ') || 'The review answer could not be accepted.'}
          </p>
        </div>
        <div className="space-y-3">
          <FactRow label="Status" value={accepted ? 'Accepted' : 'Rejected'} />
          <FactRow label="Updated outcome" value={decisionLabel(stringField(updatedDecision, 'decision'))} />
          <FactRow label="Effects" value={effects.length ? String(effects.length) : '0'} />
        </div>
        {effects.length ? (
          <div className="lg:col-span-2">
            <p className="section-label">Applied effects</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {effects.map((effect) => (
                <StatusBadge key={effect} tone="sky">{effectLabel(effect)}</StatusBadge>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  )
}

function ReviewBlock({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <section className="workspace-surface overflow-hidden p-5">
      <span className="detail-section-icon">{icon}</span>
      <h2 className="mt-4 text-xl font-bold leading-tight">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-ink-muted">{children}</p>
    </section>
  )
}

function ReviewSectionHeader({
  compact = false,
  icon,
  label,
  title,
}: {
  compact?: boolean
  icon: ReactNode
  label: string
  title: string
}) {
  return (
    <div className={compact ? 'detail-section-header-compact' : 'detail-section-header'}>
      <span className="detail-section-icon">{icon}</span>
      <div className="min-w-0">
        <p className="section-label">{label}</p>
        <h2 className="mt-1 text-2xl font-bold leading-tight text-ink">{title}</h2>
      </div>
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

function ReviewEmpty({ text, title }: { text: string; title: string }) {
  return (
    <section className="workspace-surface p-6">
      <p className="section-label">Review workspace</p>
      <h1 className="mt-3 text-3xl font-bold text-ink">{title}</h1>
      <p className="mt-3 text-sm leading-6 text-ink-muted">{text}</p>
    </section>
  )
}

function latestReviewResult(record: ApiRunRecord | undefined) {
  const latestEvent = record?.review_events.at(-1)
  return latestEvent?.result ?? null
}

function decisionObjectFromRunRecord(run: ApiRunRecord) {
  const finalDecision = objectField(run.result, 'final_decision')
  const initialDecision = objectField(run.result, 'initial_decision')
  if (finalDecision) return finalDecision
  if (stringField(run.result, 'decision')) return run.result
  return initialDecision
}

function decisionName(decision: Record<string, unknown> | null) {
  return stringField(decision, 'decision')
}

function decisionLabel(decision: string | null) {
  const labels: Record<string, string> = {
    auto_handoff: 'Ready to send',
    blocked: 'Blocked',
    generate_context_request: 'Needs context',
    needs_user_review: 'Needs review',
  }
  return decision ? labels[decision] ?? humanize(decision) : 'Recorded'
}

function effectLabel(effect: string) {
  const labels: Record<string, string> = {
    caveat_accepted: 'Caveat accepted',
    claim_removed: 'Claim removed',
    owner_selected: 'Owner selected',
    response_validated: 'Response validated',
    risk_accepted: 'Risk accepted',
    source_excluded: 'Source excluded',
  }
  const choiceLabels: Record<string, string> = {
    choose_owner: 'Choose owner',
    exclude_sensitive_source: 'Exclude sensitive source',
    remove_claim: 'Remove claim',
    request_validation: 'Request validation',
    skip_source: 'Skip source',
    stop_automation: 'Stop automation',
    use_cautious_wording: 'Use cautiously',
    use_directional_with_label: 'Use as directional',
    use_historical_context: 'Use as historical context',
    use_without_owner: 'Use carefully',
  }
  if (effect.startsWith('choice:')) {
    const choiceId = effect.replace(/^choice:/, '')
    return `Choice: ${choiceLabels[choiceId] ?? humanize(choiceId)}`
  }
  return labels[effect] ?? humanize(effect)
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

function ownerOptionsFromPrompt(prompt: Record<string, unknown> | null): OwnerOption[] {
  const metadata = objectField(prompt, 'metadata')
  const ownersBySource = objectField(metadata, 'owner_candidates')
  const sourceTitles = sourceTitlesFromPrompt(prompt)
  if (!ownersBySource) return []

  const seen = new Set<string>()
  return Object.entries(ownersBySource).flatMap(([sourceId, value]) => {
    if (!Array.isArray(value)) return []
    return value.flatMap((candidate) => {
      if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) return []
      const record = candidate as Record<string, unknown>
      const id = stringField(record, 'id')
      const name = stringField(record, 'name')
      if (!id || !name || seen.has(id)) return []
      seen.add(id)
      return [{
        id,
        name,
        role: stringField(record, 'role_title') ?? humanize(stringField(record, 'role') ?? 'owner'),
        reason: stringField(record, 'reason') ?? 'Recommended owner candidate.',
        sourceTitle: sourceTitles[sourceId] ?? compactFixtureId(sourceId),
      }]
    })
  })
}

function sourceTitlesFromPrompt(prompt: Record<string, unknown> | null) {
  const metadata = objectField(prompt, 'metadata')
  const sourceTitles = objectField(metadata, 'source_titles')
  if (!sourceTitles) return {}
  return Object.fromEntries(
    Object.entries(sourceTitles).flatMap(([sourceId, title]) => (
      typeof title === 'string' ? [[sourceId, title]] : []
    )),
  )
}

function choiceLabel(choices: Record<string, unknown>[], choiceId: string | null) {
  if (!choiceId) return 'Review choice'
  const choice = choices.find((item) => stringField(item, 'id') === choiceId)
  return stringField(choice, 'label') ?? humanize(choiceId)
}

function sourceLabel(citations: Record<string, unknown>[], sourceId: string) {
  const citation = citations.find((item) => stringField(item, 'source_id') === sourceId)
  return stringField(citation, 'title') ?? compactFixtureId(sourceId)
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

function booleanField(value: Record<string, unknown> | null | undefined, key: string) {
  const field = value?.[key]
  return typeof field === 'boolean' ? field : false
}

function compactFixtureId(fixtureId: string) {
  return fixtureId
    .split('/')
    .at(-1)
    ?.replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase()) ?? fixtureId
}

function humanize(value: string) {
  return value
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .replace(/\bCrm\b/g, 'CRM')
    .replace(/\bQbr\b/g, 'QBR')
}

function errorText(error: unknown) {
  return error instanceof Error ? error.message : 'Review could not be saved.'
}
