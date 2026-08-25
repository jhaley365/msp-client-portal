import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuthContext } from '../app/AuthContext'
import { initials } from '../lib/user'
import { useTheme } from '../hooks/useTheme'
import CreateTicketModal from './CreateTicketModal'
import Icon from './Icon'
import Logo from './Logo'

const NAV = [
  { to: '/', label: 'Dashboard', icon: 'dashboard', end: true },
  { to: '/aws', label: 'AWS', icon: 'cloud' },
  { to: '/tickets', label: 'Tickets', icon: 'confirmation_number' },
  { to: '/security', label: 'Huntress', icon: 'shield' },
  { to: '/dns', label: 'ScoutDNS', icon: 'dns' },
  { to: '/o365', label: 'Office 365', icon: 'mail' },
  { to: '/apps', label: 'Apps', icon: 'apps' },
  { to: '/monitoring', label: 'Monitoring', icon: 'monitor_heart' },
]

const ADMIN_NAV = [
  { to: '/admin/users', label: 'Users', icon: 'group' },
  { to: '/admin/audit', label: 'Audit Log', icon: 'history' },
]

// Derive a breadcrumb label from the current pathname
function useBreadcrumb(allNav: typeof NAV) {
  const { pathname } = useLocation()
  const match = allNav.find((n) =>
    n.end ? pathname === n.to : pathname === n.to || pathname.startsWith(n.to + '/')
  )
  return match?.label ?? ''
}

