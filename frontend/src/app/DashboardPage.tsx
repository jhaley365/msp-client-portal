import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../lib/api'
import KpiCard from '../components/KpiCard'
import MiniBarChart from '../components/MiniBarChart'
import Badge from '../components/Badge'
import { useAuthContext } from './AuthContext'

interface Summary { instances: number; volumes: number; snapshots: number }
interface SyncroSummary { total: number; open: number; closed: number; in_progress: number }
interface HuntressSummary { total_agents: number; online_agents: number; open_incidents: number; critical_incidents: number }
interface ScoutSummary { total_queries: number; blocked_queries: number; block_rate: number }

interface Ticket { ticket_id: string; subject: string; status: string; priority: string; created_at: string }
interface Incident { incident_id: string; summary: string; severity: string; status: string }

export default function DashboardPage() {
  const { user } = useAuthContext()
  const [aws, setAws] = useState<Summary | null>(null)
  const [syncro, setSyncro] = useState<SyncroSummary | null>(null)
  const [huntress, setHuntress] = useState<HuntressSummary | null>(null)
  const [scout, setScout] = useState<ScoutSummary | null>(null)
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [lastSync] = useState(new Date().toLocaleTimeString())

  useEffect(() => {
    Promise.allSettled([
      api.get('/inventory/summary').then(r => setAws(r.data)),
      api.get('/syncro/summary').then(r => setSyncro(r.data)),
      api.get('/huntress/summary').then(r => setHuntress(r.data)),
      api.get('/scoutdns/summary').then(r => setScout(r.data)),
      api.get('/syncro/tickets?last_key=').then(r => setTickets(r.data.items?.slice(0, 5) ?? [])),
      api.get('/huntress/incidents').then(r => setIncidents(r.data.items?.slice(0, 5) ?? [])),
    ])
  }, [])

  const fmt = (n: number | undefined) => n !== undefined ? n.toLocaleString() : '—'

  return (
    <div className="space-y-6">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-800">Executive Summary</h1>
          <p className="text-xs text-gray-400 mt-0.5">Welcome, {user?.name || user?.email} · Last synced: {lastSync}</p>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard label="EC2 Instances"      value={fmt(aws?.instances)}          icon="🖥️" accentColor="border-blue-500" />
        <KpiCard label="Open Tickets"        value={fmt(syncro?.open)}            icon="🎫" accentColor="border-orange-400" />
        <KpiCard label="Security Incidents"  value={fmt(huntress?.open_incidents)} icon="🛡️" accentColor="border-red-500" />
        <KpiCard label="DNS Blocks Today"    value={fmt(scout?.blocked_queries)}  icon="🔒" accentColor="border-purple-500" />
      </div>

      {/* Chart cards row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* AWS */}
        <div className="section-card p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-700">AWS Resources</h2>
            <Link to="/aws" className="text-xs text-blue-600 hover:underline">View →</Link>
          </div>
          <MiniBarChart
            data={[
              { label: 'Instances', value: aws?.instances ?? 0 },
              { label: 'Volumes', value: aws?.volumes ?? 0 },
              { label: 'Snapshots', value: aws?.snapshots ?? 0 },
            ]}
            color="#0078d4"
          />
          <div className="grid grid-cols-3 gap-2 mt-3 pt-3 border-t border-gray-100 text-center">
            {[['Instances', aws?.instances], ['Volumes', aws?.volumes], ['Snapshots', aws?.snapshots]].map(([l, v]) => (
              <div key={l as string}>
                <p className="text-lg font-bold text-gray-800">{fmt(v as number)}</p>
                <p className="text-xs text-gray-400">{l as string}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Tickets */}
        <div className="section-card p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-700">Support Tickets</h2>
            <Link to="/tickets" className="text-xs text-blue-600 hover:underline">View →</Link>
          </div>
          <MiniBarChart
            data={[
              { label: 'Open', value: syncro?.open ?? 0 },
              { label: 'In Progress', value: syncro?.in_progress ?? 0 },
              { label: 'Closed', value: syncro?.closed ?? 0 },
            ]}
            color="#f59e0b"
          />
          <div className="grid grid-cols-3 gap-2 mt-3 pt-3 border-t border-gray-100 text-center">
            {[['Open', syncro?.open], ['In Progress', syncro?.in_progress], ['Closed', syncro?.closed]].map(([l, v]) => (
              <div key={l as string}>
                <p className="text-lg font-bold text-gray-800">{fmt(v as number)}</p>
                <p className="text-xs text-gray-400">{l as string}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Security */}
        <div className="section-card p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-700">Security</h2>
            <Link to="/security" className="text-xs text-blue-600 hover:underline">View →</Link>
          </div>
          <MiniBarChart
            data={[
              { label: 'Agents', value: huntress?.total_agents ?? 0 },
              { label: 'Online', value: huntress?.online_agents ?? 0 },
              { label: 'Incidents', value: huntress?.open_incidents ?? 0 },
              { label: 'Critical', value: huntress?.critical_incidents ?? 0 },
            ]}
            color="#ef4444"
          />
          <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-gray-100 text-center">
            {[['Total Agents', huntress?.total_agents], ['Open Incidents', huntress?.open_incidents]].map(([l, v]) => (
              <div key={l as string}>
                <p className="text-lg font-bold text-gray-800">{fmt(v as number)}</p>
                <p className="text-xs text-gray-400">{l as string}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom detail tables */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Recent tickets */}
        <div className="section-card">
          <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-700">Recent Tickets</h2>
            <Link to="/tickets" className="text-xs text-blue-600 hover:underline">All tickets →</Link>
          </div>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-gray-50">
              {tickets.length === 0 ? (
                <tr><td className="px-5 py-6 text-center text-gray-400 text-xs">No ticket data — sync Syncro to populate</td></tr>
              ) : tickets.map(t => (
                <tr key={t.ticket_id} className="hover:bg-gray-50">
                  <td className="px-5 py-3">
                    <p className="font-medium text-gray-800 truncate max-w-[200px]">{t.subject}</p>
                    <p className="text-xs text-gray-400">{t.created_at ? new Date(t.created_at).toLocaleDateString() : ''}</p>
                  </td>
                  <td className="px-5 py-3 text-right"><Badge state={t.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Recent incidents */}
        <div className="section-card">
          <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-700">Recent Security Incidents</h2>
            <Link to="/security" className="text-xs text-blue-600 hover:underline">All incidents →</Link>
          </div>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-gray-50">
              {incidents.length === 0 ? (
                <tr><td className="px-5 py-6 text-center text-gray-400 text-xs">No incident data — sync Huntress to populate</td></tr>
              ) : incidents.map(inc => (
                <tr key={inc.incident_id} className="hover:bg-gray-50">
                  <td className="px-5 py-3">
                    <p className="font-medium text-gray-800 truncate max-w-[200px]">{inc.summary}</p>
                    <p className="text-xs text-gray-400">{inc.status}</p>
                  </td>
                  <td className="px-5 py-3 text-right"><Badge state={inc.severity} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
