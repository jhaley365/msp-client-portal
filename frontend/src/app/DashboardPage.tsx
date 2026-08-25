import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../lib/api'
import Icon from '../components/Icon'
import Badge from '../components/Badge'
import KpiStrip, { KpiCell } from '../components/KpiStrip'
import { toneForState, TONE_FG, Tone } from '../lib/tone'
import { firstName } from '../lib/user'
import { useAuthContext } from './AuthContext'

interface Summary { instances: number; volumes: number; snapshots: number }
interface SyncroSummary { total: number; open: number; closed: number; in_progress: number }
interface HuntressSummary { total_agents: number; online_agents: number; open_incidents: number; critical_incidents: number }
interface ScoutSummary { allowed_requests: number; blocked_requests: number; threat_count: number }
interface MonitoringSummary { hosts_up: number; hosts_down: number; hosts_unreachable: number; total_hosts: number }

interface Ticket { ticket_id: string; subject: string; status: string; priority: string; created_at: string }
interface Incident { incident_id: string; summary: string; severity: string; status: string }

const severityIcon = (tone: Tone) => (tone === 'purple' || tone === 'crit' ? 'gpp_maybe' : 'info')

function StatGrid({ stats }: { stats: { value: string | number; label: string; tone?: Tone }[] }) {
  return (
    <div
      className="grid gap-2 border-t border-divider pt-4"
      style={{ gridTemplateColumns: `repeat(${stats.length}, minmax(0, 1fr))` }}
    >
      {stats.map((s) => (
        <div key={s.label} className="text-center">
          <div
            className="font-mono text-[22px] font-medium tabular-nums"
            style={{ color: s.tone ? TONE_FG[s.tone] : 'var(--color-ink-primary)' }}
          >
            {s.value}
          </div>
          <div className="mt-1 text-[11px] text-ink-faint">{s.label}</div>
        </div>
      ))}
    </div>
  )
}

