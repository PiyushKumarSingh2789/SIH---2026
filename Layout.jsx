import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import GlobalSearch from './GlobalSearch'
import NotificationsPanel from './NotificationsPanel'

const NAV_GROUPS = [
  {
    label: 'Overview',
    items: [
      { to: '/dashboard', label: 'Executive Dashboard' },
      { to: '/analytics', label: 'Portfolio Analytics' },
      { to: '/queue', label: 'Risk Queue' },
      { to: '/projects', label: 'Project Explorer' },
      { to: '/map', label: 'Map Intelligence' },
    ],
  },
  {
    label: 'Investigation',
    items: [
      { to: '/cases', label: 'Case Workspace' },
      { to: '/compliance', label: 'Compliance Center' },
      { to: '/audit', label: 'Audit Trail' },
    ],
  },
  {
    label: 'Data',
    items: [{ to: '/import', label: 'Import Console' }],
  },
]

export default function Layout({ children }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex min-h-screen bg-paper">
      <aside className="flex w-64 shrink-0 flex-col border-r border-hairline bg-paper-raised">
        <div className="border-b border-hairline px-6 py-5">
          <p className="font-display text-lg font-semibold leading-tight text-ink">MPLADS Risk<br />Intelligence</p>
          <p className="mt-1 text-xs text-slate">SIH26102</p>
        </div>
        <nav className="flex-1 overflow-y-auto px-3 py-4">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="mb-4">
              <p className="px-3 pb-1.5 text-[11px] font-medium uppercase tracking-wide text-slate">{group.label}</p>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `block rounded-sm px-3 py-2 text-sm mb-1 transition-colors ${
                      isActive ? 'bg-ink text-paper' : 'text-ink-soft hover:bg-paper'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="border-t border-hairline px-4 py-4">
          <p className="text-sm font-medium text-ink">{user?.full_name}</p>
          <p className="text-xs capitalize text-slate">{user?.roles?.join(', ').replace(/_/g, ' ')}</p>
          {user?.scopes?.[0]?.scope_value && (
            <p className="text-xs text-slate">Scope: {user.scopes[0].scope_value}</p>
          )}
          <button
            onClick={handleLogout}
            className="mt-3 text-xs font-medium text-slate underline decoration-hairline underline-offset-2 hover:text-ink"
          >
            Sign out
          </button>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-hairline bg-card px-6 py-3">
          <GlobalSearch />
          <div className="flex items-center gap-3">
            <NotificationsPanel />
          </div>
        </header>
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  )
}
