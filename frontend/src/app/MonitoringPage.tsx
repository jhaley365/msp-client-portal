import { useEffect, useState } from 'react'
import api from '../lib/api'
import KpiCard from '../components/KpiCard'
import DataTable, { Column } from '../components/DataTable'
import Badge from '../components/Badge'
import { useAuthContext } from './AuthContext'

interface MonitoringSummary {
  hosts_up: number
  hosts_down: number
  hosts_unreachable: number
  hosts_pending: number
  services_warn: number
  services_crit: number
  services_unknown: number
  total_hosts: number
  total_services: number
}

interface Host {
  host_name: string
  alias: string
  ip_address: string
  status: string
  groups: string[]
  customer_id: string
  last_synced_at: string
}

interface ServiceProblem {
  service_key: string
  host_name: string
  service_description: string
  status: string
  plugin_output: string
}


const HOST_COLUMNS: Column<Host>[] = [
  {
    key: 'host_name',
    header: 'Name',
    render: (h) => (
      <div>
        <div className="text-[13px] text-ink-primary">{h.alias || h.host_name}</div>
        {h.alias && h.alias !== h.host_name && (
          <div className="font-mono text-[11px] text-ink-muted">{h.host_name}</div>
        )}
      </div>
    ),
  },
  {
    key: 'ip_address',
    header: 'IP',
    render: (h) => (
      <span className="font-mono text-[13px] text-ink-secondary">{h.ip_address || '—'}</span>
    ),
  },
  {
    key: 'status',
    header: 'Status',
    render: (h) => <Badge state={h.status} />,
  },
  {
    key: 'customer_id',
    header: 'Customer',
    render: (h) => (
      <span className="text-[13px] text-ink-secondary">{h.customer_id || '—'}</span>
    ),
  },
]

const PROBLEM_COLUMNS: Column<ServiceProblem>[] = [
  {
    key: 'host_name',
    header: 'Host',
    render: (s) => (
      <span className="text-[13px] text-ink-primary">{s.host_name}</span>
    ),
  },
  {
    key: 'service_description',
    header: 'Service',
    render: (s) => (
      <span className="text-[13px] text-ink-primary">{s.service_description}</span>
    ),
  },
  {
    key: 'status',
    header: 'Status',
    render: (s) => <Badge state={s.status} />,
  },
  {
    key: 'plugin_output',
    header: 'Output',
    render: (s) => (
      <span className="text-[13px] text-ink-secondary">{s.plugin_output || '—'}</span>
    ),
  },
]

export default function MonitoringPage() {
  const { user } = useAuthContext()
  const isAdmin = !!user?.is_admin
  const [summary, setSummary] = useState<MonitoringSummary | null>(null)
  const [hosts, setHosts] = useState<Host[]>([])
  const [problems, setProblems] = useState<ServiceProblem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const prefix = isAdmin ? '/monitoring/admin' : '/monitoring'
    Promise.allSettled([
      api.get(`${prefix}/summary`),
      api.get(`${prefix}/hosts`),
      api.get(`${prefix}/problems`),
    ]).then(([sum, hst, prb]) => {
      if (sum.status === 'fulfilled') setSummary(sum.value.data)
      if (hst.status === 'fulfilled') {
        const items: Host[] = hst.value.data?.items ?? []
        if (!isAdmin) items.sort((a, b) => (a.alias || a.host_name).toLowerCase().localeCompare((b.alias || b.host_name).toLowerCase()))
        setHosts(items)
      }
      if (prb.status === 'fulfilled') setProblems(prb.value.data?.items ?? [])
    }).finally(() => setLoading(false))
  }, [isAdmin])

  const s = summary

  return (
    <div className="space-y-6">
      <h1 className="font-display text-xl font-bold text-ink-primary">Monitoring</h1>

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <KpiCard
          label="Hosts Up"
          value={s ? String(s.hosts_up) : '—'}
          icon="check_circle"
          tone="ok"
        />
        <KpiCard
          label="Hosts Down"
          value={s ? String(s.hosts_down) : '—'}
          icon="cancel"
          tone={s && s.hosts_down > 0 ? 'crit' : 'muted'}
        />
        <KpiCard
          label="Warnings"
          value={s ? String(s.services_warn) : '—'}
          icon="warning"
          tone={s && s.services_warn > 0 ? 'warn' : 'muted'}
        />
        <KpiCard
          label="Criticals"
          value={s ? String(s.services_crit) : '—'}
          icon="error"
          tone={s && s.services_crit > 0 ? 'crit' : 'muted'}
        />
      </div>

      {/* Hosts table */}
      <div className="section-card">
        <h2 className="mb-4 font-display text-[15px] font-semibold text-ink-primary">
          Hosts
          {s ? (
            <span className="ml-2 font-mono text-[13px] font-normal text-ink-muted">
              ({s.total_hosts})
            </span>
          ) : null}
        </h2>
        <DataTable<Host>
          columns={HOST_COLUMNS}
          data={hosts}
          keyField="host_name"
          loading={loading}
          emptyMessage="No hosts found."
        />
      </div>

      {/* Problems table */}
      <div className="section-card">
        <h2 className="mb-4 font-display text-[15px] font-semibold text-ink-primary">
          Problems
          {problems.length > 0 ? (
            <span className="ml-2 font-mono text-[13px] font-normal text-tone-crit">
              ({problems.length})
            </span>
          ) : null}
        </h2>
        <DataTable<ServiceProblem>
          columns={PROBLEM_COLUMNS}
          data={problems}
          keyField="service_key"
          loading={loading}
          emptyMessage="No problems — all services OK."
        />
      </div>
    </div>
  )
}
