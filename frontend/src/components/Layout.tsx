import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuthContext } from '../app/AuthContext'
import { initials } from '../lib/user'
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
]

export default function Layout() {
  const { user, logout, viewAsCustomerId, setViewAsCustomerId, customers, activeCustomerName } = useAuthContext()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [ticketOpen, setTicketOpen] = useState(false)
  const userMenuRef = useRef<HTMLDivElement>(null)

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
    // Reload the current page so all data refreshes for the new customer.
    window.location.reload()
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-page text-ink-primary">
      {/* Header */}
      <header className="flex h-[60px] flex-none items-center gap-2 border-b border-white/[0.07] bg-chrome px-3 sm:gap-4 sm:px-6">
        <Logo />
        <div className="flex-1" />

        {user?.is_admin && customers.length > 0 ? (
          <div className="flex max-w-[110px] items-center gap-2 rounded-lg border border-white/[0.12] bg-white/[0.06] px-2 py-1.5 sm:max-w-[240px] sm:px-3">
            <Icon name="apartment" className="hidden text-[17px] text-ink-muted sm:inline" />
            <select
              value={viewAsCustomerId || user.customer_id}
              onChange={handleCustomerChange}
              className="w-full min-w-0 cursor-pointer truncate bg-transparent text-[13px] font-semibold text-ink-primary focus:outline-none"
            >
              <option value={user.customer_id} className="text-black">
                {user.name || user.customer_id} (My Org)
              </option>
              <option disabled className="text-gray-400">
                ──────────────
              </option>
              {customers
                .filter((c) => c.customer_id !== user.customer_id)
                .map((c) => (
                  <option key={c.customer_id} value={c.customer_id} className="text-black">
                    {c.name || c.customer_id}
                  </option>
                ))}
            </select>
          </div>
        ) : (
          <div className="hidden items-center gap-2 rounded-lg border border-white/[0.12] bg-white/[0.06] px-3 py-1.5 text-[13px] font-semibold text-ink-secondary sm:flex">
            <Icon name="apartment" className="text-[17px] text-ink-muted" />
            {activeCustomerName}
          </div>
        )}

        <button
          onClick={() => setTicketOpen(true)}
          className="hidden items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-[13px] font-semibold text-white transition-[filter] hover:brightness-110 sm:flex"
        >
          <Icon name="confirmation_number" className="text-[16px]" />
          Create Ticket
        </button>

        <div className="relative" ref={userMenuRef}>
          <button
            onClick={() => setUserMenuOpen((v) => !v)}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-[13px] font-bold text-white"
            aria-label="Account menu"
          >
            {initials(user?.name || user?.email)}
          </button>
          {userMenuOpen && (
            <div className="absolute right-0 top-11 z-20 w-56 rounded-lg border border-white/[0.12] bg-panel py-1.5 shadow-xl">
              <div className="truncate border-b border-white/[0.07] px-3.5 py-2 text-xs text-ink-muted">
                {user?.email}
              </div>
              <button
                onClick={handleLogout}
                className="flex w-full items-center gap-2 px-3.5 py-2 text-left text-sm font-medium text-ink-secondary hover:bg-white/[0.06] hover:text-white"
              >
                <Icon name="logout" className="text-[17px]" />
                Sign out
              </button>
            </div>
          )}
        </div>

        <button
          className="p-1 sm:hidden"
          onClick={() => setMenuOpen((v) => !v)}
          aria-label="Toggle menu"
        >
          <div className="space-y-1">
            <span className={`block h-0.5 w-5 bg-white transition-all ${menuOpen ? 'translate-y-1.5 rotate-45' : ''}`} />
            <span className={`block h-0.5 w-5 bg-white transition-all ${menuOpen ? 'opacity-0' : ''}`} />
            <span className={`block h-0.5 w-5 bg-white transition-all ${menuOpen ? '-translate-y-1.5 -rotate-45' : ''}`} />
          </div>
        </button>
      </header>

      {/* Tab nav — desktop */}
      <nav className="hidden h-12 flex-none items-stretch gap-0.5 border-b border-white/[0.07] bg-chrome px-4 sm:flex sm:px-6">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `-mb-px flex items-center gap-2 border-b-2 px-3.5 text-[13.5px] transition-colors ${
                isActive
                  ? 'border-accent font-bold text-white'
                  : 'border-transparent font-medium text-ink-muted hover:text-white'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <Icon name={item.icon} className={`text-[18px] ${isActive ? 'text-accent' : 'text-ink-faint'}`} />
                {item.label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Mobile menu */}
      {menuOpen && (
        <nav className="flex flex-col gap-1 border-b border-white/[0.07] bg-chrome px-4 py-2 sm:hidden">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${
                  isActive ? 'bg-accent/[0.15] text-white' : 'text-ink-secondary hover:bg-white/[0.06]'
                }`
              }
            >
              <Icon name={item.icon} className="text-[18px]" />
              {item.label}
            </NavLink>
          ))}
          <div className="border-t border-white/[0.07] px-3 pb-1 pt-2 text-xs text-ink-muted">
            {activeCustomerName}
          </div>
        </nav>
      )}

      {/* Page content */}
      <main className="flex-1 overflow-y-auto p-6">
        <Outlet />
      </main>

      {ticketOpen && (
        <CreateTicketModal
          defaultEmail={user?.email || ''}
          onClose={() => setTicketOpen(false)}
        />
      )}
    </div>
  )
}
