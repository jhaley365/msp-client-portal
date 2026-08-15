import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthContext } from './AuthContext'
import Logo from '../components/Logo'
import Icon from '../components/Icon'

export default function LoginPage() {
  const { user } = useAuthContext()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle')
  const [errorMsg, setErrorMsg] = useState('')

  if (user) { navigate('/', { replace: true }); return null }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setErrorMsg('')
    setStatus('sending')
    try {
      const res = await fetch('/api/auth/magic-link', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || 'Request failed')
      }
      setStatus('sent')
    } catch (err: any) {
      setErrorMsg(err.message || 'Something went wrong. Please try again.')
      setStatus('error')
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
          {status === 'sent' ? (
            <div className="flex flex-col items-center gap-3 py-4 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[rgba(74,222,128,0.12)]">
                <Icon name="mark_email_read" className="text-[28px] text-[#4ade80]" />
              </div>
              <p className="font-semibold text-ink-primary text-lg">Check your email</p>
              <p className="text-[13px] text-ink-muted leading-relaxed">
                We sent a login link to <span className="text-ink-secondary font-medium">{email}</span>.
                <br />It expires in 15 minutes.
              </p>
              <button
                onClick={() => setStatus('idle')}
                className="mt-2 text-[12px] text-accent/80 hover:text-accent"
              >
                Use a different email
              </button>
            </div>
          ) : (
            <>
              <p className="text-ink-muted text-sm text-center mb-6">
                Sign in to view your cloud resources
              </p>
              <form onSubmit={handleSubmit} className="space-y-5">
                <div>
                  <label className="block text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5">
                    Email address
                  </label>
                  <input
                    type="email"
                    required
                    autoFocus
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    className="w-full px-4 py-2.5 bg-white/[0.06] border border-white/[0.12] rounded-lg text-sm text-ink-primary placeholder:text-ink-faint focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent"
                    placeholder="you@company.com"
                  />
                </div>

                {status === 'error' && (
                  <div className="bg-[rgba(248,113,113,0.14)] border border-[rgba(248,113,113,0.3)] text-[#f87171] text-sm px-4 py-3 rounded-lg">
                    {errorMsg}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={status === 'sending'}
                  className="w-full flex items-center justify-center gap-2 bg-accent hover:brightness-110 disabled:opacity-60 text-white font-semibold py-2.5 rounded-lg transition-[filter] text-sm"
                >
                  {status === 'sending' ? (
                    <>
                      <Icon name="progress_activity" className="animate-spin text-[17px]" />
                      Sending link…
                    </>
                  ) : (
                    <>
                      <Icon name="send" className="text-[17px]" />
                      Send login link
                    </>
                  )}
                </button>

                <p className="text-center text-[11.5px] text-ink-faint">
                  We'll email you a secure link — no password needed.
                </p>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
