import { useEffect, useRef, useState } from 'react'
import Icon from './Icon'

interface Props {
  defaultEmail: string
  onClose: () => void
}

export default function CreateTicketModal({ defaultEmail, onClose }: Props) {
  const [email, setEmail] = useState(defaultEmail)
  const [message, setMessage] = useState('')
  const [status, setStatus] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle')
  const overlayRef = useRef<HTMLDivElement>(null)

  // close on Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!message.trim()) return
    setStatus('sending')
    try {
      const res = await fetch('/api/support/ticket', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('token')}` },
        body: JSON.stringify({ email, message }),
      })
      if (!res.ok) throw new Error('send failed')
      setStatus('sent')
    } catch {
      setStatus('error')
    }
  }

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
    >
      <div className="relative w-full max-w-md rounded-2xl border border-white/[0.12] bg-panel p-8 shadow-2xl">
        {/* close button */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.12] bg-white/[0.06] text-ink-muted transition-colors hover:text-white"
        >
          <Icon name="close" className="text-[18px]" />
        </button>

        <div className="mb-1 font-mono text-[11px] tracking-[0.2em] text-accent">CREATE TICKET</div>
        <h2 className="mb-1 font-display text-[22px] font-extrabold text-white">Submit a support request</h2>
        <p className="mb-6 text-[13px] text-ink-muted">
          We'll respond to your message within one business day.
        </p>

        {status === 'sent' ? (
          <div className="flex flex-col items-center gap-3 py-6 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-tone-ok/[0.15]">
              <Icon name="check_circle" className="text-[28px] text-tone-ok" />
            </div>
            <p className="font-semibold text-white">Request sent!</p>
            <p className="text-[13px] text-ink-muted">We'll be in touch at {email}.</p>
            <button
              onClick={onClose}
              className="mt-2 rounded-lg bg-accent px-5 py-2 text-[13px] font-semibold text-white transition-[filter] hover:brightness-110"
            >
              Close
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-[12px] font-medium text-ink-secondary">Email address</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="rounded-lg border border-white/[0.12] bg-white/[0.04] px-3.5 py-2.5 text-[13px] text-ink-primary placeholder-ink-faint focus:border-accent/60 focus:outline-none focus:ring-1 focus:ring-accent/40"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[12px] font-medium text-ink-secondary">Message</label>
              <textarea
                required
                rows={5}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Describe the issue or question..."
                className="resize-none rounded-lg border border-white/[0.12] bg-white/[0.04] px-3.5 py-2.5 text-[13px] text-ink-primary placeholder-ink-faint focus:border-accent/60 focus:outline-none focus:ring-1 focus:ring-accent/40"
              />
            </div>

            {status === 'error' && (
              <p className="text-[12px] text-tone-crit">Failed to send — please try again or email support@haley365.com directly.</p>
            )}

            <button
              type="submit"
              disabled={status === 'sending'}
              className="mt-1 flex items-center justify-center gap-2 rounded-lg bg-accent py-3 text-[13px] font-semibold text-white transition-[filter] hover:brightness-110 disabled:opacity-60"
            >
              {status === 'sending' ? (
                <>
                  <Icon name="progress_activity" className="animate-spin text-[17px]" />
                  Sending…
                </>
              ) : (
                <>
                  <Icon name="send" className="text-[17px]" />
                  Send request
                </>
              )}
            </button>

            <p className="text-center text-[11.5px] text-ink-faint">
              Or email us directly at{' '}
              <a href="mailto:support@haley365.com" className="text-accent/80 hover:text-accent">
                support@haley365.com
              </a>
            </p>
          </form>
        )}
      </div>
    </div>
  )
}
