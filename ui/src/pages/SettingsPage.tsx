import { Bell, Check, DatabaseZap, Moon, Palette, PlugZap, RotateCcw, Settings2, Sun, UserCircle, Workflow, X } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { useHealthQuery, useResetLocalDataMutation } from '../api/queries'
import { useTheme } from '../app/theme-context'
import { themeColors, type ThemeColor, type ThemeMode } from '../app/theme-options'
import { AppShell } from '../components/AppShell'
import { StatusBadge } from '../components/StatusBadge'

type SettingsSection = 'appearance' | 'notifications' | 'user' | 'systems' | 'data'

const modes: Array<{ id: ThemeMode; label: string; detail: string; icon: LucideIcon }> = [
  { id: 'light', label: 'Light', detail: 'Bright workspace surfaces', icon: Sun },
  { id: 'dark', label: 'Dark', detail: 'Low-glare command surfaces', icon: Moon },
]

const settingsSections: Array<{ id: SettingsSection; label: string; icon: LucideIcon }> = [
  { id: 'appearance', label: 'Appearance', icon: Palette },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'user', label: 'User', icon: UserCircle },
  { id: 'systems', label: 'Systems', icon: PlugZap },
  { id: 'data', label: 'Data', icon: DatabaseZap },
]

const defaultNotificationPrefs = {
  reviewPrompts: true,
  runCompletions: true,
  learningUpdates: false,
}

const defaultProfile = {
  displayName: 'Local User',
  initials: 'LS',
}

const systemStatuses = [
  {
    title: 'Source systems',
    status: 'Simulated',
    detail: 'Salesforce, Drive, Calendar, partner material, and human review are represented through normalized fixtures and manual evidence.',
    next: 'Future connector records map into SourceSystemConnection and EvidenceSource.',
  },
  {
    title: 'Persistence',
    status: 'Local now',
    detail: 'Runs, review answers, and feedback learning are still saved through API-owned local stores.',
    next: 'Amplify models are shaped for workspaces, clients, scenarios, runs, review tasks, and feedback.',
  },
  {
    title: 'Review sharing',
    status: 'Local route',
    detail: 'Review work opens as a local route with a local reviewer identity.',
    next: 'ReviewTask can later carry assignment, status history, and share/email delivery.',
  },
  {
    title: 'Background jobs',
    status: 'Synchronous',
    detail: 'Ranking, decision checks, and guided checks finish immediately in the current local app.',
    next: 'EvidenceRun status is modelled for queued, running, completed, and failed states.',
  },
]

export function SettingsPage() {
  const health = useHealthQuery()
  const { color, mode, setColor, setMode } = useTheme()
  const [searchParams] = useSearchParams()
  const [notificationPrefs, setNotificationPrefs] = useStoredState(
    'source-signal-notification-settings',
    defaultNotificationPrefs,
  )
  const [profile, setProfile] = useStoredState('source-signal-local-profile', defaultProfile)

  const sectionParam = searchParams.get('section')
  const section = settingsSections.some((item) => item.id === sectionParam)
    ? (sectionParam as SettingsSection)
    : 'appearance'

  return (
    <AppShell apiConnected={health.isSuccess} onRefresh={() => void health.refetch()}>
      <div className="mx-auto max-w-6xl">
        <section className="workspace-surface relative overflow-hidden">
          <Link to="/" className="settings-close-button" aria-label="Exit settings" title="Exit settings">
            <X size={18} strokeWidth={2.4} />
          </Link>
          <div className="grid lg:grid-cols-[238px_minmax(0,1fr)]">
            <aside className="border-b border-border-soft/80 bg-[var(--surface-panel)] p-4 sm:p-5 lg:border-b-0 lg:border-r">
              <div className="flex items-center gap-3">
                <span className="grid size-10 place-items-center rounded-lg bg-primary text-white shadow-soft">
                  <Settings2 size={20} />
                </span>
                <div>
                  <p className="section-label">Settings</p>
                  <h1 className="display-type text-xl font-bold leading-tight">Workspace</h1>
                </div>
              </div>

              <nav className="mt-5 grid gap-2" aria-label="Settings sections">
                {settingsSections.map((item) => (
                  <SettingsRailLink key={item.id} section={item.id} icon={<item.icon size={17} />} active={section === item.id}>
                    {item.label}
                  </SettingsRailLink>
                ))}
              </nav>
            </aside>

            <div className="p-5 pr-16 sm:p-7 sm:pr-20">
              {section === 'appearance' ? (
                <AppearanceSettings color={color} mode={mode} setColor={setColor} setMode={setMode} />
              ) : null}

              {section === 'notifications' ? (
                <NotificationsSettings
                  notificationPrefs={notificationPrefs}
                  setNotificationPrefs={setNotificationPrefs}
                />
              ) : null}

              {section === 'user' ? <UserSettings profile={profile} setProfile={setProfile} /> : null}

              {section === 'systems' ? <SystemsSettings /> : null}

              {section === 'data' ? <DataSettings /> : null}
            </div>
          </div>
        </section>
      </div>
    </AppShell>
  )
}

