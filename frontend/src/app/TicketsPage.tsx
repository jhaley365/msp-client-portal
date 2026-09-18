import { useEffect, useState } from 'react'
import api from '../lib/api'
import KpiStrip, { KpiCell } from '../components/KpiStrip'
import DataTable, { Column } from '../components/DataTable'
import Badge from '../components/Badge'

type StatusFilter =
  | 'all' | 'open' | 'New' | 'In Progress' | 'Waiting on Customer'
  | 'Waiting for Parts' | 'Scheduled' | 'Customer Reply'
  | 'Escalated to MSP' | 'Abandoned' | 'Resolved'

interface Ticket {
  ticket_number: string | number
  subject: string
  status: string
  priority: string
  assigned_tech: string
  created_at: string
  updated_at: string
}

interface Summary { total: number; open: number }

export default function TicketsPage() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('open')
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
      setTickets((prev) => (append ? [...prev, ...data.items] : data.items))
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
    { label: 'Open', value: 'open' },
    { label: 'New', value: 'New' },
    { label: 'In Progress', value: 'In Progress' },
    { label: 'Waiting on Customer', value: 'Waiting on Customer' },
    { label: 'Waiting for Parts', value: 'Waiting for Parts' },
    { label: 'Scheduled', value: 'Scheduled' },
    { label: 'Customer Reply', value: 'Customer Reply' },
    { label: 'Escalated to MSP', value: 'Escalated to MSP' },
    { label: 'Abandoned', value: 'Abandoned' },
    { label: 'Resolved', value: 'Resolved' },
    { label: 'All', value: 'all' },
  ]

  const kpiCells: KpiCell[] = [
    { label: 'Total Tickets', value: summary?.total ?? '—', icon: 'confirmation_number', tone: 'info' },
    { label: 'Open Tickets',  value: summary?.open  ?? '—', icon: 'mark_email_unread',   tone: 'warn' },
    { label: 'Avg Response Time', value: '—', icon: 'schedule', tone: 'muted' },
  ]

  const columns: Column<Ticket>[] = [
    {
      key: 'created_at',
      header: 'Created',
      mono: true,
      render: (row) => new Date(row.created_at).toLocaleDateString(),
    },
    {
      key: 'updated_at',
      header: 'Updated',
      mono: true,
      render: (row) => new Date(row.updated_at).toLocaleDateString(),
    },
    {
      key: 'ticket_number',
      header: 'Ticket #',
      accent: true,
      render: (row) => `#${row.ticket_number}`,
    },
    {
      key: 'subject',
      header: 'Subject',
      className: 'max-w-xs whitespace-normal break-words',
    },
    {
      key: 'status',
      header: 'Status',
      render: (row) => <Badge state={row.status} />,
    },
    { key: 'priority', header: 'Priority' },
    { key: 'assigned_tech', header: 'Assigned Tech' },
  ]

  return (
    <div className="flex flex-col gap-[14px]">
      {/* Page title — "Support Tickets" is provided via breadcrumb in the topbar;
          this secondary label mirrors the spec's "Tickets · Support Tickets" format */}
      <div className="eyebrow">Support Tickets</div>

      {/* Status tab strip */}
      <div className="flex flex-wrap gap-0 border-b border-panel-border">
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

      {/* 3-cell KPI strip */}
      <KpiStrip cells={kpiCells} />

      {/* Ticket table */}
      <div className="section-card">
        <DataTable<Ticket>
          columns={columns}
          data={tickets}
          loading={loading}
          emptyMessage="No tickets found."
          hasMore={hasMore}
          onLoadMore={() => loadTickets(true)}
          keyField="ticket_number"
        />
      </div>
    </div>
  )
}
