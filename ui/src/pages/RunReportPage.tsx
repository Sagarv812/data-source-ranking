import {
  AlertCircle,
  ArrowLeft,
  Clipboard,
  FileText,
  GitBranch,
  ListChecks,
  Printer,
  Route,
  ShieldCheck,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { useHealthQuery, useRunQuery } from '../api/queries'
import type { ApiRunRecord } from '../api/types'
import { AppShell } from '../components/AppShell'
import { DecisionBadge } from '../components/DecisionBadge'
import { StatusBadge } from '../components/StatusBadge'

type ScoreRow = {
  dimension: string
  label: string
  score: number | null
}

type ReportModel = {
  auditEvents: Record<string, unknown>[]
  citationTitleBySourceId: Record<string, string>
  createdAt: string
  decision: Record<string, unknown> | null
  decisionName: string | null
  policyGates: Record<string, unknown>[]
  rankedSources: Record<string, unknown>[]
  selectedClaims: Record<string, unknown>[]
  title: string
}

export function RunReportPage() {
  const { runId } = useParams()
  const health = useHealthQuery()
  const run = useRunQuery(runId)
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle')
  const report = useMemo(() => (run.data ? reportModel(run.data) : null), [run.data])
  const refreshAll = () => {
    void health.refetch()
    void run.refetch()
  }

  async function handleCopy() {
    if (!report) return
    try {
      await navigator.clipboard.writeText(reportText(report))
      setCopyState('copied')
    } catch {
      setCopyState('failed')
    }
  }

  return (
    <AppShell apiConnected={health.isSuccess} onRefresh={refreshAll}>
      <div className="mx-auto max-w-5xl space-y-5">
        <div className="report-actions flex flex-wrap items-center justify-between gap-3">
          <Link to={runId ? `/runs/${runId}` : '/'} className="button-secondary">
            <ArrowLeft size={17} />
            Back to detail
          </Link>
          <div className="flex flex-wrap gap-2">
            <button
              className="button-secondary"
              type="button"
              onClick={() => void handleCopy()}
              disabled={!report}
            >
              <Clipboard size={17} />
              {copyState === 'copied' ? 'Copied' : 'Copy summary'}
            </button>
            <button className="button-primary" type="button" onClick={() => window.print()} disabled={!report}>
              <Printer size={17} />
              Print / PDF
            </button>
          </div>
        </div>

        {copyState === 'failed' ? (
          <div className="feedback-error report-actions">
            <AlertCircle size={17} />
            <span>Could not copy the summary from this browser session.</span>
          </div>
        ) : null}

        {run.isLoading ? (
          <ReportEmpty title="Preparing report" text="Loading the saved evidence decision." />
        ) : run.isError || !report ? (
          <ReportEmpty title="Report unavailable" text="The saved check could not be loaded from the local API." />
        ) : (
          <article className="report-page workspace-surface">
            <header className="report-hero">
              <div className="min-w-0">
                <p className="section-label">Evidence report</p>
                <h1 className="mt-3 text-4xl font-bold leading-[1.02] text-ink sm:text-5xl">
                  {report.title}
                </h1>
                <p className="mt-4 max-w-3xl text-base leading-7 text-ink-muted">
                  A shareable record of the decision, supporting evidence, safety checks, and audit trail.
                </p>
              </div>
              <div className="report-verdict">
                {report.decisionName ? <DecisionBadge decision={report.decisionName} /> : <StatusBadge tone="neutral">No outcome</StatusBadge>}
                <strong>{confidenceText(report.decision)}</strong>
                <span>{formatRunTime(report.createdAt)}</span>
              </div>
            </header>

            <section className="report-metric-row">
              <ReportMetric label="Decision" value={report.decisionName ? decisionLabel(report.decisionName) : 'No outcome'} />
              <ReportMetric label="Evidence" value={`${report.rankedSources.length} sources`} />
              <ReportMetric label="Safety" value={`${report.policyGates.length} checks`} />
              <ReportMetric label="Review" value={reviewStateText(report.decision)} />
            </section>

            <ReportSection icon={<ShieldCheck size={20} />} label="Decision" title="Decision brief">
              <div className="report-brief">
                <p>{detailText(stringField(report.decision, 'summary')) ?? 'No decision summary was saved.'}</p>
                <div className="report-fact-list">
                  <ReportFact label="Next action" value={nextActionLabel(report.decision)} />
                  <ReportFact label="Confidence" value={confidenceText(report.decision)} />
                  <ReportFact label="Created" value={formatRunTime(report.createdAt)} />
                </div>
              </div>
            </ReportSection>

            <ReportSection icon={<FileText size={20} />} label="Claims" title="Supported claims">
              {report.selectedClaims.length ? (
                <div className="report-claim-list">
                  {report.selectedClaims.map((claim, index) => (
                    <article className="report-card" key={`${stringField(claim, 'claim_id') ?? 'claim'}-${index}`}>
                      <p className="report-card-title">{stringField(claim, 'text') ?? 'Untitled claim'}</p>
                      <p className="report-card-meta">{humanize(stringField(claim, 'claim_type') ?? 'claim')}</p>
                    </article>
                  ))}
                </div>
              ) : (
                <ReportEmptyLine text="No supported claims were captured." />
              )}
            </ReportSection>

            <ReportSection icon={<GitBranch size={20} />} label="Evidence" title="Source quality">
              {report.rankedSources.length ? (
                <div className="report-source-list">
                  {report.rankedSources.map((source) => (
                    <ReportSourceCard
                      key={stringField(source, 'source_id') ?? JSON.stringify(source)}
                      source={source}
                      sourceTitle={report.citationTitleBySourceId[stringField(source, 'source_id') ?? '']}
                    />
                  ))}
                </div>
              ) : (
                <ReportEmptyLine text="No source scores were captured." />
              )}
            </ReportSection>

            <ReportSection icon={<ListChecks size={20} />} label="Safety" title="Safety checks">
              {report.policyGates.length ? (
                <div className="report-gate-grid">
                  {report.policyGates.map((gate) => (
                    <article className="report-gate" key={stringField(gate, 'gate') ?? JSON.stringify(gate)}>
                      <div>
                        <strong>{safetyCheckLabel(stringField(gate, 'gate') ?? 'safety_check')}</strong>
                        <p>{stringField(gate, 'message') ?? humanize(stringField(gate, 'effect') ?? 'recorded')}</p>
                      </div>
                      <span>{humanize(stringField(gate, 'status') ?? 'recorded')}</span>
                    </article>
                  ))}
                </div>
              ) : (
                <ReportEmptyLine text="No safety checks were captured." />
              )}
            </ReportSection>

            <ReportSection icon={<Route size={20} />} label="Audit" title="Decision trail">
              {report.auditEvents.length ? (
                <ol className="report-audit-list">
                  {report.auditEvents.slice(0, 8).map((event, index) => (
                    <li className="report-audit-item" key={`${index}-${stringField(event, 'event') ?? 'event'}`}>
                      <span>{String(index + 1).padStart(2, '0')}</span>
                      <div>
                        <strong>{auditEventTitle(event)}</strong>
                        <p>{detailText(stringField(event, 'message') ?? stringField(event, 'detail')) ?? 'Check event recorded.'}</p>
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <ReportEmptyLine text="No audit events were captured." />
              )}
            </ReportSection>
          </article>
        )}
      </div>
    </AppShell>
  )
}

function ReportSection({
  children,
  icon,
  label,
  title,
}: {
  children: ReactNode
  icon: ReactNode
  label: string
  title: string
}) {
  return (
    <section className="report-section">
      <div className="report-section-header">
        <span className="detail-section-icon">{icon}</span>
        <div className="min-w-0">
          <p className="section-label">{label}</p>
          <h2>{title}</h2>
        </div>
      </div>
      <div className="report-section-body">{children}</div>
    </section>
  )
}

function ReportMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="report-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function ReportFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="report-fact">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function ReportSourceCard({
  source,
  sourceTitle,
}: {
  source: Record<string, unknown>
  sourceTitle: string | undefined
}) {
  const tier = stringField(source, 'tier') ?? 'unscored'
  const reasons = stringArrayField(source, 'reasons')
  const scores = scoreRows(source).slice(0, 4)

  return (
    <article className="report-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="report-card-title">{sourceTitle ?? sourceDisplayName(source)}</p>
          <p className="report-card-meta">{detailText(reasons[0]) ?? 'No ranking reason was recorded.'}</p>
        </div>
        <span className="tier-token">{humanize(tier)}</span>
      </div>
      {scores.length ? (
        <div className="report-score-grid">
          {scores.map((score) => (
            <div className="report-score" key={score.dimension}>
              <span>{humanize(score.dimension)}</span>
              <strong>{score.score === null ? 'Not scored' : `${Math.round(score.score * 100)}%`}</strong>
            </div>
          ))}
        </div>
      ) : null}
    </article>
  )
}

function ReportEmpty({ text, title }: { text: string; title: string }) {
  return (
    <section className="workspace-surface p-6">
      <p className="section-label">Evidence report</p>
      <h1 className="mt-3 text-3xl font-bold text-ink">{title}</h1>
      <p className="mt-3 text-sm leading-6 text-ink-muted">{text}</p>
    </section>
  )
}

function ReportEmptyLine({ text }: { text: string }) {
  return (
    <div className="empty-detail empty-detail-compact">
      <AlertCircle size={18} />
      <span>{text}</span>
    </div>
  )
}

function reportModel(record: ApiRunRecord): ReportModel {
  const decision = decisionObjectFromRunRecord(record)
  const loopAudit = arrayOfRecords(objectField(record.result, 'audit_trace'), 'events')
  const decisionAudit = arrayOfRecords(decision, 'audit_trace')
  const citationTitleBySourceId = Object.fromEntries(
    arrayOfRecords(decision, 'source_citations').flatMap((citation) => {
      const sourceId = stringField(citation, 'source_id')
      const title = stringField(citation, 'title')
      return sourceId && title ? [[sourceId, title]] : []
    }),
  )
  return {
    auditEvents: loopAudit.length ? loopAudit : decisionAudit,
    citationTitleBySourceId,
    createdAt: record.created_at,
    decision,
    decisionName: stringField(decision, 'decision'),
    policyGates: arrayOfRecords(decision, 'policy_gates'),
    rankedSources: rankedSourcesFromDecision(decision),
    selectedClaims: uniqueClaims(arrayOfRecords(decision, 'selected_claims')),
    title: recordTitle(record),
  }
}

function reportText(report: ReportModel) {
  const lines = [
    `Source Signal Report: ${report.title}`,
    `Decision: ${report.decisionName ? decisionLabel(report.decisionName) : 'No outcome'}`,
    `Confidence: ${confidenceText(report.decision)}`,
    `Review: ${reviewStateText(report.decision)}`,
    `Created: ${formatRunTime(report.createdAt)}`,
    '',
    'Decision brief',
    detailText(stringField(report.decision, 'summary')) ?? 'No decision summary was saved.',
    '',
    'Supported claims',
    ...(
      report.selectedClaims.length
        ? report.selectedClaims.map((claim) => `- ${stringField(claim, 'text') ?? 'Untitled claim'}`)
        : ['- No supported claims were captured.']
    ),
    '',
    'Evidence',
    ...(
      report.rankedSources.length
        ? report.rankedSources.map((source) => {
            const sourceId = stringField(source, 'source_id') ?? ''
            const sourceTitle = report.citationTitleBySourceId[sourceId] ?? sourceDisplayName(source)
            return `- ${sourceTitle}: ${humanize(stringField(source, 'tier') ?? 'unscored')}`
          })
        : ['- No source scores were captured.']
    ),
    '',
    'Safety checks',
    ...(
      report.policyGates.length
        ? report.policyGates.map((gate) => `- ${safetyCheckLabel(stringField(gate, 'gate') ?? 'safety check')}: ${humanize(stringField(gate, 'status') ?? 'recorded')}`)
        : ['- No safety checks were captured.']
    ),
  ]
  return lines.join('\n')
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

function uniqueClaims(claims: Record<string, unknown>[]) {
  const seen = new Set<string>()
  return claims.filter((claim) => {
    const key = stringField(claim, 'claim_id') ?? stringField(claim, 'text') ?? JSON.stringify(claim)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
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
  const sourceId = stringField(source, 'source_id')
  if (sourceType && sourceId) return compactSourceId(sourceId)
  if (sourceType) return `${humanize(sourceType)} evidence`
  return compactSourceId(sourceId ?? 'source evidence')
}

function decisionLabel(decision: string) {
  const labels: Record<string, string> = {
    auto_handoff: 'Ready to send',
    blocked: 'Blocked',
    generate_context_request: 'Needs context',
    needs_user_review: 'Needs review',
  }
  return labels[decision] ?? humanize(decision)
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
  if (explicitTitle) return explicitTitle
  const eventName = stringField(event, 'event') ?? stringField(event, 'event_type') ?? 'audit_event'
  return labels[eventName] ?? humanize(eventName)
}

function detailText(value: string | null | undefined) {
  if (!value) return null
  const withoutScore = value
    .replace(/\bauto_handoff\b/gi, 'ready to send')
    .replace(/\bgenerate_context_request\b/gi, 'needs more context')
    .replace(/\bneeds_user_review\b/gi, 'review required')
    .replace(/\bpolicy gates\b/gi, 'safety checks')
    .replace(/\bstarter decision\b/gi, 'recommendation')
    .replace(/\bevidence bundle\b/gi, 'evidence set')
    .replace(/\bagent run\b/gi, 'guided check')
    .replace(/\branked sources\b/gi, 'scored evidence')
    .replace(/\brequired needed claims\b/gi, 'required claims')
    .replace(/\s{2,}/g, ' ')
    .trim()
  return capitalizeFirst(withoutScore.endsWith('.') ? withoutScore : `${withoutScore}.`)
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
