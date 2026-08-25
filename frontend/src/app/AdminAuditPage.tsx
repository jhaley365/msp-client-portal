import { useEffect, useState } from 'react'
import Icon from '../components/Icon'

interface LoginRecord {
  login_id: string
  email: string
  name: string
  customer_id: string
  ip_address: string
  logged_in_at: string
}

function authHeader() {
  return { Authorization: `Bearer ${localStorage.getItem('token')}` }
}

function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

export default function AdminAuditPage() {
  const [records, setRecords] = useState<LoginRecord[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/admin/login-audit', { headers: authHeader() })
      .then(r => r.json())
      .then(setRecords)
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-[11px] tracking-[0.2em] text-accent mb-1">ADMIN</p>
        <h1 className="font-sans text-2xl font-extrabold text-ink-primary">Login Audit</h1>
        <p className="mt-1 text-[13px] text-ink-muted">{records.length} login{records.length !== 1 ? 's' : ''} recorded</p>
      </div>

      <div className="rounded-xl border border-white/[0.07] bg-panel overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center gap-2 py-16 text-ink-muted text-sm">
            <Icon name="progress_activity" className="animate-spin text-[20px]" />
            Loading…
          </div>
        ) : (
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-white/[0.07] text-left text-[11px] font-semibold uppercase tracking-wider text-ink-muted">
                <th className="px-4 py-3">Date / Time</th>
                <th className="px-4 py-3">User</th>
                <th className="px-4 py-3">Customer</th>
                <th className="px-4 py-3">IP Address</th>
              </tr>
            </thead>
            <tbody>
              {records.map(r => (
                <tr key={r.login_id} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                  <td className="px-4 py-3 font-mono text-[12px] text-ink-secondary whitespace-nowrap">
                    {fmtDate(r.logged_in_at)}
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-ink-primary">{r.name || '—'}</div>
                    <div className="text-ink-muted text-[12px]">{r.email}</div>
                  </td>
                  <td className="px-4 py-3 text-ink-secondary">{r.customer_id}</td>
                  <td className="px-4 py-3 font-mono text-[12px] text-ink-muted">{r.ip_address}</td>
                </tr>
              ))}
              {records.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-12 text-center text-ink-muted text-sm">
                    No login records yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
