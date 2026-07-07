import { useEffect, useState } from 'react'
import api from '../lib/api'
import KpiCard from '../components/KpiCard'
import DataTable, { Column } from '../components/DataTable'
import Badge from '../components/Badge'

interface Summary {
  titan_total: number
  titan_in_use: number
  maestro_total: number
  maestro_in_use: number
  pa_total: number
  pa_in_use: number
  dt_total: number
  dt_in_use: number
}

interface Instance {
  name: string
  public_ip: string
  local_ip: string
  logged_on: string
  status: string
  processing: boolean
  domain_joined: boolean
  azure_ad: boolean
  instance_id: string
  create_date: string
}

export default function AppsPage() {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [instances, setInstances] = useState<Instance[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.allSettled([
      api.get('/apps/summary'),
      api.get('/apps/instances'),
    ]).then(([sum, inst]) => {
      if (sum.status === 'fulfilled') setSummary(sum.value.data)
      if (inst.status === 'fulfilled') setInstances(inst.value.data?.items ?? [])
    }).finally(() => setLoading(false))
  }, [])

  const columns: Column<Instance>[] = [
    { key: 'name', header: 'VM' },
    { key: 'logged_on', header: 'Logged On', render: (row) => (
      <div className="truncate" style={{ width: '120px', maxWidth: '120px', overflow: 'hidden' }} title={row.logged_on}>
        {row.logged_on}
      </div>
    ) },
    { key: 'public_ip', header: 'Public IP', className: 'font-mono text-xs' },
    { key: 'local_ip', header: 'Local IP', className: 'font-mono text-xs' },
    { key: 'status', header: 'Status', render: (row) => (
      <Badge state={row.status === 'In Use' ? 'active' : 'online'} />
    ) },
    { key: 'processing', header: 'Processing', render: (row) => (
      row.processing ? <Badge state="active" /> : <span className="text-xs text-gray-400">—</span>
    ) },
    { key: 'domain_joined', header: 'AD', render: (row) => (
      row.domain_joined ? <span className="text-xs font-semibold text-green-600">YES</span> : <span className="text-xs text-gray-400">NO</span>
    ) },
    { key: 'azure_ad', header: 'AAD', render: (row) => (
      row.azure_ad ? <span className="text-xs font-semibold text-green-600">YES</span> : <span className="text-xs text-gray-400">NO</span>
    ) },
    { key: 'instance_id', header: 'Instance ID', className: 'font-mono text-xs' },
  ]

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-gray-800">Apps</h1>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <KpiCard label="Maestro" value={summary ? `${summary.maestro_in_use} Sessions` : '--'} sub={`${summary?.maestro_total ?? '--'} total`} icon="desktop_windows" tone="warn" />
        <KpiCard label="Titan" value={summary ? `${summary.titan_in_use} Sessions` : '--'} sub={`${summary?.titan_total ?? '--'} total`} icon="dns" tone="info" />
        <KpiCard label="PA Sessions" value={summary ? `${summary.pa_in_use} Sessions` : '--'} sub={`${summary?.pa_total ?? '--'} total`} icon="devices" tone="ok" />
        <KpiCard label="DT Sessions" value={summary ? `${summary.dt_in_use} Sessions` : '--'} sub={`${summary?.dt_total ?? '--'} total`} icon="computer" tone="muted" />
      </div>

      <div className="section-card">
        <div className="p-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700">Instances</h2>
          <span className="text-xs text-gray-400">{instances.length} total</span>
        </div>
        <div className="overflow-y-auto" style={{ maxHeight: '36rem' }}>
          <DataTable<Instance>
            columns={columns}
            data={instances}
            loading={loading}
            emptyMessage="No instance data available."
            keyField="instance_id"
          />
        </div>
      </div>
    </div>
  )
}
