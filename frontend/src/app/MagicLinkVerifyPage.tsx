import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import Logo from '../components/Logo'
import Icon from '../components/Icon'

export default function MagicLinkVerifyPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [status, setStatus] = useState<'verifying' | 'error'>('verifying')
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    const token = params.get('token')
    if (!token) {
      setErrorMsg('No login token found. Please request a new link.')
      setStatus('error')
      return
    }

    fetch('/api/auth/magic-link/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    })
      .then(async res => {
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.detail || 'Invalid or expired link.')
        }
        return res.json()
      })
      .then(data => {
        localStorage.setItem('token', data.access_token)
        // Store user object so AuthContext initialises correctly on reload
        localStorage.setItem('user', JSON.stringify({
          customer_id: data.customer_id,
          name: data.name,
          email: data.email || '',
          is_admin: data.is_admin ?? false,
        }))
        window.location.replace('/')
      })
      .catch(err => {
        setErrorMsg(err.message || 'Something went wrong.')
        setStatus('error')
      })
  }, [params])

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4"
      style={{
        background:
          'radial-gradient(680px 420px at 50% -8%, rgba(59,130,246,0.28), transparent 70%), #0c111e',
      }}
    >
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-8">
          <Logo />
        </div>
        <div className="bg-panel border border-[rgba(96,165,250,0.16)] rounded-2xl shadow-2xl p-8 text-center">
          {status === 'verifying' ? (
            <div className="flex flex-col items-center gap-3 py-4">
              <Icon name="progress_activity" className="animate-spin text-[32px] text-accent" />
              <p className="text-ink-secondary text-sm">Signing you in…</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3 py-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[rgba(248,113,113,0.14)]">
                <Icon name="error" className="text-[28px] text-[#f87171]" />
              </div>
              <p className="font-semibold text-white">Link expired or invalid</p>
              <p className="text-[13px] text-ink-muted">{errorMsg}</p>
              <button
                onClick={() => navigate('/login', { replace: true })}
                className="mt-2 rounded-lg bg-accent px-5 py-2 text-[13px] font-semibold text-white transition-[filter] hover:brightness-110"
              >
                Request a new link
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