export default function DashboardPage() {
  const { user, activeCustomerName, viewAsCustomerId } = useAuthContext()
  const [aws, setAws] = useState<Summary | null>(null)
  const [syncro, setSyncro] = useState<SyncroSummary | null>(null)
  const [huntress, setHuntress] = useState<HuntressSummary | null>(null)
  const [scout, setScout] = useState<ScoutSummary | null>(null)
  const [monitoring, setMonitoring] = useState<MonitoringSummary | null>(null)
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [lastSync] = useState(new Date().toLocaleTimeString())

  const viewingOwnOrg = !viewAsCustomerId || viewAsCustomerId === user?.customer_id
  const useAdminEndpoints = !!user?.is_admin && viewingOwnOrg

  useEffect(() => {
    Promise.allSettled([
      api.get('/inventory/summary').then((r) => setAws(r.data)),
      api.get(useAdminEndpoints ? '/syncro/admin/summary' : '/syncro/summary').then((r) => setSyncro(r.data)),
      api.get('/huntress/summary').then((r) => setHuntress(r.data)),
      api.get('/scoutdns/summary').then((r) => setScout(r.data)),
      api.get('/syncro/tickets').then((r) => setTickets(r.data.items?.slice(0, 5) ?? [])),
      api.get('/huntress/incidents').then((r) => setIncidents(r.data.items?.slice(0, 5) ?? [])),
      api.get(useAdminEndpoints ? '/monitoring/admin/summary' : '/monitoring/summary').then((r) => setMonitoring(r.data)),
    ])
  }, [useAdminEndpoints])

  const fmt = (n: number | undefined) => (n !== undefined ? n.toLocaleString() : '—')

  const scoutTotal = (scout?.allowed_requests ?? 0) + (scout?.blocked_requests ?? 0)
  const scoutBlockRate = scout && scoutTotal > 0 ? ((scout.blocked_requests / scoutTotal) * 100).toFixed(1) : null

  const monitoringDown = monitoring ? monitoring.hosts_down + monitoring.hosts_unreachable : 0
  const monitoringTone = !monitoring ? 'muted' : monitoringDown > 0 ? 'crit' : 'ok'
  const monitoringValue = monitoring
    ? monitoringDown > 0
      ? `${monitoringDown} Down`
      : 'All Up'
    : '—'

  const kpiCells: KpiCell[] = [
    {
      label: 'EC2 Instances',
      value: fmt(aws?.instances),
      sub: 'Across all regions',
      icon: 'dns',
      tone: 'info',
    },
    {
      label: 'Open Tickets',
      value: fmt(syncro?.open),
      sub: syncro ? `${fmt(syncro.in_progress)} in progress` : 'Loading…',
      icon: 'confirmation_number',
      tone: 'warn',
    },
    {
      label: 'Security Incidents',
      value: fmt(huntress?.open_incidents),
      sub: 'Open · Huntress',
      icon: 'shield',
      tone: 'ok',
    },
    {
      label: 'DNS Blocks Today',
      value: typeof scout?.blocked_requests === 'number' ? fmt(scout.blocked_requests) : '—',
      sub: scoutBlockRate !== null ? `${scoutBlockRate}% block rate` : 'Awaiting data feed',
      icon: 'block',
      tone: typeof scout?.blocked_requests === 'number' ? 'info' : 'muted',
    },
    {
      label: 'Device Monitoring',
      value: monitoringValue,
      sub: monitoring ? `${monitoring.hosts_up} of ${monitoring.total_hosts} online` : 'Loading…',
      icon: 'monitor_heart',
      tone: monitoringTone,
    },
  ]

  return (
    <div className="flex flex-col gap-[14px]">
      {/* Page head */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="eyebrow mb-2">EXECUTIVE SUMMARY</div>
          <h1 className="text-[22px] font-semibold tracking-[-0.015em] text-ink-primary">
            Welcome back, {firstName(user?.name || user?.email) || 'there'}
          </h1>
        </div>
        <div className="font-mono text-[11.5px] text-ink-faint">
          {activeCustomerName} · Last synced {lastSync}
        </div>
      </div>

      {/* KPI strip — one divided container */}
      <KpiStrip cells={kpiCells} />

      {/* Service summary panels */}
      <div className="grid grid-cols-1 gap-[14px] md:grid-cols-3">

        {/* AWS Resources */}
        <div className="kpi-card !p-0">
          <div className="flex items-center justify-between px-[17px] pt-[15px] pb-[13px]">
            <div className="flex items-center gap-2">
              <Icon name="cloud" className="text-[17px]" style={{ color: TONE_FG.info }} />
              <span className="eyebrow">AWS RESOURCES</span>
            </div>
            <Link to="/aws" className="flex items-center gap-0.5 text-[11.5px] font-medium text-icon-blue no-underline hover:text-[#a5c8ff]">
              View <Icon name="arrow_forward" className="text-[14px]" />
            </Link>
          </div>
          <div className="px-[17px] pb-[17px]">
            <StatGrid stats={[
              { value: fmt(aws?.instances), label: 'Instances' },
              { value: fmt(aws?.volumes), label: 'Volumes' },
              { value: fmt(aws?.snapshots), label: 'Snapshots' },
            ]} />
          </div>
        </div>

        {/* Support Tickets */}
        <div className="kpi-card !p-0">
          <div className="flex items-center justify-between px-[17px] pt-[15px] pb-[13px]">
            <div className="flex items-center gap-2">
              <Icon name="confirmation_number" className="text-[17px]" style={{ color: TONE_FG.warn }} />
              <span className="eyebrow">SUPPORT TICKETS</span>
            </div>
            <Link to="/tickets" className="flex items-center gap-0.5 text-[11.5px] font-medium text-icon-blue no-underline hover:text-[#a5c8ff]">
              View <Icon name="arrow_forward" className="text-[14px]" />
            </Link>
          </div>
          <div className="px-[17px] pb-[17px]">
            <StatGrid stats={[
              { value: fmt(syncro?.open), label: 'Open', tone: 'warn' },
              { value: fmt(syncro?.in_progress), label: 'In Progress' },
              { value: fmt(syncro?.closed), label: 'Closed', tone: 'ok' },
            ]} />
          </div>
        </div>

        {/* Huntress Security */}
        <div className="kpi-card !p-0">
          <div className="flex items-center justify-between px-[17px] pt-[15px] pb-[13px]">
            <div className="flex items-center gap-2">
              <Icon name="shield" className="text-[17px]" style={{ color: TONE_FG.ok }} />
              <span className="eyebrow">HUNTRESS SECURITY</span>
            </div>
            <Link to="/security" className="flex items-center gap-0.5 text-[11.5px] font-medium text-icon-blue no-underline hover:text-[#a5c8ff]">
              View <Icon name="arrow_forward" className="text-[14px]" />
            </Link>
          </div>
          <div className="px-[17px] pb-[17px]">
            <StatGrid stats={[
              { value: fmt(huntress?.total_agents), label: 'Total Agents' },
              { value: fmt(huntress?.open_incidents), label: 'Open Incidents', tone: 'ok' },
              { value: fmt(huntress?.critical_incidents), label: 'Critical' },
            ]} />
          </div>
        </div>
      </div>

      {/* Two-column lists */}
      <div className="grid grid-cols-1 items-start gap-[14px] md:grid-cols-2">

        {/* Recent Tickets */}
        <div className="kpi-card !pb-2">
          <div className="mb-3 flex items-center justify-between">
            <span className="eyebrow">RECENT TICKETS</span>
            <Link to="/tickets" className="flex items-center gap-0.5 text-[11.5px] font-medium text-icon-blue no-underline hover:text-[#a5c8ff]">
              All tickets <Icon name="arrow_forward" className="text-[14px]" />
            </Link>
          </div>
          {tickets.length === 0 ? (
            <div className="py-6 text-center text-[12px] text-ink-muted">
              No ticket data — sync Syncro to populate
            </div>
          ) : (
            tickets.map((t, i) => (
              <div
                key={t.ticket_id}
                className={`flex items-center gap-3 py-3 ${i > 0 ? 'border-t border-row-hairline' : ''}`}
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[12.5px] text-ink-secondary">{t.subject}</div>
                  <div className="mt-0.5 font-mono text-[11px] text-ink-faint">
                    {t.created_at ? new Date(t.created_at).toLocaleDateString() : ''}
                  </div>
                </div>
                <Badge state={t.status} />
              </div>
            ))
          )}
        </div>

        {/* Recent Security Incidents */}
        <div className="kpi-card !pb-2">
          <div className="mb-3 flex items-center justify-between">
            <span className="eyebrow">RECENT SECURITY INCIDENTS</span>
            <Link to="/security" className="flex items-center gap-0.5 text-[11.5px] font-medium text-icon-blue no-underline hover:text-[#a5c8ff]">
              All incidents <Icon name="arrow_forward" className="text-[14px]" />
            </Link>
          </div>
          {incidents.length === 0 ? (
            <div className="py-6 text-center text-[12px] text-ink-muted">
              No incident data — sync Huntress to populate
            </div>
          ) : (
            incidents.map((inc, i) => {
              const tone = toneForState(inc.severity)
              return (
                <div
                  key={inc.incident_id}
                  className={`flex items-center gap-3 py-3 ${i > 0 ? 'border-t border-row-hairline' : ''}`}
                >
                  <span
                    className="flex h-[30px] w-[30px] flex-none items-center justify-center rounded-lg"
                    style={{ color: TONE_FG[tone], background: `${TONE_FG[tone]}20` }}
                  >
                    <Icon name={severityIcon(tone)} className="text-[17px]" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[12.5px] text-ink-secondary">{inc.summary}</div>
                    <div className="mt-0.5 font-mono text-[11px] text-ink-faint">{inc.status}</div>
                  </div>
                  <Badge state={inc.severity} />
                </div>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}
