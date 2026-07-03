import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthContext } from './AuthContext'
import Logo from '../components/Logo'

export default function LoginPage() {
  const { login, user } = useAuthContext()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (user) { navigate('/', { replace: true }); return null }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/', { replace: true })
    } catch {
      setError('Invalid email or password. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4 bg-page"
      style={{
        background:
          'radial-gradient(680px 420px at 50% -8%, rgba(59,130,246,0.28), transparent 70%), #0c111e',
      }}
    >
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-8">
          <Logo />
        </div>
        <div className="bg-panel border border-[rgba(96,165,250,0.16)] rounded-2xl shadow-2xl p-8">
          <p className="text-ink-muted text-sm text-center mb-6">Sign in to view your cloud resources</p>
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5">
                Email address
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="w-full px-4 py-2.5 bg-white/[0.06] border border-white/[0.12] rounded-lg text-sm text-white placeholder:text-ink-faint focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent"
                placeholder="you@company.com"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5">
                Password
              </label>
              <input
                type="password"
                required
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full px-4 py-2.5 bg-white/[0.06] border border-white/[0.12] rounded-lg text-sm text-white placeholder:text-ink-faint focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent"
                placeholder="••••••••"
              />
            </div>
            {error && (
              <div className="bg-[rgba(248,113,113,0.14)] border border-[rgba(248,113,113,0.3)] text-[#f87171] text-sm px-4 py-3 rounded-lg">
                {error}
              </div>
            )}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-accent hover:brightness-110 disabled:opacity-60 text-white font-semibold py-2.5 rounded-lg transition-[filter] text-sm"
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
