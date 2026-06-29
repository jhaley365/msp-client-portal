import { useEffect, useState } from 'react'
import api from '../lib/api'
import KpiCard from '../components/KpiCard'
import DataTable, { Column } from '../components/DataTable'
import Badge from '../components/Badge'

type StatusFilter = 'all' | 'New' | 'In Progress' | 'Customer Reply' | 'Waiting On Customer' | 'Resolved'

interface Ticket {
  ticket_number: string | number
  subject: string
  status: string
  priority: string
  assigned_tech: string
  created_at: string
  updated_at: string
}

interface Summary {
  total: number
  open: number
}

export default function TicketsPage() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [loading, setLoading] = useState(false)
  const [lastKey, setLastKey] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [summary, setSummary] = useState<Summary | null>(null)

  const loadTickets = async (append = false) => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (statusFilter !== 'all') params.status = statusFilter
      if (append && lastKey) params.last_key = lastKey
      const { data } = await api.get('/syncro/tickets', { params })
      setTickets((prev) => append ? [...prev, ...data.items] : data.items)
      setLastKey(data.next_key ?? null)
      setHasMore(!!data.next_key)
    } catch {
      if (!append) setTickets([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setSummary(null)
    api.get('/syncro/summary').then(({ data }) => setSummary(data)).catch(() => {})
    loadTickets()
  }, [statusFilter])

  const filters: { label: string; value: StatusFilter }[] = [
    { label: 'All', value: 'all' },
    { label: 'New', value: 'New' },
    { label: 'In Progress', value: 'In Progress' },
    { label: 'Customer Reply', value: 'Customer Reply' },
    { label: 'Waiting On Customer', value: 'Waiting On Customer' },
    { label: 'Resolved', value: 'Resolved' },
  ]

  const columns: Column<Ticket>[] = [
    { key: 'created_at', header: 'Created', render: (row) => new Date(row.created_at).toLocaleDateString() },
    { key: 'updated_at', header: 'Updated', render: (row) => new Date(row.updated_at).toLocaleDateString() },
    { key: 'ticket_number', header: 'Ticket #', render: (row) => `#${row.ticket_number}` },
    { key: 'subject', header: 'Subject', className: 'max-w-xs whitespace-normal break-words' },
    { key: 'status', header: 'Status', render: (row) => <Badge state={row.status} /> },
    { key: 'priority', header: 'Priority' },
    { key: 'assigned_tech', header: 'Assigned Tech' },
  ]

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-gray-800">Support Tickets</h1>

      <div className="flex gap-2 flex-wrap">
        {filters.map((f) => (
          <button
            key={f.value}
            onClick={() => setStatusFilter(f.value)}
            className={`tab-btn ${statusFilter === f.value ? 'active' : ''}`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <KpiCard label="Total Tickets" value={summary?.total ?? '--'} />
        <KpiCard label="Open Tickets" value={summary?.open ?? '--'} accentColor="border-orange-500" />
        <KpiCard label="Avg Response Time" value="--" accentColor="border-gray-400" />
      </div>

      <div className="section-card">
        <DataTable<Ticket>
          columns={columns}
          data={tickets}
          loading={loading}
          emptyMessage="No tickets found."
          hasMore={hasMore}
          onLoadMore={() => loadTickets(true)}
        />
      </div>
    </div>
  )
}
