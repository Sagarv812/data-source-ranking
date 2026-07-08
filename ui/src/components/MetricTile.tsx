import type { ReactNode } from 'react'

export function MetricTile({
  label,
  value,
  detail,
  icon,
}: {
  label: string
  value: string | number
  detail: string
  icon: ReactNode
}) {
  return (
    <section className="panel min-h-32 p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-ink-muted">{label}</p>
        <span className="surface-icon size-9">
          {icon}
        </span>
      </div>
      <p className="mt-4 text-3xl font-bold leading-none text-ink">{value}</p>
      <p className="mt-2 text-sm leading-6 text-ink-muted">{detail}</p>
    </section>
  )
}
