import { useEffect, useState } from 'react'
import api from '../lib/api'
import KpiCard from '../components/KpiCard'
import DataTable, { Column } from '../components/DataTable'
import Badge from '../components/Badge'

interface DnsSummary {
  allowed_requests: number
  blocked_requests: number
  threat_count: number
  online_clients: number
  offline_clients: number
  top_categories: { name: string; count: number }[]
  top_domains: { domain: string; count: number }[]
  period: string
  last_synced_at: string | null
}

interface Site {
  site_id: string
  name: string
  address: string
  last_synced_at: string
}

interface Client {
  client_id: string
  client_name: string
  os_name: string
  agent_status: string
  profile: string
  version: string
  last_sync_at: string
}

export default function DnsPage() {
  const [summary, setSummary] = useState<DnsSummary | null>(null)
  const [sites, setSites] = useState<Site[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.allSettled([
      api.get('/scoutdns/summary'),
      api.get('/scoutdns/sites'),
      api.get('/scoutdns/clients'),
    ]).then(([sum, sts, cls]) => {
      if (sum.status === 'fulfilled') setSummary(sum.value.data)
      if (sts.status === 'fulfilled') setSites(sts.value.data?.items ?? sts.value.data ?? [])
      if (cls.status === 'fulfilled') setClients(cls.value.data?.items ?? cls.value.data ?? [])
    }).finally(() => setLoading(false))
  }, [])

  const fmtDate = (val: string) => {
    if (!val) return '—'
    const d = new Date(val)
    return isNaN(d.getTime()) ? '—' : d.toLocaleDateString()
  }

  const totalRequests = (summary?.allowed_requests ?? 0) + (summary?.blocked_requests ?? 0)
  const blockRatePct = totalRequests > 0
    ? ((summary!.blocked_requests / totalRequests) * 100).toFixed(1) + '%'
    : '--'

  const siteColumns: Column<Site>[] = [
    { key: 'name', header: 'Site Name' },
    { key: 'address', header: 'Address' },
  ]

  const clientColumns: Column<Client>[] = [
    { key: 'client_name', header: 'Device' },
    { key: 'os_name', header: 'OS' },
    { key: 'agent_status', header: 'Status', render: (row) => <Badge state={row.agent_status} /> },
    { key: 'profile', header: 'Profile' },
    { key: 'version', header: 'Version' },
    { key: 'last_sync_at', header: 'Last Sync', render: (row) => fmtDate(row.last_sync_at) },
  ]

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-800">DNS — ScoutDNS</h1>
        {summary?.last_synced_at && (
          <span className="text-xs text-gray-400">
            Synced {fmtDate(summary.last_synced_at)} · {summary.period}
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <KpiCard label="Allowed Requests" value={summary?.allowed_requests?.toLocaleString() ?? '--'} accentColor="border-green-500" />
        <KpiCard label="Blocked Requests" value={summary?.blocked_requests?.toLocaleString() ?? '--'} accentColor="border-red-500" />
        <KpiCard label="Threats Detected" value={summary?.threat_count?.toLocaleString() ?? '--'} accentColor="border-orange-500" />
        <KpiCard label="Block Rate" value={summary ? blockRatePct : '--'} accentColor="border-purple-500" />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <KpiCard label="Online Clients" value={summary?.online_clients?.toLocaleString() ?? '--'} accentColor="border-blue-500" />
        <KpiCard label="Offline Clients" value={summary?.offline_clients?.toLocaleString() ?? '--'} accentColor="border-yellow-500" />
      </div>

      {/* Top categories and domains */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="section-card p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Top Blocked Categories</h2>
          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-6 bg-gray-200 rounded animate-pulse" />
              ))}
            </div>
          ) : (summary?.top_categories ?? []).length === 0 ? (
            <p className="text-sm text-gray-400">No category data available.</p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {(summary?.top_categories ?? []).map((c, i) => (
                <li key={i} className="flex items-center justify-between py-2 text-sm">
                  <span className="text-gray-700 truncate max-w-[60%]">{c.name}</span>
                  <span className="text-gray-500 tabular-nums">{Number(c.count).toLocaleString()}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="section-card p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Top Blocked Domains</h2>
          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-6 bg-gray-200 rounded animate-pulse" />
              ))}
            </div>
          ) : (summary?.top_domains ?? []).length === 0 ? (
            <p className="text-sm text-gray-400">No domain data available.</p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {(summary?.top_domains ?? []).map((d, i) => (
                <li key={i} className="flex items-center justify-between py-2 text-sm">
                  <span className="text-gray-700 font-mono text-xs truncate max-w-[60%]">{d.domain}</span>
                  <span className="text-gray-500 tabular-nums">{Number(d.count).toLocaleString()}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Sites */}
      <div className="section-card">
        <div className="p-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700">Network Sites</h2>
          <span className="text-xs text-gray-400">{sites.length} total</span>
        </div>
        <div className="overflow-y-auto" style={{ maxHeight: '20rem' }}>
          <DataTable<Site>
            columns={siteColumns}
            data={sites}
            loading={loading}
            emptyMessage="No sites found."
            keyField="site_id"
          />
        </div>
      </div>

      {/* Roaming clients */}
      <div className="section-card">
        <div className="p-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700">Roaming Clients</h2>
          <span className="text-xs text-gray-400">{clients.length} total</span>
        </div>
        <div className="overflow-y-auto" style={{ maxHeight: '32rem' }}>
          <DataTable<Client>
            columns={clientColumns}
            data={clients}
            loading={loading}
            emptyMessage="No roaming clients found."
            keyField="client_id"
          />
        </div>
      </div>
    </div>
  )
}
