import { Bell, Check, Moon, Palette, Settings2, Sun, UserCircle, X } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { useHealthQuery } from '../api/queries'
import { useTheme } from '../app/theme-context'
import { themeColors, type ThemeColor, type ThemeMode } from '../app/theme-options'
import { AppShell } from '../components/AppShell'
import { StatusBadge } from '../components/StatusBadge'

type SettingsSection = 'appearance' | 'notifications' | 'user'

const modes: Array<{ id: ThemeMode; label: string; detail: string; icon: LucideIcon }> = [
  { id: 'light', label: 'Light', detail: 'Bright workspace surfaces', icon: Sun },
  { id: 'dark', label: 'Dark', detail: 'Low-glare command surfaces', icon: Moon },
]

const settingsSections: Array<{ id: SettingsSection; label: string; icon: LucideIcon }> = [
  { id: 'appearance', label: 'Appearance', icon: Palette },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'user', label: 'User', icon: UserCircle },
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

            <div className="p-5 sm:p-7">
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
            <span className="grid size-10 place-items-center rounded-lg bg-mint-100 text-primary ring-1 ring-mint-300">
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
            <span className="grid size-10 place-items-center rounded-lg bg-mint-100 text-primary ring-1 ring-mint-300">
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
      className={`flex min-h-11 items-center gap-3 rounded-lg px-3 text-sm font-bold transition ${
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
          className={`absolute top-1 size-5 rounded-full transition ${
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
