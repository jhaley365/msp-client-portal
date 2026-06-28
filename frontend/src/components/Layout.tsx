import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuthContext } from '../app/AuthContext'

const navItems = [
  { to: '/',          label: 'Dashboard',  icon: '🏠', end: true },
  { to: '/instances', label: 'Instances',  icon: '🖥️' },
  { to: '/volumes',   label: 'Volumes',    icon: '💾' },
  { to: '/snapshots', label: 'Snapshots',  icon: '📸' },
]

export default function Layout() {
  const { user, logout } = useAuthContext()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
      isActive
        ? 'bg-brand-700 text-white'
        : 'text-brand-100 hover:bg-brand-700 hover:text-white'
    }`

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top nav */}
      <header className="bg-brand-900 text-white shadow-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <span className="text-lg font-bold tracking-tight">MSP Client Portal</span>

            {/* Desktop nav */}
            <nav className="hidden md:flex items-center gap-1">
              {navItems.map((item) => (
                <NavLink key={item.to} to={item.to} end={item.end} className={linkClass}>
                  <span>{item.icon}</span>
                  {item.label}
                </NavLink>
              ))}
            </nav>

            {/* User + logout */}
            <div className="hidden md:flex items-center gap-3">
              <span className="text-sm text-brand-100">{user?.name || user?.email}</span>
              <button
                onClick={handleLogout}
                className="text-sm bg-brand-700 hover:bg-brand-600 px-3 py-1.5 rounded-lg transition-colors"
              >
                Sign out
              </button>
            </div>

            {/* Mobile hamburger */}
            <button
              className="md:hidden p-2 rounded-lg hover:bg-brand-700 transition-colors"
              onClick={() => setMenuOpen(!menuOpen)}
              aria-label="Toggle menu"
            >
              <div className="space-y-1">
                <span className={`block w-6 h-0.5 bg-white transition-transform ${menuOpen ? 'rotate-45 translate-y-1.5' : ''}`} />
                <span className={`block w-6 h-0.5 bg-white transition-opacity ${menuOpen ? 'opacity-0' : ''}`} />
                <span className={`block w-6 h-0.5 bg-white transition-transform ${menuOpen ? '-rotate-45 -translate-y-1.5' : ''}`} />
              </div>
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {menuOpen && (
          <div className="md:hidden border-t border-brand-700 px-4 py-3 space-y-1">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={linkClass}
                onClick={() => setMenuOpen(false)}
              >
                <span>{item.icon}</span>
                {item.label}
              </NavLink>
            ))}
            <div className="pt-2 border-t border-brand-700 flex items-center justify-between">
              <span className="text-sm text-brand-100">{user?.name || user?.email}</span>
              <button
                onClick={handleLogout}
                className="text-sm bg-brand-700 hover:bg-brand-600 px-3 py-1.5 rounded-lg"
              >
                Sign out
              </button>
            </div>
          </div>
        )}
      </header>

      {/* Page content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>

      <footer className="text-center text-xs text-gray-400 py-4">
        MSP Client Portal · {new Date().getFullYear()}
      </footer>
    </div>
  )
}
