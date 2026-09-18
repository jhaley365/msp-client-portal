import { useEffect, useState } from 'react'
import api from '../lib/api'
import KpiCard from '../components/KpiCard'
import DataTable, { Column } from '../components/DataTable'
import Badge from '../components/Badge'

interface Agent {
  hostname: string
  platform: string
  os: string
  status: string
  defender_status: string
  last_seen_at: string
}

interface Incident {
  subject: string
  summary: string
  severity: string
  status: string
  type: string
  created_at: string
}

interface Summary {
  total_agents: number
  online_agents: number
  open_incidents: number
  critical_incidents: number
}

export default function SecurityPage() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.allSettled([
      api.get('/huntress/summary'),
      api.get('/huntress/agents'),
      api.get('/huntress/incidents'),
    ]).then(([sum, agts, incs]) => {
      if (sum.status === 'fulfilled') setSummary(sum.value.data)
      if (agts.status === 'fulfilled') {
        const items = agts.value.data?.items ?? agts.value.data ?? []
        setAgents([...items].sort((a: Agent, b: Agent) => a.hostname.localeCompare(b.hostname)))
      }
      if (incs.status === 'fulfilled') setIncidents(incs.value.data?.items ?? incs.value.data ?? [])
    }).finally(() => setLoading(false))
  }, [])

  const fmtDate = (val: string) => {
    if (!val) return '—'
    const d = new Date(val)
    return isNaN(d.getTime()) ? '—' : d.toLocaleDateString()
  }

  const agentColumns: Column<Agent>[] = [
    { key: 'hostname', header: 'Hostname' },
    { key: 'os', header: 'OS' },
    { key: 'status', header: 'Status', render: (row) => <Badge state={row.status} /> },
    { key: 'defender_status', header: 'Defender' },
    { key: 'last_seen_at', header: 'Last Seen', render: (row) => fmtDate(row.last_seen_at) },
  ]

  const incidentColumns: Column<Incident>[] = [
    { key: 'subject', header: 'Summary', render: (row) => row.subject || row.summary || '—',
      className: 'max-w-xs whitespace-normal break-words' },
    { key: 'severity', header: 'Severity', render: (row) => <Badge state={row.severity} /> },
    { key: 'status', header: 'Status', render: (row) => <Badge state={row.status} /> },
    { key: 'type', header: 'Type' },
    { key: 'created_at', header: 'Created', render: (row) => fmtDate(row.created_at) },
  ]

  return (
    <div className="space-y-5">
      <h1 className="font-sans text-xl font-bold text-ink-primary">Security — Huntress</h1>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <KpiCard label="Total Agents" value={summary?.total_agents ?? '--'} icon="shield" tone="muted" />
        <KpiCard label="Online Agents" value={summary?.online_agents ?? '--'} icon="shield" tone="ok" />
        <KpiCard label="Open Incidents" value={summary?.open_incidents ?? '--'} icon="gpp_maybe" tone="warn" />
        <KpiCard label="Critical Incidents" value={summary?.critical_incidents ?? '--'} icon="gpp_maybe" tone="crit" />
      </div>

      <div className="space-y-4">
        <div className="section-card">
          <div className="p-4 border-b border-white/[0.07] flex items-center justify-between">
            <h2 className="font-sans text-sm font-semibold text-white">Incidents</h2>
            <span className="text-xs text-ink-muted">{incidents.length} total</span>
          </div>
          <div className="overflow-y-auto" style={{ maxHeight: '32rem' }}>
            <DataTable<Incident>
              columns={incidentColumns}
              data={incidents}
              loading={loading}
              emptyMessage="No incidents found."
            />
          </div>
        </div>

        <div className="section-card">
          <div className="p-4 border-b border-white/[0.07] flex items-center justify-between">
            <h2 className="font-sans text-sm font-semibold text-white">Agents</h2>
            <span className="text-xs text-ink-muted">{agents.length} total</span>
          </div>
          <div className="overflow-y-auto" style={{ maxHeight: '32rem' }}>
            <DataTable<Agent>
              columns={agentColumns}
              data={agents}
              loading={loading}
              emptyMessage="No agents found."
            />
          </div>
        </div>
      </div>
    </div>
  )
}
