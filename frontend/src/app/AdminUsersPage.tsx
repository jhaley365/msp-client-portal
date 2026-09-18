import { useEffect, useState } from 'react'
import { useAuthContext } from './AuthContext'
import Icon from '../components/Icon'

interface Customer { customer_id: string; name: string }
interface User {
  user_id: string
  email: string
  name: string
  customer_id: string
  is_admin: boolean
  is_active: boolean
  created_at: string
}

function authHeader() {
  return { Authorization: `Bearer ${localStorage.getItem('token')}`, 'Content-Type': 'application/json' }
}

export default function AdminUsersPage() {
  const { user: me } = useAuthContext()
  const [users, setUsers] = useState<User[]>([])
  const [customers, setCustomers] = useState<Customer[]>([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState({ email: '', name: '', customer_id: '', is_admin: false })
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  const load = () => {
    setLoading(true)
    Promise.all([
      fetch('/api/admin/users', { headers: authHeader() }).then(r => r.json()),
      fetch('/api/admin/customers', { headers: authHeader() }).then(r => r.json()),
    ]).then(([u, c]) => {
      setUsers(u)
      setCustomers(c)
    }).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.customer_id) { setFormError('Please select a customer.'); return }
    setSaving(true)
    setFormError('')
    try {
      const res = await fetch('/api/admin/users', {
        method: 'POST',
        headers: authHeader(),
        body: JSON.stringify(form),
      })
      if (!res.ok) {
        const d = await res.json().catch(() => ({}))
        throw new Error(d.detail || 'Failed to create user')
      }
      setModalOpen(false)
      setForm({ email: '', name: '', customer_id: '', is_admin: false })
      load()
    } catch (err: any) {
      setFormError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const toggleActive = async (u: User) => {
    await fetch(`/api/admin/users/${u.user_id}`, {
      method: 'PATCH',
      headers: authHeader(),
      body: JSON.stringify({ is_active: !u.is_active }),
    })
    load()
  }

  const sendMagicLink = async (email: string) => {
    await fetch('/api/auth/magic-link', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    })
    alert(`Login link sent to ${email}`)
  }

  const customerName = (cid: string) =>
    customers.find(c => c.customer_id === cid)?.name || cid

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-mono text-[11px] tracking-[0.2em] text-accent mb-1">ADMIN</p>
          <h1 className="font-sans text-2xl font-extrabold text-ink-primary">Users</h1>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-[13px] font-semibold text-white transition-[filter] hover:brightness-110"
        >
          <Icon name="person_add" className="text-[16px]" />
          Add user
        </button>
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
                <th className="px-4 py-3">Name / Email</th>
                <th className="px-4 py-3">Customer</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.user_id} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                  <td className="px-4 py-3">
                    <div className="font-medium text-ink-primary">{u.name || '—'}</div>
                    <div className="text-ink-muted text-[12px]">{u.email}</div>
                  </td>
                  <td className="px-4 py-3 text-ink-secondary">{customerName(u.customer_id)}</td>
                  <td className="px-4 py-3">
                    {u.is_admin ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-[rgba(124,176,255,0.14)] px-2.5 py-0.5 text-[11.5px] font-semibold text-[#7cb0ff]">Admin</span>
                    ) : (
                      <span className="text-ink-muted">User</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {u.is_active ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-[rgba(74,222,128,0.12)] px-2.5 py-0.5 text-[11.5px] font-semibold text-[#4ade80]">Active</span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full bg-[rgba(154,166,184,0.12)] px-2.5 py-0.5 text-[11.5px] font-semibold text-[#9aa6b8]">Inactive</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      {u.is_active && (
                        <button
                          onClick={() => sendMagicLink(u.email)}
                          className="flex items-center gap-1 rounded-lg border border-white/[0.10] bg-white/[0.04] px-2.5 py-1.5 text-[12px] text-ink-secondary hover:text-white"
                          title="Send login link"
                        >
                          <Icon name="send" className="text-[14px]" />
                          Send link
                        </button>
                      )}
                      {u.user_id !== me?.customer_id && (
                        <button
                          onClick={() => toggleActive(u)}
                          className="flex items-center gap-1 rounded-lg border border-white/[0.10] bg-white/[0.04] px-2.5 py-1.5 text-[12px] text-ink-secondary hover:text-white"
                        >
                          {u.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-ink-muted text-sm">
                    No users yet. Add one to get started.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Add user modal */}
      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={e => { if (e.target === e.currentTarget) setModalOpen(false) }}
        >
          <div className="relative w-full max-w-md rounded-2xl border border-white/[0.12] bg-panel p-8 shadow-2xl">
            <button
              onClick={() => setModalOpen(false)}
              className="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.12] bg-white/[0.06] text-ink-muted hover:text-white"
            >
              <Icon name="close" className="text-[18px]" />
            </button>

            <div className="mb-1 font-mono text-[11px] tracking-[0.2em] text-accent">NEW USER</div>
            <h2 className="mb-6 font-sans text-[20px] font-extrabold text-ink-primary">Add user</h2>

            <form onSubmit={handleCreate} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-medium text-ink-secondary">Email address</label>
                <input
                  type="email"
                  required
                  value={form.email}
                  onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                  className="rounded-lg border border-white/[0.12] bg-white/[0.04] px-3.5 py-2.5 text-[13px] text-ink-primary placeholder-ink-faint focus:border-accent/60 focus:outline-none focus:ring-1 focus:ring-accent/40"
                  placeholder="user@company.com"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-medium text-ink-secondary">Full name</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  className="rounded-lg border border-white/[0.12] bg-white/[0.04] px-3.5 py-2.5 text-[13px] text-ink-primary placeholder-ink-faint focus:border-accent/60 focus:outline-none focus:ring-1 focus:ring-accent/40"
                  placeholder="Jane Smith"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-medium text-ink-secondary">Customer</label>
                <select
                  required
                  value={form.customer_id}
                  onChange={e => setForm(f => ({ ...f, customer_id: e.target.value }))}
                  className="rounded-lg border border-white/[0.12] bg-[#0e1424] px-3.5 py-2.5 text-[13px] text-ink-primary focus:border-accent/60 focus:outline-none focus:ring-1 focus:ring-accent/40"
                >
                  <option value="">Select a customer…</option>
                  {customers.map(c => (
                    <option key={c.customer_id} value={c.customer_id}>
                      {c.name || c.customer_id}
                    </option>
                  ))}
                </select>
              </div>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.is_admin}
                  onChange={e => setForm(f => ({ ...f, is_admin: e.target.checked }))}
                  className="h-4 w-4 rounded accent-accent"
                />
                <span className="text-[13px] text-ink-secondary">Admin access (can view all customers)</span>
              </label>

              {formError && (
                <p className="text-[12px] text-[#f87171]">{formError}</p>
              )}

              <button
                type="submit"
                disabled={saving}
                className="mt-1 flex items-center justify-center gap-2 rounded-lg bg-accent py-3 text-[13px] font-semibold text-white transition-[filter] hover:brightness-110 disabled:opacity-60"
              >
                {saving ? (
                  <><Icon name="progress_activity" className="animate-spin text-[17px]" />Creating…</>
                ) : (
                  <><Icon name="person_add" className="text-[17px]" />Create user</>
                )}
              </button>

              <p className="text-center text-[11.5px] text-ink-faint">
                A login link will be sent when the user first signs in.
              </p>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
