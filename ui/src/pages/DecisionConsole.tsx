import {
  AlertCircle,
  Boxes,
  CheckCircle2,
  ClipboardCheck,
  DatabaseZap,
  FilePlus2,
  GitBranch,
  History,
  Layers3,
  MessageSquareText,
  ShieldAlert,
  Sparkles,
} from 'lucide-react'
import type { CSSProperties, ReactNode } from 'react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  useBundleFixturesQuery,
  useCreateAgentRunMutation,
  useCreateCustomDecisionRunMutation,
  useCreateDecisionRunMutation,
  useFeedbackSnapshotQuery,
  useFixturesByKindQuery,
  useHealthQuery,
  useRankBundleMutation,
  useRankCustomBundleMutation,
  useRunsQuery,
} from '../api/queries'
import type { ApiRunRecord, ApiRunSummary, CustomDecisionRunRequest, FixtureSummary, RankedBundle } from '../api/types'
import { AppShell } from '../components/AppShell'
import { CustomScenarioBuilder } from '../components/CustomScenarioBuilder'
import { DecisionBadge } from '../components/DecisionBadge'
import { StatusBadge } from '../components/StatusBadge'

type ScenarioMode = 'fixture' | 'custom'
type RunningKind = 'rank' | 'decision' | 'agent'

type RankScoreRow = {
  dimension: string
  score: number
}

