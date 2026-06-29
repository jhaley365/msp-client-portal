import { useEffect, useState } from 'react'
import api from '../lib/api'
import KpiCard from '../components/KpiCard'
import DataTable, { Column } from '../components/DataTable'

interface DnsSummary {
  total_queries: number
  blocked_queries: number
  block_rate: number
}

interface DnsStat {
  date: string
  total_queries: number
  blocked: number
  allowed: number
  block_rate: number
}

interface BlockedDomain {
  domain: string
  count: number
}

export default function DnsPage() {
  const [summary, setSummary] = useState<DnsSummary | null>(null)
  const [stats, setStats] = useState<DnsStat[]>([])
  const [topDomains, setTopDomains] = useState<BlockedDomain[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.allSettled([
      api.get('/scoutdns/summary'),
      api.get('/scoutdns/stats'),
      api.get('/scoutdns/top-blocked'),
    ]).then(([sum, st, top]) => {
      if (sum.status === 'fulfilled') setSummary(sum.value.data)
      if (st.status === 'fulfilled') setStats(st.value.data?.items ?? st.value.data ?? [])
      if (top.status === 'fulfilled') setTopDomains(top.value.data?.items ?? top.value.data ?? [])
    }).finally(() => setLoading(false))
  }, [])

  const statColumns: Column<DnsStat>[] = [
    { key: 'date', header: 'Date' },
    { key: 'total_queries', header: 'Total' },
    { key: 'blocked', header: 'Blocked' },
    { key: 'allowed', header: 'Allowed' },
    { key: 'block_rate', header: 'Block Rate', render: (row) => `${row.block_rate}%` },
  ]

  const sortedStats = [...stats].sort((a, b) =>
    new Date(b.date).getTime() - new Date(a.date).getTime()
  )

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-gray-800">DNS — ScoutDNS</h1>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <KpiCard label="Total Queries" value={summary?.total_queries ?? '--'} accentColor="border-blue-500" />
        <KpiCard label="Blocked Queries" value={summary?.blocked_queries ?? '--'} accentColor="border-red-500" />
        <KpiCard
          label="Block Rate"
          value={summary?.block_rate != null ? `${summary.block_rate}%` : '--'}
          accentColor="border-orange-500"
        />
      </div>

      <div className="section-card">
        <div className="p-4 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-700">Query History</h2>
        </div>
        <DataTable<DnsStat>
          columns={statColumns}
          data={sortedStats}
          loading={loading}
          emptyMessage="No query history available."
        />
      </div>

      <div className="section-card p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Top Blocked Domains</h2>
        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-6 bg-gray-200 rounded animate-pulse" />
            ))}
          </div>
        ) : topDomains.length === 0 ? (
          <p className="text-sm text-gray-400">No blocked domain data available.</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {topDomains.map((d, i) => (
              <li key={i} className="flex items-center justify-between py-2 text-sm">
                <span className="text-gray-700 font-mono">{d.domain}</span>
                <span className="text-gray-500">{d.count.toLocaleString()} blocks</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
