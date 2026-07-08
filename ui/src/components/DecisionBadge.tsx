import type { CSSProperties } from 'react'

const decisionMeta: Record<
  string,
  {
    label: string
    bg: string
    fg: string
    line: string
  }
> = {
  auto_handoff: {
    label: 'Ready to send',
    bg: 'var(--status-auto-soft)',
    fg: 'var(--status-auto)',
    line: 'var(--status-auto-line)',
  },
  generate_context_request: {
    label: 'Needs context',
    bg: 'var(--status-context-soft)',
    fg: 'var(--status-context)',
    line: 'var(--status-context-line)',
  },
  needs_user_review: {
    label: 'Needs review',
    bg: 'var(--status-review-soft)',
    fg: 'var(--status-review)',
    line: 'var(--status-review-line)',
  },
  blocked: {
    label: 'Blocked',
    bg: 'var(--status-blocked-soft)',
    fg: 'var(--status-blocked)',
    line: 'var(--status-blocked-line)',
  },
}

export function DecisionBadge({ decision }: { decision: string }) {
  const meta = decisionMeta[decision] ?? {
    label: humanize(decision),
    bg: 'var(--surface-panel)',
    fg: 'var(--text-muted)',
    line: 'var(--line-soft)',
  }

  return (
    <span
      className="decision-token"
      style={
        {
          '--decision-bg': meta.bg,
          '--decision-fg': meta.fg,
          '--decision-line': meta.line,
        } as CSSProperties
      }
    >
      {meta.label}
    </span>
  )
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
