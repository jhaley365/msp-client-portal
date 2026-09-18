import { useEffect, useRef } from 'react'
import Badge from './Badge'

interface TicketDetail {
  ticket_id?: string | number
  ticket_number: string | number
  subject: string
  status: string
  priority: string
  assigned_tech: string
  created_at: string
  updated_at: string
  customer_name?: string
  problem_type?: string
  body?: string
  comments?: Comment[]
}

interface Comment {
  id: string | number
  body: string
  created_at: string
  user?: string
  tech?: boolean
}

interface Props {
  ticket: TicketDetail | null
  onClose: () => void
}

function formatDate(s: string) {
  return new Date(s).toLocaleString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function TicketDetailModal({ ticket, onClose }: Props) {
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ticket) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [ticket, onClose])

  if (!ticket) return null

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 pt-16"
      style={{ background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(2px)' }}
      onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
    >
      <div
        className="relative w-full max-w-2xl rounded-lg border border-panel-border shadow-2xl"
        style={{ background: 'var(--color-panel)' }}
      >
        {/* Header */}
        <div className="flex items-start gap-3 border-b border-panel-border px-6 py-5">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-mono text-[11px] text-icon-blue">#{ticket.ticket_number}</span>
              {ticket.problem_type && (
                <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-mono px-1.5 py-0.5 rounded"
                  style={{ background: 'var(--color-ctrl-bg)' }}>
                  {ticket.problem_type}
                </span>
              )}
            </div>
            <h2 className="text-[15px] font-semibold text-ink-primary leading-snug">{ticket.subject}</h2>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 w-7 h-7 flex items-center justify-center rounded text-ink-muted hover:text-ink-primary hover:bg-white/10 transition-colors"
            aria-label="Close"
          >
            <span className="material-symbols-rounded text-[18px]">close</span>
          </button>
        </div>

        {/* Meta row */}
        <div className="grid grid-cols-2 gap-px border-b border-panel-border"
          style={{ background: 'var(--color-panel-border)' }}>
          {[
            { label: 'Status', value: <Badge state={ticket.status} /> },
            { label: 'Priority', value: ticket.priority || '—' },
            { label: 'Assigned Tech', value: ticket.assigned_tech || '—' },
            { label: 'Customer', value: ticket.customer_name || '—' },
            { label: 'Created', value: ticket.created_at ? formatDate(ticket.created_at) : '—' },
            { label: 'Updated', value: ticket.updated_at ? formatDate(ticket.updated_at) : '—' },
          ].map(({ label, value }) => (
            <div key={label} className="px-6 py-3" style={{ background: 'var(--color-panel)' }}>
              <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-mono mb-0.5">{label}</div>
              <div className="text-[12.5px] text-ink-secondary">{value}</div>
            </div>
          ))}
        </div>

        {/* Body */}
        {ticket.body && (
          <div className="px-6 py-5 border-b border-panel-border">
            <div className="eyebrow mb-2">Description</div>
            <p className="text-[12.5px] text-ink-secondary leading-relaxed whitespace-pre-wrap">{ticket.body}</p>
          </div>
        )}

        {/* Comments */}
        {ticket.comments && ticket.comments.length > 0 ? (
          <div className="px-6 py-5">
            <div className="eyebrow mb-3">Activity</div>
            <div className="flex flex-col gap-3">
              {ticket.comments.map((c) => (
                <div key={c.id} className="rounded border border-panel-border p-3"
                  style={{ background: 'var(--color-ctrl-bg)' }}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[11px] font-medium text-ink-primary">{c.user || (c.tech ? 'Technician' : 'Customer')}</span>
                    <span className="font-mono text-[10px] text-ink-mono">{formatDate(c.created_at)}</span>
                  </div>
                  <p className="text-[12px] text-ink-secondary leading-relaxed whitespace-pre-wrap">{c.body}</p>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="px-6 py-5">
            <div className="eyebrow mb-2">Activity</div>
            <p className="text-[12px] text-ink-muted">No comments on this ticket.</p>
          </div>
        )}
      </div>
    </div>
  )
}
