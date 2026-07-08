import { CheckCircle2, FilePlus2, Plus, Trash2 } from 'lucide-react'
import type { FormEvent } from 'react'
import { useMemo, useState } from 'react'

import type {
  ClaimType,
  CustomDecisionRunRequest,
  CustomSource,
  DirectnessRelation,
  NeededClaimType,
  RiskTolerance,
  SensitivityLabel,
  SourceSystem,
  SourceType,
} from '../api/types'
import { StatusBadge } from './StatusBadge'

type DraftSource = {
  title: string
  summary: string
  claim: string
  type: SourceType
  sourceSystem: SourceSystem
  directness: DirectnessRelation
  createdAt: string
  ownerName: string
  sensitivity: SensitivityLabel
  similarityReason: string
}

type BuilderState = {
  title: string
  clientName: string
  emailGoal: string
  primaryClaim: string
  secondaryClaim: string
  riskTolerance: RiskTolerance
  asOf: string
  sources: DraftSource[]
}

const sourceTypeOptions: Array<{ value: SourceType; label: string }> = [
  { value: 'crm_note', label: 'CRM note' },
  { value: 'meeting_notes', label: 'Meeting notes' },
  { value: 'salesforce_opportunity_note', label: 'Opportunity note' },
  { value: 'proposal', label: 'Proposal' },
  { value: 'deck', label: 'Deck' },
  { value: 'human_validated_context', label: 'Human validated' },
  { value: 'partner_material', label: 'Partner material' },
  { value: 'other', label: 'Other' },
]

const sourceSystemOptions: Array<{ value: SourceSystem; label: string }> = [
  { value: 'salesforce', label: 'Salesforce' },
  { value: 'calendar', label: 'Calendar' },
  { value: 'drive', label: 'Drive' },
  { value: 'human', label: 'Human review' },
  { value: 'partner_portal', label: 'Partner portal' },
  { value: 'other', label: 'Other' },
]

const directnessOptions: Array<{ value: DirectnessRelation; label: string }> = [
  { value: 'same_client_same_opportunity', label: 'Same opportunity' },
  { value: 'same_client_adjacent_opportunity', label: 'Adjacent opportunity' },
  { value: 'same_account_group', label: 'Same account group' },
  { value: 'closely_related_stakeholder', label: 'Related stakeholder' },
  { value: 'similar_client', label: 'Similar client' },
  { value: 'generic_industry', label: 'Generic industry' },
  { value: 'weak_match', label: 'Weak match' },
]

const sensitivityOptions: Array<{ value: SensitivityLabel; label: string }> = [
  { value: 'none', label: 'None' },
  { value: 'internal_only', label: 'Internal only' },
  { value: 'confidential', label: 'Confidential' },
  { value: 'partner_channel', label: 'Partner channel' },
  { value: 'unsupported_inference', label: 'Unsupported inference' },
]

const defaultSource = (): DraftSource => ({
  title: 'Recent account note',
  summary: 'The client asked for a clearer implementation plan before the renewal discussion.',
  claim: 'The client wants implementation risk addressed before renewal.',
  type: 'crm_note',
  sourceSystem: 'salesforce',
  directness: 'same_client_same_opportunity',
  createdAt: '2026-06-15',
  ownerName: 'Mina Patel',
  sensitivity: 'none',
  similarityReason: '',
})

const defaultState: BuilderState = {
  title: 'Manual renewal context',
  clientName: 'Acme',
  emailGoal: 'Prepare a renewal handoff with the safest available context.',
  primaryClaim: 'Current client concern that should shape the handoff.',
  secondaryClaim: 'Concrete next step or validated prior work that can be mentioned.',
  riskTolerance: 'normal',
  asOf: '2026-06-21',
  sources: [defaultSource()],
}