export function DecisionConsole() {
  const health = useHealthQuery()
  const fixtures = useBundleFixturesQuery()
  const ownerFixtures = useFixturesByKindQuery('owner_response')
  const retrievalFixtures = useFixturesByKindQuery('simulated_retrieval')
  const runs = useRunsQuery()
  const feedback = useFeedbackSnapshotQuery()
  const createDecisionRun = useCreateDecisionRunMutation()
  const createCustomDecisionRun = useCreateCustomDecisionRunMutation()
  const createAgentRun = useCreateAgentRunMutation()
  const rankBundle = useRankBundleMutation()
  const rankCustomBundle = useRankCustomBundleMutation()
  const [scenarioMode, setScenarioMode] = useState<ScenarioMode>('fixture')
  const [selectedFixtureId, setSelectedFixtureId] = useState('')
  const [activeRun, setActiveRun] = useState<ApiRunRecord | null>(null)
  const [activeRanking, setActiveRanking] = useState<RankedBundle | null>(null)
  const [activeRankingTitle, setActiveRankingTitle] = useState('')
  const [runningKind, setRunningKind] = useState<RunningKind | null>(null)
  const [agentAssistMode, setAgentAssistMode] = useState<AgentAssistMode>('none')
  const [selectedOwnerFixtureId, setSelectedOwnerFixtureId] = useState('')
  const [selectedRetrievalFixtureId, setSelectedRetrievalFixtureId] = useState('')
  const refreshAll = () => {
    void health.refetch()
    void fixtures.refetch()
    void ownerFixtures.refetch()
    void retrievalFixtures.refetch()
    void runs.refetch()
    void feedback.refetch()
  }

  const bundleFixtures = useMemo(() => fixtures.data?.fixtures ?? [], [fixtures.data?.fixtures])
  const runSummaries = runs.data?.runs ?? []
  const latestRun = runSummaries.at(-1)
  const learnedDefaults = Object.keys(feedback.data?.reliability_defaults ?? {}).length
  const selectedFixture = bundleFixtures.find((fixture) => fixture.id === selectedFixtureId)
  const compatibleOwnerFixtures = useMemo(
    () => compatibleAgentFixtures(ownerFixtures.data?.fixtures ?? [], selectedFixture),
    [ownerFixtures.data?.fixtures, selectedFixture],
  )
  const compatibleRetrievalFixtures = useMemo(
    () => compatibleAgentFixtures(retrievalFixtures.data?.fixtures ?? [], selectedFixture),
    [retrievalFixtures.data?.fixtures, selectedFixture],
  )
  const fixtureTitleById = useMemo(
    () => Object.fromEntries(bundleFixtures.map((fixture) => [fixture.id, fixture.title])),
    [bundleFixtures],
  )
  const runError = rankBundle.error ?? rankCustomBundle.error ?? createDecisionRun.error ?? createCustomDecisionRun.error ?? createAgentRun.error
  const isRunning = Boolean(runningKind)
  const agentAssistReady =
    agentAssistMode === 'none' ||
    (agentAssistMode === 'owner' && Boolean(selectedOwnerFixtureId)) ||
    (agentAssistMode === 'retrieval' && Boolean(selectedRetrievalFixtureId))

  useEffect(() => {
    if (bundleFixtures.length === 0) {
      setSelectedFixtureId('')
      return
    }
    if (!selectedFixtureId || !bundleFixtures.some((fixture) => fixture.id === selectedFixtureId)) {
      setSelectedFixtureId(bundleFixtures[0].id)
    }
  }, [bundleFixtures, selectedFixtureId])

  useEffect(() => {
    const hasSelectedOwner = compatibleOwnerFixtures.some(
      (fixture) => fixture.id === selectedOwnerFixtureId,
    )
    const hasSelectedRetrieval = compatibleRetrievalFixtures.some(
      (fixture) => fixture.id === selectedRetrievalFixtureId,
    )

    setSelectedOwnerFixtureId(hasSelectedOwner ? selectedOwnerFixtureId : compatibleOwnerFixtures[0]?.id ?? '')
    setSelectedRetrievalFixtureId(
      hasSelectedRetrieval ? selectedRetrievalFixtureId : compatibleRetrievalFixtures[0]?.id ?? '',
    )

    if (agentAssistMode === 'owner' && compatibleOwnerFixtures.length === 0) {
      setAgentAssistMode('none')
    }
    if (agentAssistMode === 'retrieval' && compatibleRetrievalFixtures.length === 0) {
      setAgentAssistMode('none')
    }
  }, [
    agentAssistMode,
    compatibleOwnerFixtures,
    compatibleRetrievalFixtures,
    selectedOwnerFixtureId,
    selectedRetrievalFixtureId,
  ])

  async function handleDecisionRun() {
    if (!selectedFixtureId) return
    rankBundle.reset()
    rankCustomBundle.reset()
    createDecisionRun.reset()
    createCustomDecisionRun.reset()
    createAgentRun.reset()
    setActiveRanking(null)
    setRunningKind('decision')
    try {
      const run = await createDecisionRun.mutateAsync({ fixture_id: selectedFixtureId })
      setActiveRun(run)
    } catch {
      // The mutation error is rendered below the controls.
    } finally {
      setRunningKind(null)
    }
  }

  async function handleCustomDecisionRun(request: CustomDecisionRunRequest) {
    rankBundle.reset()
    rankCustomBundle.reset()
    createDecisionRun.reset()
    createCustomDecisionRun.reset()
    createAgentRun.reset()
    setActiveRanking(null)
    setRunningKind('decision')
    try {
      const run = await createCustomDecisionRun.mutateAsync(request)
      setActiveRun(run)
    } catch {
      // The mutation error is rendered below the controls.
    } finally {
      setRunningKind(null)
    }
  }

  async function handleAgentRun() {
    if (!selectedFixtureId) return
    rankBundle.reset()
    rankCustomBundle.reset()
    createDecisionRun.reset()
    createCustomDecisionRun.reset()
    createAgentRun.reset()
    setActiveRanking(null)
    setRunningKind('agent')
    try {
      const run = await createAgentRun.mutateAsync({
        fixture_id: selectedFixtureId,
        max_iterations: 3,
        owner_response_fixture_id:
          agentAssistMode === 'owner' ? selectedOwnerFixtureId : null,
        simulated_retrieval_fixture_id:
          agentAssistMode === 'retrieval' ? selectedRetrievalFixtureId : null,
      })
      setActiveRun(run)
    } catch {
      // The mutation error is rendered below the controls.
    } finally {
      setRunningKind(null)
    }
  }

  async function handleRankOnly() {
    if (!selectedFixtureId) return
    rankBundle.reset()
    rankCustomBundle.reset()
    createDecisionRun.reset()
    createCustomDecisionRun.reset()
    createAgentRun.reset()
    setActiveRun(null)
    setRunningKind('rank')
    try {
      const ranked = await rankBundle.mutateAsync({ fixture_id: selectedFixtureId })
      setActiveRanking(ranked)
      setActiveRankingTitle(selectedFixture?.title ?? sourceTitleFromRankedBundle(ranked))
    } catch {
      // The mutation error is rendered below the controls.
    } finally {
      setRunningKind(null)
    }
  }

  async function handleCustomRankOnly(request: CustomDecisionRunRequest) {
    rankBundle.reset()
    rankCustomBundle.reset()
    createDecisionRun.reset()
    createCustomDecisionRun.reset()
    createAgentRun.reset()
    setActiveRun(null)
    setRunningKind('rank')
    try {
      const ranked = await rankCustomBundle.mutateAsync(request)
      setActiveRanking(ranked)
      setActiveRankingTitle(request.bundle.title)
    } catch {
      // The mutation error is rendered below the controls.
    } finally {
      setRunningKind(null)
    }
  }

  return (
    <AppShell apiConnected={health.isSuccess} onRefresh={refreshAll}>
      <div className="space-y-5">
        <section className="workspace-surface overflow-hidden">
          <div className="grid lg:grid-cols-[minmax(0,1.15fr)_minmax(340px,0.85fr)]">
            <div className="p-5 sm:p-7">
              <p className="section-label">Decision desk</p>
              <h1 className="mt-3 max-w-2xl text-4xl font-bold leading-[1.02] text-ink sm:text-5xl">
                Choose evidence, read the signal, keep the handoff honest.
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-ink-muted">
                Pick an evidence scenario and compare the outcome against review, ownership, and learning state.
              </p>

              <div className="source-mode-switch mt-7" role="group" aria-label="Scenario source">
                <SourceModeButton
                  active={scenarioMode === 'fixture'}
                  detail="Use the saved demo library."
                  icon={<Boxes size={18} />}
                  label="Sample scenarios"
                  onClick={() => setScenarioMode('fixture')}
                />
                <SourceModeButton
                  active={scenarioMode === 'custom'}
                  detail="Enter context and sources manually."
                  icon={<FilePlus2 size={18} />}
                  label="Custom evidence"
                  onClick={() => setScenarioMode('custom')}
                />
              </div>

              {scenarioMode === 'fixture' ? (
                <>
                  <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto_auto_auto]">
                    <label className="min-w-0">
                      <span className="field-label">Evidence scenario</span>
                      <select
                        className="field mt-2"
                        value={selectedFixtureId}
                        onChange={(event) => setSelectedFixtureId(event.target.value)}
                        disabled={fixtures.isLoading || isRunning}
                      >
                        {bundleFixtures.length === 0 ? (
                          <option value="">No scenarios loaded</option>
                        ) : (
                          bundleFixtures.map((fixture) => (
                            <option key={fixture.id} value={fixture.id}>
                              {fixture.title}
                            </option>
                          ))
                        )}
                      </select>
                    </label>
                    <button
                      className="button-secondary self-end"
                      type="button"
                      onClick={() => void handleRankOnly()}
                      disabled={!selectedFixtureId || isRunning}
                    >
                      {runningKind === 'rank' ? 'Ranking...' : 'Rank only'}
                    </button>
                    <button
                      className="button-primary self-end"
                      type="button"
                      onClick={() => void handleDecisionRun()}
                      disabled={!selectedFixtureId || isRunning}
                    >
                      {runningKind === 'decision' ? 'Checking...' : 'Check evidence'}
                    </button>
                    <button
                      className="button-secondary self-end"
                      type="button"
                      onClick={() => void handleAgentRun()}
                      disabled={!selectedFixtureId || isRunning || !agentAssistReady}
                    >
                      {runningKind === 'agent' ? 'Checking...' : 'Guided check'}
                    </button>
                  </div>

                  <AgentAssistControls
                    isLoading={ownerFixtures.isLoading || retrievalFixtures.isLoading}
                    mode={agentAssistMode}
                    ownerFixtures={compatibleOwnerFixtures}
                    retrievalFixtures={compatibleRetrievalFixtures}
                    selectedOwnerFixtureId={selectedOwnerFixtureId}
                    selectedRetrievalFixtureId={selectedRetrievalFixtureId}
                    setMode={setAgentAssistMode}
                    setSelectedOwnerFixtureId={setSelectedOwnerFixtureId}
                    setSelectedRetrievalFixtureId={setSelectedRetrievalFixtureId}
                  />
                </>
              ) : (
                <CustomScenarioBuilder
                  disabled={isRunning}
                  isRanking={runningKind === 'rank'}
                  isRunning={runningKind === 'decision'}
                  onRank={(request) => void handleCustomRankOnly(request)}
                  onRun={(request) => void handleCustomDecisionRun(request)}
                />
              )}

              {scenarioMode === 'fixture' && selectedFixture ? (
                <p className="mt-3 text-sm leading-6 text-ink-muted">
                  Selected scenario: <span className="font-semibold text-ink">{selectedFixture.title}</span>
                </p>
              ) : null}

              {runError ? (
                <div className="mt-4 flex items-start gap-3 rounded-lg border border-rose-300 bg-rose-100/70 p-3 text-sm leading-6 text-rose-900">
                  <AlertCircle className="mt-0.5 shrink-0" size={17} />
                  <span>{errorText(runError)}</span>
                </div>
              ) : null}
            </div>

            <div className="border-t border-border-soft/80 bg-[var(--surface-panel)] p-5 sm:p-6 lg:border-l lg:border-t-0">
              <OutcomeReceipt
                activeRun={activeRun}
                activeRanking={activeRanking}
                activeRankingTitle={activeRankingTitle}
                isRunning={isRunning}
                latestRun={latestRun}
                runningKind={runningKind}
              />

              <div className="mt-4 grid grid-cols-3 overflow-hidden rounded-lg border border-border-soft bg-[var(--surface-panel)]">
                <MetricCell label="Scenarios" value={bundleFixtures.length} icon={<Boxes size={17} />} />
                <MetricCell label="Checks" value={runSummaries.length} icon={<DatabaseZap size={17} />} />
                <MetricCell label="Signals" value={learnedDefaults} icon={<Sparkles size={17} />} />
              </div>
            </div>
          </div>
        </section>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <section className="workspace-surface min-w-0 overflow-hidden">
            <div className="flex flex-wrap items-end justify-between gap-3 border-b border-border-soft/80 p-5 sm:p-6">
              <div>
                <p className="section-label">Scenario library</p>
                <h2 className="mt-2 text-2xl font-bold leading-tight">Evidence scenarios</h2>
              </div>
              <StatusBadge tone="neutral">{fixtures.isLoading ? 'Loading' : `${bundleFixtures.length} scenarios`}</StatusBadge>
            </div>

            <div className="divide-y divide-border-soft/80">
              {bundleFixtures.length === 0 ? (
                <EmptyLine text={fixtures.isError ? 'Could not load scenarios.' : 'No evidence scenarios found.'} />
              ) : (
                bundleFixtures.map((fixture) => (
                  <article
                    key={fixture.id}
                    className="grid gap-3 p-4 transition-colors duration-150 hover:bg-[var(--surface-hover)] sm:p-5 md:grid-cols-[minmax(0,1fr)_auto] md:items-center"
                  >
                    <div className="flex min-w-0 gap-3">
                      <span className="mt-1 h-10 w-1 rounded-full bg-primary/72" />
                      <div className="min-w-0">
                        <h3 className="break-words text-base font-bold leading-snug text-ink">{fixture.title}</h3>
                        <p className="mt-1 text-sm leading-5 text-ink-muted">{fixture.expected_decision ? 'Expected outcome available' : 'Ready for a check'}</p>
                      </div>
                    </div>
                    {fixture.expected_decision ? (
                      <span className="md:justify-self-end">
                        <DecisionBadge decision={fixture.expected_decision} />
                      </span>
                    ) : null}
                  </article>
                ))
              )}
            </div>
          </section>

          <aside className="workspace-surface min-w-0 overflow-hidden">
            <RailSection icon={<Layers3 size={20} />} label="Evidence path" title="Signal flow">
              <div className="space-y-3">
                <PathStep title="Sources" text="Owner, freshness, directness, corroboration, and confidence tier." />
                <PathStep title="Claims" text="Citations, weak points, conflicts, and missing context." />
                <PathStep title="Decision" text="Outcome, review state, blocked state, and handoff preview." />
              </div>
            </RailSection>

            <RailSection icon={<History size={20} />} label="Check history" title="Recent checks">
              <RunHistoryList fixtureTitles={fixtureTitleById} runs={runSummaries} />
            </RailSection>

            <RailSection icon={<MessageSquareText size={20} />} label="Review portal" title="Pending review">
              <PendingReviewList fixtureTitles={fixtureTitleById} runs={runSummaries} />
            </RailSection>

            <RailSection icon={<Sparkles size={20} />} label="Feedback snapshot" title="Reliability learning">
              {feedback.data?.updates.length ? (
                <div className="space-y-3">
                  {feedback.data.updates.slice(0, 4).map((update) => (
                    <div key={update.key} className="rounded-lg bg-[var(--surface-panel)] p-3 ring-1 ring-border-soft">
                      <div className="flex items-center justify-between gap-3">
                        <p className="break-words text-sm font-bold">{update.key}</p>
                        <StatusBadge tone={update.delta >= 0 ? 'mint' : 'rose'}>
                          {update.delta >= 0 ? '+' : ''}
                          {update.delta.toFixed(2)}
                        </StatusBadge>
                      </div>
                      <p className="mt-2 text-xs leading-5 text-ink-muted">{update.reasons.join(', ') || 'No movement'}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyLine text="No learned feedback yet." compact />
              )}
            </RailSection>
          </aside>
        </div>
      </div>
    </AppShell>
  )
}

type AgentAssistMode = 'none' | 'owner' | 'retrieval'

function AgentAssistControls({
  isLoading,
  mode,
  ownerFixtures,
  retrievalFixtures,
  selectedOwnerFixtureId,
  selectedRetrievalFixtureId,
  setMode,
  setSelectedOwnerFixtureId,
  setSelectedRetrievalFixtureId,
}: {
  isLoading: boolean
  mode: AgentAssistMode
  ownerFixtures: FixtureSummary[]
  retrievalFixtures: FixtureSummary[]
  selectedOwnerFixtureId: string
  selectedRetrievalFixtureId: string
  setMode: (mode: AgentAssistMode) => void
  setSelectedOwnerFixtureId: (fixtureId: string) => void
  setSelectedRetrievalFixtureId: (fixtureId: string) => void
}) {
  const ownerDisabled = ownerFixtures.length === 0
  const retrievalDisabled = retrievalFixtures.length === 0

  return (
    <div className="agent-assist-panel mt-4">
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <GitBranch size={17} className="text-primary" />
            <p className="section-label">Agent assist</p>
          </div>
          <p className="mt-2 text-sm leading-6 text-ink-muted">
            Attach one simulated improvement to the guided check.
          </p>
        </div>
        <StatusBadge tone="neutral">
          {isLoading ? 'Loading' : `${ownerFixtures.length + retrievalFixtures.length} available`}
        </StatusBadge>
      </div>

      <div className="agent-mode-grid mt-4" role="group" aria-label="Agent assist mode">
        <AgentModeButton
          active={mode === 'none'}
          detail="Run the bounded check without extra evidence."
          label="No assist"
          onClick={() => setMode('none')}
        />
        <AgentModeButton
          active={mode === 'owner'}
          detail={
            ownerDisabled
              ? 'No owner response fits this scenario.'
              : 'Apply a saved owner validation response.'
          }
          disabled={ownerDisabled}
          label="Owner validation"
          onClick={() => setMode('owner')}
        />
        <AgentModeButton
          active={mode === 'retrieval'}
          detail={
            retrievalDisabled
              ? 'No retrieval fixture fits this scenario.'
              : 'Add retrieved evidence or test a no-hit search.'
          }
          disabled={retrievalDisabled}
          label="Retrieval"
          onClick={() => setMode('retrieval')}
        />
      </div>

      {mode === 'owner' ? (
        <label className="mt-4 block">
          <span className="field-label">Owner response</span>
          <select
            className="field mt-2"
            value={selectedOwnerFixtureId}
            onChange={(event) => setSelectedOwnerFixtureId(event.target.value)}
          >
            {ownerFixtures.map((fixture) => (
              <option key={fixture.id} value={fixture.id}>
                {agentFixtureLabel(fixture)}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {mode === 'retrieval' ? (
        <label className="mt-4 block">
          <span className="field-label">Retrieval result</span>
          <select
            className="field mt-2"
            value={selectedRetrievalFixtureId}
            onChange={(event) => setSelectedRetrievalFixtureId(event.target.value)}
          >
            {retrievalFixtures.map((fixture) => (
              <option key={fixture.id} value={fixture.id}>
                {agentFixtureLabel(fixture)}
              </option>
            ))}
          </select>
        </label>
      ) : null}
    </div>
  )
}

function SourceModeButton({
  active,
  detail,
  icon,
  label,
  onClick,
}: {
  active: boolean
  detail: string
  icon: ReactNode
  label: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      className={active ? 'source-mode-button source-mode-button-active' : 'source-mode-button'}
      aria-pressed={active}
      onClick={onClick}
    >
      <span className="source-mode-icon">{icon}</span>
      <span className="min-w-0 text-left">
        <span className="block text-sm font-extrabold text-ink">{label}</span>
        <span className="mt-1 block text-xs font-semibold leading-5 text-ink-muted">{detail}</span>
      </span>
    </button>
  )
}

function AgentModeButton({
  active,
  detail,
  disabled = false,
  label,
  onClick,
}: {
  active: boolean
  detail: string
  disabled?: boolean
  label: string
  onClick: () => void
}) {
  return (
    <button
      aria-pressed={active}
      className={active ? 'agent-mode-button agent-mode-button-active' : 'agent-mode-button'}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      <span>{label}</span>
      <small>{detail}</small>
    </button>
  )
}

type OutcomeTone = 'auto' | 'context' | 'review' | 'blocked' | 'neutral' | 'running'

type OutcomeReceiptState = {
  decision: string | null
  eyebrow: string
  label: string
  summary: string
  tone: OutcomeTone
  runId: string | null
  runKind: string | null
  confidence: string
  sourceCount: string
  reviewState: string
  nextAction: string
}

const outcomeMeta: Record<
  string,
  {
    label: string
    eyebrow: string
    tone: OutcomeTone
  }
> = {
  auto_handoff: {
    label: 'Ready to send',
    eyebrow: 'Ready for handoff',
    tone: 'auto',
  },
  generate_context_request: {
    label: 'Needs context',
    eyebrow: 'Needs more context',
    tone: 'context',
  },
  needs_user_review: {
    label: 'Needs review',
    eyebrow: 'Human check required',
    tone: 'review',
  },
  blocked: {
    label: 'Blocked',
    eyebrow: 'Automation stopped',
    tone: 'blocked',
  },
}

const outcomeToneVars: Record<OutcomeTone, CSSProperties> = {
  auto: {
    '--outcome-accent': 'var(--status-auto)',
    '--outcome-soft': 'var(--status-auto-soft)',
    '--outcome-line': 'var(--status-auto-line)',
  } as CSSProperties,
  context: {
    '--outcome-accent': 'var(--status-context)',
    '--outcome-soft': 'var(--status-context-soft)',
    '--outcome-line': 'var(--status-context-line)',
  } as CSSProperties,
  review: {
    '--outcome-accent': 'var(--status-review)',
    '--outcome-soft': 'var(--status-review-soft)',
    '--outcome-line': 'var(--status-review-line)',
  } as CSSProperties,
  blocked: {
    '--outcome-accent': 'var(--status-blocked)',
    '--outcome-soft': 'var(--status-blocked-soft)',
    '--outcome-line': 'var(--status-blocked-line)',
  } as CSSProperties,
  neutral: {
    '--outcome-accent': 'var(--accent)',
    '--outcome-soft': 'var(--accent-soft)',
    '--outcome-line': 'var(--accent-ring)',
  } as CSSProperties,
  running: {
    '--outcome-accent': 'var(--accent)',
    '--outcome-soft': 'var(--accent-soft)',
    '--outcome-line': 'var(--accent-ring)',
  } as CSSProperties,
}

function OutcomeReceipt({
  activeRun,
  activeRanking,
  activeRankingTitle,
  isRunning,
  latestRun,
  runningKind,
}: {
  activeRun: ApiRunRecord | null
  activeRanking: RankedBundle | null
  activeRankingTitle: string
  isRunning: boolean
  latestRun: ApiRunSummary | undefined
  runningKind: RunningKind | null
}) {
  if (activeRanking && !isRunning) {
    return <RankingReceipt ranked={activeRanking} title={activeRankingTitle || sourceTitleFromRankedBundle(activeRanking)} />
  }

  const receipt = outcomeReceiptState({ activeRun, isRunning, latestRun, runningKind })

  return (
    <div className="outcome-receipt p-4 sm:p-5" style={outcomeToneVars[receipt.tone]}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="outcome-kicker">{receipt.eyebrow}</span>
            {receipt.runKind ? <span className="outcome-chip">{receipt.runKind}</span> : null}
          </div>
          <h2 className="mt-3 text-3xl font-bold leading-none text-ink sm:text-4xl">{receipt.label}</h2>
          <p className="mt-3 max-w-xl text-sm leading-6 text-ink-muted">{receipt.summary}</p>
        </div>
        <span className="outcome-medallion" aria-hidden="true">
          {outcomeIcon(receipt.tone)}
        </span>
      </div>

      <div className="mt-5 grid gap-2 sm:grid-cols-3">
        <OutcomeFact label="Confidence" value={receipt.confidence} />
        <OutcomeFact label="Sources" value={receipt.sourceCount} />
        <OutcomeFact label="Review" value={receipt.reviewState} />
      </div>

      <div className="outcome-audit-strip mt-4">
        <OutcomeAuditStep label="Evidence" active={receipt.sourceCount !== 'Pending'} />
        <OutcomeAuditStep label="Safety checks" active={Boolean(receipt.decision)} />
        <OutcomeAuditStep label={receipt.nextAction} active={Boolean(receipt.runId)} />
      </div>

      {receipt.runId ? (
        <div className="mt-4 flex min-w-0 flex-wrap items-center gap-2 border-t border-border-soft/80 pt-4">
          {receipt.decision ? <DecisionBadge decision={receipt.decision} /> : null}
          <StatusBadge tone="neutral">{receipt.runKind ?? 'Quick check'}</StatusBadge>
          <Link className="outcome-detail-link focus-ring" to={`/runs/${receipt.runId}`}>
            View details
          </Link>
        </div>
      ) : null}
    </div>
  )
}

function RankingReceipt({ ranked, title }: { ranked: RankedBundle; title: string }) {
  const counts = tierCounts(ranked)
  const topSources = [...ranked.ranked_sources]
    .sort((left, right) => sourceStrengthScore(right) - sourceStrengthScore(left))
    .slice(0, 3)
  const sourceTitles = recordField(ranked.metadata, 'source_titles') ?? {}
  const sourceSummaries = recordField(ranked.metadata, 'source_summaries') ?? {}

  return (
    <div className="ranking-receipt p-4 sm:p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="outcome-kicker">Evidence ranking</span>
            <span className="outcome-chip">Rank only</span>
          </div>
          <h2 className="mt-3 text-3xl font-bold leading-none text-ink sm:text-4xl">{title}</h2>
          <p className="mt-3 max-w-xl text-sm leading-6 text-ink-muted">
            Sources are scored and tiered without creating a decision run or applying handoff policy.
          </p>
        </div>
        <span className="outcome-medallion" aria-hidden="true">
          <GitBranch size={24} strokeWidth={2.1} />
        </span>
      </div>

      <div className="mt-5 grid gap-2 sm:grid-cols-3">
        <OutcomeFact label="Strong" value={String(counts.strong)} />
        <OutcomeFact label="Usable" value={String(counts.medium)} />
        <OutcomeFact label="Weak" value={String(counts.weak)} />
      </div>

      <div className="ranking-source-list mt-4">
        {topSources.length ? (
          topSources.map((source, index) => (
            <article className="ranking-source-card" key={source.source_id}>
              <div className="ranking-source-rank">{String(index + 1).padStart(2, '0')}</div>
              <div className="min-w-0">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <h3 className="ranking-source-title">
                    {stringRecordValue(sourceTitles, source.source_id) ?? compactSourceId(source.source_id)}
                  </h3>
                  <span className="tier-token">{humanize(source.tier)}</span>
                </div>
                <p className="mt-2 text-sm leading-6 text-ink-muted">
                  {detailText(source.reasons[0]) ?? stringRecordValue(sourceSummaries, source.source_id) ?? 'No ranking reason was recorded.'}
                </p>
                <div className="ranking-score-row mt-3">
                  {scoreRows(source).slice(0, 4).map((score) => (
                    <span className="ranking-score-pill" key={score.dimension}>
                      {humanize(score.dimension)}
                      <strong>{Math.round(score.score * 100)}%</strong>
                    </span>
                  ))}
                </div>
              </div>
            </article>
          ))
        ) : (
          <EmptyLine text="No ranked sources were returned." compact />
        )}
      </div>
    </div>
  )
}

function OutcomeFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="outcome-fact">
      <p>{label}</p>
      <strong>{value}</strong>
    </div>
  )
}

function OutcomeAuditStep({ active, label }: { active: boolean; label: string }) {
  return (
    <span className={active ? 'outcome-audit-step outcome-audit-step-active' : 'outcome-audit-step'}>
      {label}
    </span>
  )
}

function RunHistoryList({
  fixtureTitles,
  runs,
}: {
  fixtureTitles: Record<string, string>
  runs: ApiRunSummary[]
}) {
  if (runs.length === 0) {
    return <EmptyLine text="No checks saved yet." compact />
  }

  const recentRuns = runs.slice(-4).reverse()

  return (
    <div className="run-history-list">
      {recentRuns.map((run) => (
        <RunHistoryItem
          fixtureTitle={runTitle(run, fixtureTitles)}
          key={run.run_id}
          run={run}
        />
      ))}
    </div>
  )
}

function RunHistoryItem({
  fixtureTitle,
  run,
}: {
  fixtureTitle: string
  run: ApiRunSummary
}) {
  const decision = run.final_decision ?? run.decision

  return (
    <Link className="run-history-item focus-ring" to={`/runs/${run.run_id}`}>
      <span className="run-history-dot" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="run-history-title">{fixtureTitle}</h3>
            <p className="run-history-meta">
              <span>{formatRunTime(run.created_at)}</span>
            </p>
          </div>
          <span className={run.kind === 'agent' ? 'run-kind-pill run-kind-pill-agent' : 'run-kind-pill'}>
            {run.kind === 'agent' ? 'Guided' : 'Quick'}
          </span>
        </div>
        <div className="mt-3 flex min-w-0 flex-wrap items-center gap-2">
          {decision ? <DecisionBadge decision={decision} /> : <span className="run-history-empty-decision">No outcome</span>}
        </div>
      </div>
    </Link>
  )
}

function PendingReviewList({
  fixtureTitles,
  runs,
}: {
  fixtureTitles: Record<string, string>
  runs: ApiRunSummary[]
}) {
  const reviewRuns = runs
    .filter((run) => (run.final_decision ?? run.decision) === 'needs_user_review')
    .slice(-3)
    .reverse()

  if (reviewRuns.length === 0) {
    return <p className="text-sm leading-6 text-ink-muted">No saved checks are waiting for reviewer input.</p>
  }

  return (
    <div className="grid gap-2">
      {reviewRuns.map((run) => (
        <Link className="run-history-item focus-ring" key={run.run_id} to={`/review/${run.run_id}`}>
          <span className="run-history-dot" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <div className="flex min-w-0 items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="run-history-title">{runTitle(run, fixtureTitles)}</h3>
                <p className="run-history-meta">
                  <span>{formatRunTime(run.created_at)}</span>
                </p>
              </div>
              <span className={run.kind === 'agent' ? 'run-kind-pill run-kind-pill-agent' : 'run-kind-pill'}>
                {run.kind === 'agent' ? 'Guided' : 'Quick'}
              </span>
            </div>
            <div className="mt-3 flex min-w-0 flex-wrap items-center gap-2">
              <DecisionBadge decision="needs_user_review" />
            </div>
          </div>
        </Link>
      ))}
    </div>
  )
}

function compatibleAgentFixtures(
  fixtures: FixtureSummary[],
  selectedFixture: FixtureSummary | undefined,
) {
  if (!selectedFixture?.bundle_id) return []
  return fixtures.filter((fixture) => fixture.bundle_id === selectedFixture.bundle_id)
}

function runTitle(run: ApiRunSummary, fixtureTitles: Record<string, string>) {
  return run.title ?? fixtureTitles[run.fixture_id] ?? compactFixtureId(run.fixture_id)
}

function agentFixtureLabel(fixture: FixtureSummary) {
  if (fixture.kind === 'owner_response') {
    return fixture.title.replace(': accepted', ' validates context')
  }
  if (fixture.kind === 'simulated_retrieval') {
    if (fixture.expected_decision === 'blocked') return 'No retrieval hit'
    if (fixture.expected_decision === 'auto_handoff') return 'Retrieve validated evidence'
    return `Retrieval -> ${humanize(fixture.expected_decision ?? 'updated outcome')}`
  }
  return fixture.title
}

function outcomeReceiptState({
  activeRun,
  isRunning,
  latestRun,
  runningKind,
}: {
  activeRun: ApiRunRecord | null
  isRunning: boolean
  latestRun: ApiRunSummary | undefined
  runningKind: RunningKind | null
}): OutcomeReceiptState {
  if (isRunning) {
    const label =
      runningKind === 'agent'
        ? 'Running guided check'
        : runningKind === 'rank'
          ? 'Ranking evidence'
          : 'Checking evidence'
    return {
      decision: null,
      eyebrow: 'Scoring in progress',
      label,
      summary:
        runningKind === 'rank'
          ? 'Scoring each source by freshness, directness, ownership, and reliability without creating a decision run.'
          : 'Evaluating source quality, safety checks, and the next safe action.',
      tone: 'running',
      runId: null,
      runKind: runningKind === 'agent' ? 'Guided check' : runningKind === 'rank' ? 'Rank only' : 'Quick check',
      confidence: 'Pending',
      sourceCount: 'Pending',
      reviewState: 'Pending',
      nextAction: runningKind === 'rank' ? 'Show ranking' : 'Save check',
    }
  }

  if (activeRun) {
    const decisionObject = decisionObjectFromRunRecord(activeRun)
    const decision = decisionFromDecisionObject(decisionObject) ?? decisionFromRunRecord(activeRun)
    const meta = decision ? outcomeMeta[decision] : null
    const confidence = confidenceText(decisionObject)
    const sourceCount = sourceCountText(decisionObject)
    const reviewState = reviewStateText(decisionObject)
    const nextAction = nextActionText(decisionObject)

    return {
      decision,
      eyebrow: meta?.eyebrow ?? 'Check saved',
      label: meta?.label ?? humanize(decision ?? 'Check saved'),
      summary: summaryFromDecisionObject(decisionObject) ?? 'The check was saved with its evidence and safety trail.',
      tone: meta?.tone ?? 'neutral',
      runId: activeRun.run_id,
      runKind: activeRun.kind === 'agent' ? 'Guided check' : 'Quick check',
      confidence,
      sourceCount,
      reviewState,
      nextAction,
    }
  }

  if (latestRun) {
    const decision = latestRun.final_decision ?? latestRun.decision
    const meta = decision ? outcomeMeta[decision] : null
    return {
      decision,
      eyebrow: meta?.eyebrow ?? 'Latest check',
      label: meta?.label ?? humanize(decision ?? 'Saved check'),
      summary: 'A recent check is available in history. Open details to inspect the evidence and safety checks.',
      tone: meta?.tone ?? 'neutral',
      runId: latestRun.run_id,
      runKind: latestRun.kind === 'agent' ? 'Guided check' : 'Quick check',
      confidence: 'Saved',
      sourceCount: 'History',
      reviewState: decision === 'needs_user_review' ? 'Prompt open' : 'Recorded',
      nextAction: 'Open details',
    }
  }

  return {
    decision: null,
    eyebrow: 'Ready',
    label: 'No check selected',
    summary: 'Choose a scenario to generate a decision receipt with confidence, evidence coverage, and review state.',
    tone: 'neutral',
    runId: null,
    runKind: null,
    confidence: 'Waiting',
    sourceCount: '0',
    reviewState: 'None',
    nextAction: 'Start',
  }
}

function outcomeIcon(tone: OutcomeTone) {
  if (tone === 'blocked') return <ShieldAlert size={24} strokeWidth={2.1} />
  if (tone === 'review') return <ClipboardCheck size={24} strokeWidth={2.1} />
  if (tone === 'running') return <Sparkles size={24} strokeWidth={2.1} />
  if (tone === 'context') return <MessageSquareText size={24} strokeWidth={2.1} />
  return <CheckCircle2 size={24} strokeWidth={2.1} />
}

function tierCounts(ranked: RankedBundle) {
  return ranked.ranked_sources.reduce(
    (counts, source) => ({
      ...counts,
      [source.tier]: counts[source.tier] + 1,
    }),
    { strong: 0, medium: 0, weak: 0 },
  )
}

function sourceStrengthScore(source: RankedBundle['ranked_sources'][number]) {
  const tierWeight = source.tier === 'strong' ? 3 : source.tier === 'medium' ? 2 : 1
  const scores = scoreRows(source)
  const average = scores.length
    ? scores.reduce((total, score) => total + score.score, 0) / scores.length
    : 0
  return tierWeight + average
}

function scoreRows(source: RankedBundle['ranked_sources'][number]): RankScoreRow[] {
  return Object.entries(source.scores).flatMap(([dimension, value]) => {
    const score = typeof value.score === 'number' ? value.score : null
    return score === null ? [] : [{ dimension, score }]
  })
}

function sourceTitleFromRankedBundle(ranked: RankedBundle) {
  return stringField(ranked.metadata, 'bundle_title') ?? compactFixtureId(ranked.id)
}

function recordField(value: Record<string, unknown>, key: string) {
  const field = value[key]
  return field && typeof field === 'object' && !Array.isArray(field)
    ? (field as Record<string, unknown>)
    : null
}

function stringRecordValue(record: Record<string, unknown>, key: string) {
  const value = record[key]
  return typeof value === 'string' ? value : null
}

function decisionFromRunRecord(run: ApiRunRecord) {
  const decisionObject = decisionObjectFromRunRecord(run)
  return decisionFromDecisionObject(decisionObject)
}

function decisionObjectFromRunRecord(run: ApiRunRecord) {
  const finalDecision = objectField(run.result, 'final_decision')
  const initialDecision = objectField(run.result, 'initial_decision')
  if (finalDecision) return finalDecision
  if (stringField(run.result, 'decision')) return run.result
  return initialDecision
}

function decisionFromDecisionObject(decision: Record<string, unknown> | null) {
  return stringField(decision, 'decision')
}

function summaryFromDecisionObject(decision: Record<string, unknown> | null) {
  return stringField(decision, 'summary')
}

function confidenceText(decision: Record<string, unknown> | null) {
  const confidence = objectField(decision ?? {}, 'confidence')
  const label = stringField(confidence, 'label')
  const score = numberField(confidence, 'score')
  if (label && typeof score === 'number') return `${humanize(label)} · ${Math.round(score * 100)}%`
  if (label) return humanize(label)
  return 'Not scored'
}

function sourceCountText(decision: Record<string, unknown> | null) {
  const selectedSources = arrayField(decision ?? {}, 'selected_sources')
  if (!selectedSources) return '0'
  return String(selectedSources.length)
}

function reviewStateText(decision: Record<string, unknown> | null) {
  if (objectField(decision ?? {}, 'approval_prompt')) return 'Prompt open'
  if (objectField(decision ?? {}, 'context_request')) return 'Needs context'
  if (objectField(decision ?? {}, 'blocked_output')) return 'Blocked'
  return 'Clear'
}

function nextActionText(decision: Record<string, unknown> | null) {
  const nextAction = objectField(decision ?? {}, 'next_action')
  return stringField(nextAction, 'label') ?? 'Next action'
}

function objectField(value: Record<string, unknown>, key: string) {
  const field = value[key]
  return field && typeof field === 'object' && !Array.isArray(field)
    ? (field as Record<string, unknown>)
    : null
}

function arrayField(value: Record<string, unknown>, key: string) {
  const field = value[key]
  return Array.isArray(field) ? field : null
}

function stringField(value: Record<string, unknown> | null, key: string) {
  const field = value?.[key]
  return typeof field === 'string' ? field : null
}

function numberField(value: Record<string, unknown> | null, key: string) {
  const field = value?.[key]
  return typeof field === 'number' ? field : null
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

function detailText(value: string | null | undefined) {
  if (!value) return null
  const withoutScore = value
    .replace(/\bownership_signal\b/gi, 'ownership')
    .replace(/\bhistorical_reliability\b/gi, 'reliability history')
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

function errorText(error: unknown) {
  return error instanceof Error ? error.message : 'Check failed.'
}

function MetricCell({ label, value, icon }: { label: string; value: string | number; icon: ReactNode }) {
  return (
    <section className="min-w-0 border-r border-border-soft/80 p-4 last:border-r-0">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold text-ink-muted">{label}</p>
        <span className="text-primary">{icon}</span>
      </div>
      <p className="mt-3 text-3xl font-bold leading-none text-ink">{value}</p>
    </section>
  )
}

function RailSection({
  icon,
  label,
  title,
  children,
}: {
  icon: ReactNode
  label: string
  title: string
  children: ReactNode
}) {
  return (
    <section className="border-b border-border-soft/80 p-5 last:border-b-0">
      <div className="flex items-start gap-3">
        <span className="surface-icon size-10">{icon}</span>
        <div className="min-w-0 flex-1">
          <p className="section-label">{label}</p>
          <h2 className="mt-1 text-xl font-bold leading-tight">{title}</h2>
        </div>
      </div>
      <div className="mt-4">{children}</div>
    </section>
  )
}

function PathStep({ title, text }: { title: string; text: string }) {
  return (
    <div className="grid grid-cols-[2.25rem_minmax(0,1fr)] gap-3 rounded-lg bg-[var(--surface-panel)] p-3 ring-1 ring-border-soft">
      <span className="surface-icon size-8">
        <CheckCircle2 size={16} />
      </span>
      <div>
        <p className="text-sm font-bold text-ink">{title}</p>
        <p className="mt-1 text-sm leading-6 text-ink-muted">{text}</p>
      </div>
    </div>
  )
}

function EmptyLine({ text, compact = false }: { text: string; compact?: boolean }) {
  return (
    <div
      className={`flex items-center gap-3 border border-dashed border-border-soft bg-[var(--surface-panel)] text-sm text-ink-muted ${
        compact ? 'min-h-16 rounded-lg p-3' : 'min-h-24 p-5'
      }`}
    >
      <AlertCircle size={18} />
      {text}
    </div>
  )
}
