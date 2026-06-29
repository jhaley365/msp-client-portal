import { useEffect, useState } from 'react'
import api from '../lib/api'
import KpiCard from '../components/KpiCard'
import DataTable, { Column } from '../components/DataTable'
import Badge from '../components/Badge'

interface Agent {
  hostname: string
  platform: string
  status: string
  policy: string
  last_seen: string
}

interface Incident {
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
      if (agts.status === 'fulfilled') setAgents(agts.value.data?.items ?? agts.value.data ?? [])
      if (incs.status === 'fulfilled') setIncidents(incs.value.data?.items ?? incs.value.data ?? [])
    }).finally(() => setLoading(false))
  }, [])

  const agentColumns: Column<Agent>[] = [
    { key: 'hostname', header: 'Hostname' },
    { key: 'platform', header: 'Platform' },
    { key: 'status', header: 'Status', render: (row) => <Badge state={row.status} /> },
    { key: 'policy', header: 'Policy' },
    { key: 'last_seen', header: 'Last Seen', render: (row) => new Date(row.last_seen).toLocaleDateString() },
  ]

  const incidentColumns: Column<Incident>[] = [
    { key: 'summary', header: 'Summary' },
    { key: 'severity', header: 'Severity', render: (row) => <Badge state={row.severity} /> },
    { key: 'status', header: 'Status', render: (row) => <Badge state={row.status} /> },
    { key: 'type', header: 'Type' },
    { key: 'created_at', header: 'Created', render: (row) => new Date(row.created_at).toLocaleDateString() },
  ]

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-gray-800">Security — Huntress</h1>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <KpiCard label="Total Agents" value={summary?.total_agents ?? '--'} accentColor="border-gray-400" />
        <KpiCard label="Online Agents" value={summary?.online_agents ?? '--'} accentColor="border-green-500" />
        <KpiCard label="Open Incidents" value={summary?.open_incidents ?? '--'} accentColor="border-orange-500" />
        <KpiCard label="Critical Incidents" value={summary?.critical_incidents ?? '--'} accentColor="border-red-500" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="section-card">
          <div className="p-4 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-700">Agents</h2>
          </div>
          <DataTable<Agent>
            columns={agentColumns}
            data={agents}
            loading={loading}
            emptyMessage="No agents found."
          />
        </div>

        <div className="section-card">
          <div className="p-4 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-700">Incidents</h2>
          </div>
          <DataTable<Incident>
            columns={incidentColumns}
            data={incidents}
            loading={loading}
            emptyMessage="No incidents found."
          />
        </div>
      </div>
    </div>
  )
}
