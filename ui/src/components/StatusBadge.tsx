import type { ReactNode } from 'react'

type BadgeTone = 'mint' | 'sky' | 'apricot' | 'lavender' | 'rose' | 'neutral'

const toneClass: Record<BadgeTone, string> = {
  mint: 'bg-mint-100/80 text-mint-900 ring-mint-300',
  sky: 'bg-sky-100/80 text-sky-900 ring-sky-300',
  apricot: 'bg-apricot-100/80 text-apricot-900 ring-apricot-300',
  lavender: 'bg-lavender-100/80 text-lavender-900 ring-lavender-300',
  rose: 'bg-rose-100/80 text-rose-900 ring-rose-300',
  neutral: 'bg-[var(--surface-panel)] text-ink-muted ring-border-soft',
}

export function StatusBadge({
  children,
  tone = 'neutral',
}: {
  children: ReactNode
  tone?: BadgeTone
}) {
  return (
    <span
      className={`inline-flex min-h-7 items-center gap-1.5 rounded-full px-3 text-xs font-semibold ring-1 ${toneClass[tone]}`}
    >
      {children}
    </span>
  )
}