function AppearanceSettings({
  color,
  mode,
  setColor,
  setMode,
}: {
  color: ThemeColor
  mode: ThemeMode
  setColor: (color: ThemeColor) => void
  setMode: (mode: ThemeMode) => void
}) {
  return (
    <div className="space-y-5">
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
        <div>
          <p className="section-label">Appearance</p>
          <h2 className="mt-3 max-w-2xl text-4xl font-bold leading-[1.02] text-ink sm:text-5xl">
            Theme controls that stay out of the way.
          </h2>
          <p className="mt-4 max-w-2xl text-base leading-7 text-ink-muted">
            Choose a workspace mode first, then choose the accent family independently.
          </p>
        </div>

        <div className="seamless-panel p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="section-label">Current theme</p>
              <h3 className="mt-2 display-type text-2xl font-bold leading-tight capitalize">
                {color} · {mode}
              </h3>
            </div>
            <Palette className="mt-1 text-primary" size={22} />
          </div>
          <div className="mt-5 grid grid-cols-2 gap-2">
            <span className="theme-swatch h-14 w-full" data-mode-choice={mode} />
            <span className="theme-swatch h-14 w-full" data-theme-choice={color} />
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <StatusBadge tone="neutral">Appearance</StatusBadge>
            <StatusBadge tone="sky">Saved locally</StatusBadge>
          </div>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,0.82fr)_minmax(0,1.18fr)]">
        <section className="seamless-panel p-5 sm:p-6">
          <div className="flex items-center gap-3">
            <span className="surface-icon size-10">
              <Sun size={20} />
            </span>
            <div>
              <p className="section-label">Mode</p>
              <h3 className="text-2xl font-bold leading-tight">Light or dark</h3>
            </div>
          </div>

          <div className="mt-5 grid gap-3">
            {modes.map((themeMode) => {
              const Icon = themeMode.icon
              return (
                <ThemeChoice
                  key={themeMode.id}
                  selected={mode === themeMode.id}
                  label={themeMode.label}
                  detail={themeMode.detail}
                  onClick={() => setMode(themeMode.id)}
                >
                  <span className="theme-swatch" data-mode-choice={themeMode.id} />
                  <Icon size={18} className="text-primary" />
                </ThemeChoice>
              )
            })}
          </div>
        </section>

        <section className="seamless-panel p-5 sm:p-6">
          <div className="flex items-center gap-3">
            <span className="surface-icon size-10">
              <Palette size={20} />
            </span>
            <div>
              <p className="section-label">Color</p>
              <h3 className="text-2xl font-bold leading-tight">Accent family</h3>
            </div>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-3">
            {themeColors.map((themeColor) => (
              <ColorChoice
                key={themeColor.id}
                color={themeColor.id}
                selected={color === themeColor.id}
                label={themeColor.label}
                detail={themeColor.detail}
                onClick={() => setColor(themeColor.id)}
              />
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}

function NotificationsSettings({
  notificationPrefs,
  setNotificationPrefs,
}: {
  notificationPrefs: typeof defaultNotificationPrefs
  setNotificationPrefs: (value: typeof defaultNotificationPrefs) => void
}) {
  return (
    <div className="max-w-3xl">
      <p className="section-label">Notifications</p>
      <h2 className="mt-3 text-4xl font-bold leading-[1.02] text-ink sm:text-5xl">Signals worth interrupting for.</h2>
      <p className="mt-4 text-base leading-7 text-ink-muted">
        Keep local alerts focused on review work, completed checks, and reliability movement.
      </p>

      <div className="mt-6 grid gap-3">
        <PreferenceToggle
          label="Review prompts"
          detail="Context questions and reviewer decisions."
          checked={notificationPrefs.reviewPrompts}
          onChange={(checked) => setNotificationPrefs({ ...notificationPrefs, reviewPrompts: checked })}
        />
        <PreferenceToggle
          label="Completed checks"
          detail="Finished quick checks and guided checks."
          checked={notificationPrefs.runCompletions}
          onChange={(checked) => setNotificationPrefs({ ...notificationPrefs, runCompletions: checked })}
        />
        <PreferenceToggle
          label="Learning updates"
          detail="Source reliability changes after reviewer feedback."
          checked={notificationPrefs.learningUpdates}
          onChange={(checked) => setNotificationPrefs({ ...notificationPrefs, learningUpdates: checked })}
        />
      </div>
    </div>
  )
}

function UserSettings({
  profile,
  setProfile,
}: {
  profile: typeof defaultProfile
  setProfile: (value: typeof defaultProfile) => void
}) {
  return (
    <div className="max-w-3xl">
      <p className="section-label">User</p>
      <h2 className="mt-3 text-4xl font-bold leading-[1.02] text-ink sm:text-5xl">Local workspace identity.</h2>
      <p className="mt-4 text-base leading-7 text-ink-muted">
        This profile labels the local review environment without needing authentication.
      </p>

      <div className="mt-6 grid gap-4 md:grid-cols-[96px_minmax(0,1fr)]">
        <div className="grid size-24 place-items-center rounded-xl bg-primary text-2xl font-extrabold text-white shadow-soft">
          {profile.initials || 'LS'}
        </div>
        <div className="grid gap-4">
          <label>
            <span className="field-label">Display name</span>
            <input
              className="field mt-2"
              value={profile.displayName}
              onChange={(event) => setProfile({ ...profile, displayName: event.target.value })}
            />
          </label>
          <label>
            <span className="field-label">Initials</span>
            <input
              className="field mt-2 max-w-28 uppercase"
              maxLength={3}
              value={profile.initials}
              onChange={(event) => setProfile({ ...profile, initials: event.target.value.toUpperCase() })}
            />
          </label>
        </div>
      </div>
    </div>
  )
}

function SystemsSettings() {
  return (
    <div className="max-w-5xl">
      <p className="section-label">Systems</p>
      <h2 className="mt-3 max-w-3xl text-4xl font-bold leading-[1.02] text-ink sm:text-5xl">
        Local today, ready for real systems later.
      </h2>
      <p className="mt-4 max-w-3xl text-base leading-7 text-ink-muted">
        These are the production-facing seams. They are visible here so the product direction is clear, while the current app stays honest about what is simulated.
      </p>

      <div className="system-status-grid mt-6">
        {systemStatuses.map((item) => (
          <article className="system-status-card" key={item.title}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="section-label">{item.status}</p>
                <h3>{item.title}</h3>
              </div>
              <span className="surface-icon size-10">
                {item.title === 'Background jobs' ? <Workflow size={19} /> : <PlugZap size={19} />}
              </span>
            </div>
            <p>{item.detail}</p>
            <div className="system-next-step">
              <Check size={16} />
              <span>{item.next}</span>
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}

function DataSettings() {
  const resetLocalData = useResetLocalDataMutation()
  const [selection, setSelection] = useState({ runs: true, reviews: true, feedback: true })
  const [confirming, setConfirming] = useState(false)
  const selectedCount = Object.values(selection).filter(Boolean).length
  const canReset = selectedCount > 0 && !resetLocalData.isPending
  const resetResult = resetLocalData.data

  function updateSelection(key: keyof typeof selection) {
    setConfirming(false)
    resetLocalData.reset()
    setSelection((current) => ({ ...current, [key]: !current[key] }))
  }

  async function handleReset() {
    if (!canReset) return
    if (!confirming) {
      setConfirming(true)
      return
    }
    await resetLocalData.mutateAsync(selection)
    setConfirming(false)
  }

  return (
    <div className="max-w-4xl">
      <p className="section-label">Data</p>
      <h2 className="mt-3 text-4xl font-bold leading-[1.02] text-ink sm:text-5xl">Reset the local workspace.</h2>
      <p className="mt-4 max-w-2xl text-base leading-7 text-ink-muted">
        Clear generated product state before a fresh test run. Fixtures, scoring rules, and UI preferences stay in place.
      </p>

      <section className="data-reset-panel mt-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-3">
            <span className="surface-icon size-10 shrink-0">
              <DatabaseZap size={20} />
            </span>
            <div className="min-w-0">
              <h3 className="text-2xl font-bold leading-tight text-ink">Demo data reset</h3>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-muted">
                Use this when you want the app to feel new again during product testing.
              </p>
            </div>
          </div>
          <StatusBadge tone="neutral">{selectedCount} selected</StatusBadge>
        </div>

        <div className="reset-scope-grid mt-5">
          <ResetScopeOption
            checked={selection.runs}
            label="Run history"
            detail="Saved quick checks, guided checks, and visible history."
            onClick={() => updateSelection('runs')}
          />
          <ResetScopeOption
            checked={selection.reviews}
            label="Review answers"
            detail="Reviewer choices captured against previous runs."
            onClick={() => updateSelection('reviews')}
          />
          <ResetScopeOption
            checked={selection.feedback}
            label="Learning feedback"
            detail="Reliability signals created from accepted or rejected outcomes."
            onClick={() => updateSelection('feedback')}
          />
        </div>

        {confirming ? (
          <div className="reset-confirm-strip mt-5">
            <RotateCcw size={18} />
            <span>This will clear the selected workspace data. The sample fixtures remain available.</span>
          </div>
        ) : null}

        {resetResult ? (
          <div className="feedback-saved mt-5">
            <Check size={18} />
            <span>
              Reset complete. Cleared {formatResetSummary(resetResult.counts_before)}.
            </span>
          </div>
        ) : null}

        {resetLocalData.error ? (
          <div className="feedback-error mt-5">
            <X size={18} />
            <span>{errorText(resetLocalData.error)}</span>
          </div>
        ) : null}

        <div className="mt-5 flex flex-wrap justify-end gap-2">
          {confirming ? (
            <button
              type="button"
              className="button-secondary"
              onClick={() => setConfirming(false)}
              disabled={resetLocalData.isPending}
            >
              Cancel
            </button>
          ) : null}
          <button type="button" className="button-danger" onClick={() => void handleReset()} disabled={!canReset}>
            {resetLocalData.isPending ? 'Resetting...' : confirming ? 'Confirm reset' : 'Review reset'}
          </button>
        </div>
      </section>
    </div>
  )
}

function ResetScopeOption({
  checked,
  label,
  detail,
  onClick,
}: {
  checked: boolean
  label: string
  detail: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      className={`reset-scope-option ${checked ? 'reset-scope-option-selected' : ''}`}
      aria-pressed={checked}
      onClick={onClick}
    >
      <span className="grid size-8 place-items-center rounded-lg border border-border-soft bg-[var(--surface-panel-strong)]">
        {checked ? <Check size={17} className="text-primary" /> : null}
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-extrabold text-ink">{label}</span>
        <span className="mt-1 block text-sm leading-6 text-ink-muted">{detail}</span>
      </span>
    </button>
  )
}

function SettingsRailLink({
  section,
  icon,
  active,
  children,
}: {
  section: SettingsSection
  icon: ReactNode
  active: boolean
  children: ReactNode
}) {
  return (
    <Link
      to={section === 'appearance' ? '/settings' : `/settings?section=${section}`}
      className={`flex min-h-11 items-center gap-3 rounded-lg px-3 text-sm font-bold transition-colors duration-150 ${
        active ? 'bg-primary text-white shadow-soft' : 'text-ink-muted hover:bg-[var(--surface-hover)] hover:text-ink'
      }`}
      aria-current={active ? 'page' : undefined}
    >
      {icon}
      {children}
    </Link>
  )
}

function PreferenceToggle({
  label,
  detail,
  checked,
  onChange,
}: {
  label: string
  detail: string
  checked: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <button type="button" className="theme-option min-h-20" role="switch" aria-checked={checked} onClick={() => onChange(!checked)}>
      <span className="relative h-7 w-12 rounded-full bg-[var(--surface-panel-strong)] ring-1 ring-border-soft">
        <span
          className={`absolute top-1 size-5 rounded-full transition-[left,background-color] duration-150 ${
            checked ? 'left-6 bg-primary' : 'left-1 bg-ink-muted'
          }`}
        />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-base font-bold text-ink">{label}</span>
        <span className="mt-1 block text-sm leading-6 text-ink-muted">{detail}</span>
      </span>
      <StatusBadge tone={checked ? 'sky' : 'neutral'}>{checked ? 'On' : 'Off'}</StatusBadge>
    </button>
  )
}

function ThemeChoice({
  selected,
  label,
  detail,
  children,
  onClick,
}: {
  selected: boolean
  label: string
  detail: string
  children: ReactNode
  onClick: () => void
}) {
  return (
    <button
      type="button"
      className={`theme-option min-h-20 ${selected ? 'theme-option-selected' : ''}`}
      onClick={onClick}
      aria-pressed={selected}
    >
      <span className="flex items-center gap-3">{children}</span>
      <span className="min-w-0 flex-1 text-left">
        <span className="block text-base font-bold text-ink">{label}</span>
        <span className="mt-1 block text-sm leading-6 text-ink-muted">{detail}</span>
      </span>
      {selected ? <Check size={18} className="text-primary" /> : null}
    </button>
  )
}

function ColorChoice({
  color,
  selected,
  label,
  detail,
  onClick,
}: {
  color: ThemeColor
  selected: boolean
  label: string
  detail: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      className={`theme-option min-h-36 flex-col items-start ${selected ? 'theme-option-selected' : ''}`}
      onClick={onClick}
      aria-pressed={selected}
    >
      <span className="flex w-full items-start justify-between gap-3">
        <span className="theme-swatch" data-theme-choice={color} />
        {selected ? <Check size={18} className="text-primary" /> : null}
      </span>
      <span className="mt-4 text-left">
        <span className="block text-base font-bold text-ink">{label}</span>
        <span className="mt-1 block text-sm leading-6 text-ink-muted">{detail}</span>
      </span>
    </button>
  )
}

function useStoredState<T>(key: string, fallback: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = window.localStorage.getItem(key)
      return stored ? (JSON.parse(stored) as T) : fallback
    } catch {
      return fallback
    }
  })

  useEffect(() => {
    window.localStorage.setItem(key, JSON.stringify(value))
  }, [key, value])

  return [value, setValue] as const
}

function formatResetSummary(counts: Record<string, number>) {
  const labels: Record<string, string> = {
    runs: 'run history',
    reviews: 'review answers',
    feedback: 'learning feedback',
  }
  const parts = Object.entries(counts).map(([key, count]) => `${count} ${labels[key] ?? key}`)
  return parts.length > 0 ? parts.join(', ') : 'no saved records'
}

function errorText(error: unknown) {
  return error instanceof Error ? error.message : 'Reset failed. Please try again.'
}
