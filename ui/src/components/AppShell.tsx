import { Activity, Bell, Database, History, RefreshCw, Settings2, ShieldCheck } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, NavLink } from 'react-router-dom'

import { StatusBadge } from './StatusBadge'

export function AppShell({
  apiConnected,
  children,
  onRefresh,
}: {
  apiConnected: boolean
  children: ReactNode
  onRefresh: () => void
}) {
  return (
    <div className="h-dvh overflow-hidden text-ink">
      <div className="app-frame grid h-dvh w-full overflow-hidden lg:grid-cols-[244px_minmax(0,1fr)]">
        <aside className="app-sidebar hidden min-h-0 border-r border-border-soft px-5 py-5 lg:flex lg:flex-col">
          <Link to="/" className="focus-ring flex items-center gap-3 rounded-lg">
            <span className="grid size-12 place-items-center rounded-lg bg-primary text-white shadow-soft">
              <ShieldCheck size={24} strokeWidth={2.2} />
            </span>
            <span>
              <span className="block text-xl font-bold leading-tight">Source Signal</span>
              <span className="block text-sm text-ink-muted">Evidence desk</span>
            </span>
          </Link>

          <nav className="mt-8 space-y-2">
            <SidebarLink to="/" icon={<Database size={18} />}>
              Console
            </SidebarLink>
            <SidebarLink to="/review/local" icon={<History size={18} />}>
              Review
            </SidebarLink>
          </nav>

          <div className="theme-card mt-8 p-4">
            <p className="section-label">Workspace</p>
            <p className="mt-3 text-3xl font-bold leading-none">Local</p>
            <p className="mt-2 text-sm leading-6 text-ink-muted">Synthetic and saved evidence checks.</p>
          </div>

          <div className="mt-auto space-y-3">
            <StatusBadge tone={apiConnected ? 'mint' : 'rose'}>
              <Activity size={14} />
              API {apiConnected ? 'online' : 'offline'}
            </StatusBadge>
            <button type="button" className="icon-button w-full" onClick={onRefresh} aria-label="Refresh data">
              <RefreshCw size={18} />
            </button>
          </div>
        </aside>

        <div className="flex min-h-0 min-w-0 flex-col">
          <header className="shrink-0 border-b border-border-soft bg-[var(--surface-panel)] px-4 py-4 sm:px-6 lg:px-7">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <Link to="/" className="focus-ring flex items-center gap-3 rounded-lg lg:hidden">
                <span className="grid size-11 place-items-center rounded-lg bg-primary text-white shadow-soft">
                  <ShieldCheck size={22} strokeWidth={2.2} />
                </span>
                <span>
                  <span className="block text-lg font-bold leading-tight">Source Signal</span>
                  <span className="block text-sm text-ink-muted">Evidence desk</span>
                </span>
              </Link>

              <nav className="theme-card flex min-h-11 items-center p-1 lg:hidden">
                <TopLink to="/" icon={<Database size={16} />}>
                  Console
                </TopLink>
                <TopLink to="/review/local" icon={<History size={16} />}>
                  Review
                </TopLink>
              </nav>

              <div className="flex flex-wrap items-center gap-2 lg:ml-auto">
                <div className="app-utility-bar">
                  <Link to="/settings?section=notifications" className="utility-button" aria-label="Notifications">
                    <Bell size={18} />
                  </Link>
                  <NavLink
                    to="/settings"
                    className={({ isActive }) =>
                      `utility-button ${isActive ? 'utility-button-active' : ''}`
                    }
                    aria-label="Settings"
                  >
                    <Settings2 size={18} />
                  </NavLink>
                  <span className="mx-1 hidden h-6 w-px bg-border-soft sm:block" aria-hidden="true" />
                  <Link
                    to="/settings?section=user"
                    className="user-chip hidden items-center gap-2 px-2 pr-3 text-sm font-bold text-ink sm:flex"
                    aria-label="User settings"
                  >
                    <span className="grid size-8 place-items-center rounded-lg bg-primary text-xs font-extrabold text-white shadow-soft">
                      LS
                    </span>
                    Local
                  </Link>
                </div>
                <StatusBadge tone={apiConnected ? 'mint' : 'rose'}>
                  <Activity size={14} />
                  {apiConnected ? 'online' : 'offline'}
                </StatusBadge>
                <button type="button" className="icon-button" onClick={onRefresh} aria-label="Refresh data">
                  <RefreshCw size={18} />
                </button>
              </div>
            </div>
          </header>

          <main className="app-main-scroll min-h-0 min-w-0 flex-1 overflow-y-auto overscroll-contain px-4 py-5 sm:px-6 lg:px-7 lg:py-7">
            {children}
          </main>
        </div>
      </div>
    </div>
  )
}

function SidebarLink({ to, icon, children }: { to: string; icon: ReactNode; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex min-h-11 items-center gap-3 rounded-lg px-3 text-sm font-semibold transition ${
          isActive ? 'bg-primary text-white shadow-soft' : 'text-ink-muted hover:bg-[var(--surface-hover)] hover:text-ink'
        }`
      }
    >
      {icon}
      {children}
    </NavLink>
  )
}

function TopLink({ to, icon, children }: { to: string; icon: ReactNode; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `inline-flex min-h-9 items-center gap-2 rounded-lg px-2 text-sm font-semibold transition sm:px-3 ${
          isActive ? 'bg-primary text-white shadow-soft' : 'text-ink-muted hover:bg-[var(--surface-hover)] hover:text-ink'
        }`
      }
    >
      {icon}
      {children}
    </NavLink>
  )
}