export default function Layout() {
  const { user, logout, viewAsCustomerId, setViewAsCustomerId, customers, activeCustomerName } =
    useAuthContext()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [ticketOpen, setTicketOpen] = useState(false)
  // Mobile drawer open state
  const [drawerOpen, setDrawerOpen] = useState(false)
  const userMenuRef = useRef<HTMLDivElement>(null)

  const allNav = user?.is_admin ? [...NAV, ...ADMIN_NAV] : NAV
  const breadcrumb = useBreadcrumb(allNav)

  useEffect(() => {
    if (!userMenuOpen) return
    const onClick = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [userMenuOpen])

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const handleCustomerChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setViewAsCustomerId(e.target.value)
    window.location.reload()
  }

  return (
    <div className="flex h-screen overflow-hidden bg-page text-ink-primary">

      {/* ── Left icon rail (88px, collapses to icon-only at <1100px) ── */}
      <aside className="hidden sm:flex flex-col flex-none bg-rail border-r border-panel-border"
        style={{ width: 88 }}>

        {/* Rail header — 58px, shares baseline with topbar */}
        <div className="flex h-[58px] flex-none items-center justify-center border-b border-panel-border">
          <Logo />
        </div>

        {/* Nav items */}
        <nav className="flex flex-1 flex-col gap-0.5 px-2 py-2">
          {allNav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={'end' in item ? (item.end as boolean) : false}
              title={item.label}
              className={({ isActive }) =>
                `flex flex-col items-center gap-1 rounded-[7px] px-1 py-[11px] transition-colors ${
                  isActive
                    ? 'bg-rail-active text-ink-primary'
                    : 'text-ink-muted hover:bg-rail-active/60 hover:text-ink-primary'
                }`
              }
            >
              <Icon name={item.icon} className="text-[21px]" />
              <span className="text-[10px] font-medium leading-none tracking-wide">
                {item.label}
              </span>
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* ── Mobile bottom bar ── */}
      <nav className="fixed bottom-0 left-0 right-0 z-30 flex items-center justify-around border-t border-panel-border bg-rail pb-safe sm:hidden">
        {allNav.slice(0, 6).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={'end' in item ? (item.end as boolean) : false}
            onClick={() => setDrawerOpen(false)}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 px-3 py-2 text-[9px] font-medium ${
                isActive ? 'text-accent' : 'text-ink-muted'
              }`
            }
          >
            <Icon name={item.icon} className="text-[22px]" />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* ── Right column: topbar + content ── */}
      <div className="flex flex-1 flex-col min-w-0">

        {/* Topbar — 58px */}
        <header className="flex h-[58px] flex-none items-center gap-3 border-b border-panel-border bg-chrome px-5">

          {/* Breadcrumb / page title */}
          <div className="flex min-w-0 items-baseline gap-2">
            <span className="text-[16px] font-semibold text-ink-primary leading-none truncate">
              {breadcrumb}
            </span>
            {breadcrumb === 'Dashboard' && (
              <span className="hidden text-[12.5px] text-ink-faint sm:inline">
                · executive summary
              </span>
            )}
          </div>

          <div className="flex-1" />

          {/* Org switcher */}
          {user?.is_admin && customers.length > 0 ? (
            <div className="flex items-center gap-1.5 rounded-md border border-ctrl-border bg-ctrl-bg px-2.5 py-1.5">
              <Icon name="apartment" className="hidden text-[16px] text-ink-muted sm:inline" />
              <select
                value={viewAsCustomerId || user.customer_id}
                onChange={handleCustomerChange}
                className="cursor-pointer bg-transparent text-[12.5px] font-medium text-ink-primary focus:outline-none"
              >
                <option value={user.customer_id} className="text-black">
                  {user.name || user.customer_id} (My Org)
                </option>
                <option disabled className="text-gray-400">──────────────</option>
                {customers
                  .filter((c) => c.customer_id !== user.customer_id)
                  .map((c) => (
                    <option key={c.customer_id} value={c.customer_id} className="text-black">
                      {c.name || c.customer_id}
                    </option>
                  ))}
              </select>
              <Icon name="expand_more" className="text-[16px] text-ink-chevron" />
            </div>
          ) : (
            <div className="hidden items-center gap-1.5 rounded-md border border-ctrl-border bg-ctrl-bg px-2.5 py-1.5 sm:flex">
              <Icon name="apartment" className="text-[16px] text-ink-muted" />
              <span className="text-[12.5px] font-medium text-ink-primary">{activeCustomerName}</span>
              <Icon name="expand_more" className="text-[16px] text-ink-chevron" />
            </div>
          )}

          {/* Theme toggle */}
          <button
            onClick={toggleTheme}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            className="flex h-[30px] w-[30px] items-center justify-center rounded-md border border-ctrl-border bg-ctrl-bg text-ink-muted transition-colors hover:text-ink-primary"
          >
            <Icon name={theme === 'dark' ? 'light_mode' : 'dark_mode'} className="text-[16px]" />
          </button>

          {/* Create Ticket CTA */}
          <button
            onClick={() => setTicketOpen(true)}
            className="hidden items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-[12.5px] font-semibold text-white transition-[filter] hover:brightness-110 sm:flex"
          >
            <Icon name="confirmation_number" className="text-[15px]" />
            Create Ticket
          </button>

          {/* Avatar + user menu */}
          <div className="relative" ref={userMenuRef}>
            <button
              onClick={() => setUserMenuOpen((v) => !v)}
              className="flex h-[30px] w-[30px] items-center justify-center rounded-full bg-accent text-[12px] font-bold text-white"
              aria-label="Account menu"
            >
              {initials(user?.name || user?.email)}
            </button>
            {userMenuOpen && (
              <div className="absolute right-0 top-10 z-20 w-52 rounded-lg border border-panel-border bg-panel py-1.5 shadow-xl">
                <div className="truncate border-b border-panel-border px-3.5 py-2 text-[11.5px] text-ink-muted">
                  {user?.email}
                </div>
                <button
                  onClick={handleLogout}
                  className="flex w-full items-center gap-2 px-3.5 py-2 text-left text-[13px] font-medium text-ink-secondary hover:bg-white/[0.06] hover:text-ink-primary"
                >
                  <Icon name="logout" className="text-[16px]" />
                  Sign out
                </button>
              </div>
            )}
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-5 pb-16 sm:pb-5">
          <Outlet />
        </main>
      </div>

      {ticketOpen && (
        <CreateTicketModal
          defaultEmail={user?.email || ''}
          onClose={() => setTicketOpen(false)}
        />
      )}
    </div>
  )
}