export function CustomScenarioBuilder({
  disabled,
  isRanking,
  isRunning,
  onRank,
  onRun,
}: {
  disabled?: boolean
  isRanking: boolean
  isRunning: boolean
  onRank: (request: CustomDecisionRunRequest) => void
  onRun: (request: CustomDecisionRunRequest) => void
}) {
  const [state, setState] = useState<BuilderState>(defaultState)
  const validationMessages = useMemo(() => validateBuilderState(state), [state])
  const canSubmit = validationMessages.length === 0 && !disabled && !isRunning

  function updateSource(index: number, patch: Partial<DraftSource>) {
    setState((current) => ({
      ...current,
      sources: current.sources.map((source, sourceIndex) =>
        sourceIndex === index ? { ...source, ...patch } : source,
      ),
    }))
  }

  function addSource() {
    setState((current) => ({
      ...current,
      sources: [
        ...current.sources,
        {
          ...defaultSource(),
          title: `Supporting source ${current.sources.length + 1}`,
          ownerName: '',
        },
      ],
    }))
  }

  function removeSource(index: number) {
    setState((current) => ({
      ...current,
      sources: current.sources.filter((_source, sourceIndex) => sourceIndex !== index),
    }))
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canSubmit) return
    onRun(buildCustomRunRequest(state))
  }

  function handleRankOnly() {
    if (!canSubmit) return
    onRank(buildCustomRunRequest(state))
  }

  return (
    <form className="custom-builder" onSubmit={handleSubmit}>
      <div className="custom-builder-toolbar">
        <div className="flex min-w-0 items-start gap-3">
          <span className="surface-icon size-10 shrink-0">
            <FilePlus2 size={20} />
          </span>
          <div className="min-w-0">
            <p className="section-label">Custom evidence</p>
            <h2 className="mt-1 text-2xl font-bold leading-tight text-ink">Build a scenario from scratch</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-muted">
              Add the context need and the evidence you would want the system to judge before a handoff.
            </p>
          </div>
        </div>
        <StatusBadge tone={validationMessages.length ? 'apricot' : 'sky'}>
          {validationMessages.length ? 'Needs detail' : 'Ready'}
        </StatusBadge>
      </div>

      <div className="custom-builder-grid mt-5">
        <section className="custom-builder-panel">
          <div>
            <p className="section-label">Context need</p>
            <h3 className="mt-1 text-xl font-bold leading-tight text-ink">What are we preparing?</h3>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <label>
              <span className="field-label">Scenario title</span>
              <input
                className="field mt-2"
                value={state.title}
                onChange={(event) => setState({ ...state, title: event.target.value })}
              />
            </label>
            <label>
              <span className="field-label">Client</span>
              <input
                className="field mt-2"
                value={state.clientName}
                onChange={(event) => setState({ ...state, clientName: event.target.value })}
              />
            </label>
            <label>
              <span className="field-label">Risk tolerance</span>
              <select
                className="field mt-2"
                value={state.riskTolerance}
                onChange={(event) =>
                  setState({ ...state, riskTolerance: event.target.value as RiskTolerance })
                }
              >
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
              </select>
            </label>
            <label>
              <span className="field-label">Assessment date</span>
              <input
                className="field mt-2"
                type="date"
                value={state.asOf}
                onChange={(event) => setState({ ...state, asOf: event.target.value })}
              />
            </label>
          </div>

          <label className="mt-3 block">
            <span className="field-label">Email goal</span>
            <textarea
              className="field custom-textarea mt-2"
              value={state.emailGoal}
              onChange={(event) => setState({ ...state, emailGoal: event.target.value })}
            />
          </label>

          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label>
              <span className="field-label">Required claim</span>
              <textarea
                className="field custom-textarea mt-2"
                value={state.primaryClaim}
                onChange={(event) => setState({ ...state, primaryClaim: event.target.value })}
              />
            </label>
            <label>
              <span className="field-label">Optional claim</span>
              <textarea
                className="field custom-textarea mt-2"
                value={state.secondaryClaim}
                onChange={(event) => setState({ ...state, secondaryClaim: event.target.value })}
              />
            </label>
          </div>
        </section>

        <section className="custom-builder-panel">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="section-label">Sources</p>
              <h3 className="mt-1 text-xl font-bold leading-tight text-ink">Evidence to evaluate</h3>
            </div>
            <button className="button-secondary" type="button" onClick={addSource}>
              <Plus size={17} />
              Add source
            </button>
          </div>

          <div className="mt-4 grid gap-3">
            {state.sources.map((source, index) => (
              <article className="custom-source-card" key={index}>
                <div className="custom-source-header">
                  <div className="min-w-0">
                    <p className="section-label">Source {index + 1}</p>
                    <h4 className="mt-1 text-base font-extrabold leading-tight text-ink">
                      {source.title || 'Untitled evidence'}
                    </h4>
                  </div>
                  <button
                    aria-label={`Remove source ${index + 1}`}
                    className="icon-button"
                    disabled={state.sources.length === 1}
                    type="button"
                    onClick={() => removeSource(index)}
                  >
                    <Trash2 size={17} />
                  </button>
                </div>

                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <label>
                    <span className="field-label">Source title</span>
                    <input
                      className="field mt-2"
                      value={source.title}
                      onChange={(event) => updateSource(index, { title: event.target.value })}
                    />
                  </label>
                  <label>
                    <span className="field-label">Owner</span>
                    <input
                      className="field mt-2"
                      value={source.ownerName}
                      onChange={(event) => updateSource(index, { ownerName: event.target.value })}
                    />
                  </label>
                  <label>
                    <span className="field-label">Type</span>
                    <select
                      className="field mt-2"
                      value={source.type}
                      onChange={(event) => updateSource(index, { type: event.target.value as SourceType })}
                    >
                      {sourceTypeOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span className="field-label">System</span>
                    <select
                      className="field mt-2"
                      value={source.sourceSystem}
                      onChange={(event) =>
                        updateSource(index, { sourceSystem: event.target.value as SourceSystem })
                      }
                    >
                      {sourceSystemOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span className="field-label">Directness</span>
                    <select
                      className="field mt-2"
                      value={source.directness}
                      onChange={(event) =>
                        updateSource(index, { directness: event.target.value as DirectnessRelation })
                      }
                    >
                      {directnessOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span className="field-label">Source date</span>
                    <input
                      className="field mt-2"
                      type="date"
                      value={source.createdAt}
                      onChange={(event) => updateSource(index, { createdAt: event.target.value })}
                    />
                  </label>
                  <label>
                    <span className="field-label">Sensitivity</span>
                    <select
                      className="field mt-2"
                      value={source.sensitivity}
                      onChange={(event) =>
                        updateSource(index, { sensitivity: event.target.value as SensitivityLabel })
                      }
                    >
                      {sensitivityOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  {source.directness === 'similar_client' ? (
                    <label>
                      <span className="field-label">Similarity reason</span>
                      <input
                        className="field mt-2"
                        value={source.similarityReason}
                        onChange={(event) => updateSource(index, { similarityReason: event.target.value })}
                      />
                    </label>
                  ) : null}
                </div>

                <label className="mt-3 block">
                  <span className="field-label">Source summary</span>
                  <textarea
                    className="field custom-textarea mt-2"
                    value={source.summary}
                    onChange={(event) => updateSource(index, { summary: event.target.value })}
                  />
                </label>
                <label className="mt-3 block">
                  <span className="field-label">Supported claim</span>
                  <textarea
                    className="field custom-textarea mt-2"
                    value={source.claim}
                    onChange={(event) => updateSource(index, { claim: event.target.value })}
                  />
                </label>
              </article>
            ))}
          </div>
        </section>
      </div>

      <div className="custom-builder-actions mt-4">
        <div className="min-w-0">
          {validationMessages.length ? (
            <p className="text-sm font-semibold leading-6 text-ink-muted">{validationMessages[0]}</p>
          ) : (
            <p className="flex items-center gap-2 text-sm font-semibold leading-6 text-ink-muted">
              <CheckCircle2 size={17} className="text-primary" />
              This scenario will be saved as a normal decision check.
            </p>
          )}
        </div>
        <button className="button-primary" disabled={!canSubmit} type="submit">
          {isRunning ? 'Checking...' : 'Check custom evidence'}
        </button>
        <button className="button-secondary" disabled={!canSubmit} type="button" onClick={handleRankOnly}>
          {isRanking ? 'Ranking...' : 'Rank only'}
        </button>
      </div>
    </form>
  )
}

function validateBuilderState(state: BuilderState) {
  const messages: string[] = []
  if (!state.title.trim()) messages.push('Add a scenario title.')
  if (!state.clientName.trim()) messages.push('Add a client name.')
  if (!state.emailGoal.trim()) messages.push('Add the email goal.')
  if (!state.primaryClaim.trim()) messages.push('Add at least one needed claim.')
  if (!state.asOf) messages.push('Choose an assessment date.')
  if (state.sources.length === 0) messages.push('Add at least one source.')
  state.sources.forEach((source, index) => {
    if (!source.title.trim()) messages.push(`Source ${index + 1} needs a title.`)
    if (!source.summary.trim()) messages.push(`Source ${index + 1} needs a summary.`)
    if (!source.claim.trim()) messages.push(`Source ${index + 1} needs a supported claim.`)
    if (source.directness === 'similar_client' && !source.similarityReason.trim()) {
      messages.push(`Source ${index + 1} needs a similarity reason.`)
    }
  })
  return messages
}

function buildCustomRunRequest(state: BuilderState): CustomDecisionRunRequest {
  const bundleId = `bundle_${slug(state.title) || 'manual_scenario'}`
  const clientId = `client_${slug(state.clientName) || 'manual_client'}`
  const primaryClaimId = 'need_claim_primary'
  const secondaryClaimId = 'need_claim_secondary'
  const neededClaims = [
    {
      id: primaryClaimId,
      type: claimTypeForNeededClaim(state.primaryClaim),
      description: state.primaryClaim.trim(),
      required: true,
    },
    ...(state.secondaryClaim.trim()
      ? [
          {
            id: secondaryClaimId,
            type: 'next_step' as NeededClaimType,
            description: state.secondaryClaim.trim(),
            required: false,
          },
        ]
      : []),
  ]

  return {
    as_of: state.asOf,
    bundle: {
      id: bundleId,
      title: state.title.trim(),
      context_need: {
        id: `need_${slug(state.title) || 'manual'}`,
        client_id: clientId,
        email_goal: state.emailGoal.trim(),
        needed_claims: neededClaims,
        risk_tolerance: state.riskTolerance,
        metadata: {
          created_from: 'manual_builder',
          client_name: state.clientName.trim(),
        },
      },
      sources: state.sources.map((source, index) =>
        buildCustomSource(source, index, clientId, primaryClaimId),
      ),
      metadata: {
        created_from: 'manual_builder',
      },
    },
  }
}

function buildCustomSource(
  draft: DraftSource,
  index: number,
  clientId: string,
  neededClaimId: string,
): CustomSource {
  const sourceId = `src_${slug(draft.title) || `manual_${index + 1}`}`
  const owner = draft.ownerName.trim()
  const ownerId = owner ? `user_${slug(owner)}` : ''
  return {
    id: sourceId,
    type: draft.type,
    title: draft.title.trim(),
    summary: draft.summary.trim(),
    client_id: clientId,
    directness_relation: draft.directness,
    similar_to_client_id: draft.directness === 'similar_client' ? 'similar_client' : undefined,
    similarity_reason:
      draft.directness === 'similar_client' ? draft.similarityReason.trim() : undefined,
    created_at: draft.createdAt || undefined,
    updated_at: draft.createdAt || undefined,
    author: owner ? { id: ownerId, name: owner, role: 'account_owner' } : undefined,
    owner_candidates: owner
      ? [
          {
            id: ownerId,
            name: owner,
            role: 'account_owner',
            reason: 'Named owner for this manually entered evidence.',
            confidence: 0.82,
          },
        ]
      : [],
    sensitivity_labels: draft.sensitivity === 'none' ? [] : [draft.sensitivity],
    source_system: draft.sourceSystem,
    claims: [
      {
        id: `claim_${slug(draft.title) || `manual_${index + 1}`}`,
        text: draft.claim.trim(),
        claim_type: claimTypeForSource(draft),
        supports_needed_claim_ids: [neededClaimId],
        source_ids: [sourceId],
      },
    ],
    metadata: {
      created_from: 'manual_builder',
    },
  }
}

function claimTypeForNeededClaim(value: string): NeededClaimType {
  const normalized = value.toLowerCase()
  if (normalized.includes('owner')) return 'likely_account_owner'
  if (normalized.includes('risk')) return 'implementation_risk'
  if (normalized.includes('prior') || normalized.includes('work')) return 'validated_prior_work'
  if (normalized.includes('next')) return 'next_step'
  return 'current_client_concern'
}

function claimTypeForSource(source: DraftSource): ClaimType {
  if (source.directness === 'similar_client') return 'similar_client_context'
  if (source.type === 'proposal') return 'prior_work'
  if (source.sensitivity === 'unsupported_inference') return 'unsupported_inference'
  return 'client_concern'
}

function slug(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}
