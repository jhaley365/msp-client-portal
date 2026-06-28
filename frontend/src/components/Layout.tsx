import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuthContext } from '../app/AuthContext'

const NAV = [
  { to: '/',         label: 'Dashboard',  end: true },
  { to: '/aws',      label: 'AWS' },
  { to: '/tickets',  label: 'Tickets' },
  { to: '/security', label: 'Security' },
  { to: '/dns',      label: 'DNS' },
  { to: '/o365',     label: 'Office 365' },
]

export default function Layout() {
  const { user, logout } = useAuthContext()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)

  const handleLogout = () => { logout(); navigate('/login', { replace: true }) }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top header */}
      <header style={{ backgroundColor: '#1e3a5f' }} className="text-white shadow-md flex-shrink-0">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          <span className="text-base font-bold tracking-tight">MSP Client Portal</span>
          <div className="flex items-center gap-3">
            <span className="hidden sm:block text-sm text-blue-200">{user?.name || user?.email}</span>
            <button
              onClick={handleLogout}
              className="text-xs bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded-lg transition-colors"
            >
              Sign out
            </button>
            <button
              className="sm:hidden p-1"
              onClick={() => setMenuOpen(!menuOpen)}
              aria-label="Toggle menu"
            >
              <div className="space-y-1">
                <span className={`block w-5 h-0.5 bg-white transition-all ${menuOpen ? 'rotate-45 translate-y-1.5' : ''}`} />
                <span className={`block w-5 h-0.5 bg-white transition-all ${menuOpen ? 'opacity-0' : ''}`} />
                <span className={`block w-5 h-0.5 bg-white transition-all ${menuOpen ? '-rotate-45 -translate-y-1.5' : ''}`} />
              </div>
            </button>
          </div>
        </div>
      </header>

      {/* Tab nav — desktop */}
      <nav className="bg-white border-b border-gray-200 flex-shrink-0 hidden sm:block">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex gap-0 overflow-x-auto">
          {NAV.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `tab-btn ${isActive ? 'tab-btn-active' : 'tab-btn-inactive'}`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </div>
      </nav>

      {/* Mobile menu */}
      {menuOpen && (
        <nav className="sm:hidden bg-white border-b border-gray-200 px-4 py-2 flex flex-col gap-1">
          {NAV.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) =>
                `px-3 py-2 rounded-lg text-sm font-medium ${isActive ? 'bg-blue-50 text-blue-600' : 'text-gray-600 hover:bg-gray-50'}`
              }
            >
              {item.label}
            </NavLink>
          ))}
          <div className="pt-2 border-t border-gray-100 text-xs text-gray-400 px-3 pb-1">
            {user?.name || user?.email}
          </div>
        </nav>
      )}

      {/* Page content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Outlet />
      </main>

      <footer className="text-center text-xs text-gray-400 py-3 border-t border-gray-200">
        MSP Client Portal · {new Date().getFullYear()}
      </footer>
    </div>
  )
}
