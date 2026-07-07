import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../lib/api'
import Icon from '../components/Icon'
import Badge from '../components/Badge'
import KpiCard from '../components/KpiCard'
import { toneForState, TONE_FG, Tone } from '../lib/tone'
import { firstName } from '../lib/user'
import { useAuthContext } from './AuthContext'

interface Summary { instances: number; volumes: number; snapshots: number }
interface SyncroSummary { total: number; open: number; closed: number; in_progress: number }
interface HuntressSummary { total_agents: number; online_agents: number; open_incidents: number; critical_incidents: number }
interface ScoutSummary { allowed_requests: number; blocked_requests: number; threat_count: number }

interface Ticket { ticket_id: string; subject: string; status: string; priority: string; created_at: string }
interface Incident { incident_id: string; summary: string; severity: string; status: string }

const severityIcon = (tone: Tone) => (tone === 'purple' || tone === 'crit' ? 'gpp_maybe' : 'info')

function StatGrid({ stats }: { stats: { value: string | number; label: string; tone?: Tone }[] }) {
  return (
    <div
      className="grid gap-2 border-t border-white/[0.07] pt-4"
      style={{ gridTemplateColumns: `repeat(${stats.length}, minmax(0, 1fr))` }}
    >
      {stats.map((s) => (
        <div key={s.label} className="text-center">
          <div
            className="font-mono text-[22px] font-semibold tabular-nums"
            style={{ color: s.tone ? TONE_FG[s.tone] : '#fff' }}
          >
            {s.value}
          </div>
          <div className="mt-1 text-[11.5px] text-ink-muted">{s.label}</div>
        </div>
      ))}
    </div>
  )
}

export default function DashboardPage() {
  const { user, activeCustomerName } = useAuthContext()
  const [aws, setAws] = useState<Summary | null>(null)
  const [syncro, setSyncro] = useState<SyncroSummary | null>(null)
  const [huntress, setHuntress] = useState<HuntressSummary | null>(null)
  const [scout, setScout] = useState<ScoutSummary | null>(null)
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [lastSync] = useState(new Date().toLocaleTimeString())

  useEffect(() => {
    Promise.allSettled([
      api.get('/inventory/summary').then((r) => setAws(r.data)),
      api.get('/syncro/summary').then((r) => setSyncro(r.data)),
      api.get('/huntress/summary').then((r) => setHuntress(r.data)),
      api.get('/scoutdns/summary').then((r) => setScout(r.data)),
      api.get('/syncro/tickets').then((r) => setTickets(r.data.items?.slice(0, 5) ?? [])),
      api.get('/huntress/incidents').then((r) => setIncidents(r.data.items?.slice(0, 5) ?? [])),
    ])
  }, [])

  const fmt = (n: number | undefined) => (n !== undefined ? n.toLocaleString() : '—')

  const scoutTotal = (scout?.allowed_requests ?? 0) + (scout?.blocked_requests ?? 0)
  const scoutBlockRate = scout && scoutTotal > 0 ? ((scout.blocked_requests / scoutTotal) * 100).toFixed(1) : null

  return (
    <div className="flex flex-col gap-4.5">
      {/* Page head */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="mb-2 font-mono text-[11.5px] tracking-[0.2em] text-brand-light">
            EXECUTIVE SUMMARY
          </div>
          <h1 className="font-display text-[26px] font-extrabold tracking-[-0.01em] text-white">
            Welcome back, {firstName(user?.name || user?.email) || 'there'}
          </h1>
          <div className="mt-1.5 text-[13px] text-ink-muted">
            {activeCustomerName} · Last synced {lastSync}
          </div>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <KpiCard
          label="EC2 Instances"
          value={fmt(aws?.instances)}
          sub="Across all regions"
          icon="dns"
          tone="info"
        />
        <KpiCard
          label="Open Tickets"
          value={fmt(syncro?.open)}
          sub={syncro ? `${fmt(syncro.in_progress)} in progress` : 'Loading…'}
          icon="confirmation_number"
          tone="warn"
        />
        <KpiCard
          label="Security Incidents"
          value={fmt(huntress?.open_incidents)}
          sub="Open · Huntress"
          icon="shield"
          tone="ok"
        />
        <KpiCard
          label="DNS Blocks Today"
          value={typeof scout?.blocked_requests === 'number' ? fmt(scout.blocked_requests) : '—'}
          sub={scoutBlockRate !== null ? `${scoutBlockRate}% block rate` : 'Awaiting data feed'}
          icon="block"
          tone={typeof scout?.blocked_requests === 'number' ? 'info' : 'muted'}
        />
      </div>

      {/* Service summary cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="kpi-card !p-0">
          <div className="flex items-center justify-between px-5 pt-4.5 pb-4">
            <div className="flex items-center gap-2.5">
              <span
                className="flex h-[30px] w-[30px] items-center justify-center rounded-lg"
                style={{ color: TONE_FG.info, background: `${TONE_FG.info}22` }}
              >
                <Icon name="cloud" className="text-[18px]" />
              </span>
              <span className="font-display text-[15px] font-bold text-white">AWS Resources</span>
            </div>
            <Link to="/aws" className="flex items-center gap-1 text-[12.5px] font-semibold text-icon-blue no-underline">
              View <Icon name="arrow_forward" className="text-[15px]" />
            </Link>
          </div>
          <div className="px-5 pb-5">
            <StatGrid
              stats={[
                { value: fmt(aws?.instances), label: 'Instances' },
                { value: fmt(aws?.volumes), label: 'Volumes' },
                { value: fmt(aws?.snapshots), label: 'Snapshots' },
              ]}
            />
          </div>
        </div>

        <div className="kpi-card !p-0">
          <div className="flex items-center justify-between px-5 pt-4.5 pb-4">
            <div className="flex items-center gap-2.5">
              <span
                className="flex h-[30px] w-[30px] items-center justify-center rounded-lg"
                style={{ color: TONE_FG.warn, background: `${TONE_FG.warn}22` }}
              >
                <Icon name="confirmation_number" className="text-[18px]" />
              </span>
              <span className="font-display text-[15px] font-bold text-white">Support Tickets</span>
            </div>
            <Link to="/tickets" className="flex items-center gap-1 text-[12.5px] font-semibold text-icon-blue no-underline">
              View <Icon name="arrow_forward" className="text-[15px]" />
            </Link>
          </div>
          <div className="px-5 pb-5">
            <StatGrid
              stats={[
                { value: fmt(syncro?.open), label: 'Open', tone: 'warn' },
                { value: fmt(syncro?.in_progress), label: 'In Progress' },
                { value: fmt(syncro?.closed), label: 'Closed', tone: 'ok' },
              ]}
            />
          </div>
        </div>

        <div className="kpi-card !p-0">
          <div className="flex items-center justify-between px-5 pt-4.5 pb-4">
            <div className="flex items-center gap-2.5">
              <span
                className="flex h-[30px] w-[30px] items-center justify-center rounded-lg"
                style={{ color: TONE_FG.ok, background: `${TONE_FG.ok}22` }}
              >
                <Icon name="shield" className="text-[18px]" />
              </span>
              <span className="font-display text-[15px] font-bold text-white">Huntress Security</span>
            </div>
            <Link to="/security" className="flex items-center gap-1 text-[12.5px] font-semibold text-icon-blue no-underline">
              View <Icon name="arrow_forward" className="text-[15px]" />
            </Link>
          </div>
          <div className="px-5 pb-5">
            <StatGrid
              stats={[
                { value: fmt(huntress?.total_agents), label: 'Total Agents' },
                { value: fmt(huntress?.open_incidents), label: 'Open Incidents', tone: 'ok' },
                { value: fmt(huntress?.critical_incidents), label: 'Critical' },
              ]}
            />
          </div>
        </div>
      </div>

      {/* Two-column lists */}
      <div className="grid grid-cols-1 items-start gap-4 md:grid-cols-2">
        <div className="kpi-card !pb-2">
          <div className="mb-1 flex items-center justify-between">
            <span className="font-display text-[15px] font-bold text-white">Recent Tickets</span>
            <Link to="/tickets" className="flex items-center gap-1 text-[12.5px] font-semibold text-icon-blue no-underline">
              All tickets <Icon name="arrow_forward" className="text-[15px]" />
            </Link>
          </div>
          {tickets.length === 0 ? (
            <div className="py-6 text-center text-xs text-ink-muted">No ticket data — sync Syncro to populate</div>
          ) : (
            tickets.map((t) => (
              <div key={t.ticket_id} className="flex items-center gap-3 border-t border-white/[0.07] py-3.5">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[13.5px] font-semibold text-ink-primary">{t.subject}</div>
                  <div className="mt-0.5 text-xs text-ink-faint">
                    {t.created_at ? new Date(t.created_at).toLocaleDateString() : ''}
                  </div>
                </div>
                <Badge state={t.status} />
              </div>
            ))
          )}
        </div>

        <div className="kpi-card !pb-2">
          <div className="mb-1 flex items-center justify-between">
            <span className="font-display text-[15px] font-bold text-white">Recent Security Incidents</span>
            <Link to="/security" className="flex items-center gap-1 text-[12.5px] font-semibold text-icon-blue no-underline">
              All incidents <Icon name="arrow_forward" className="text-[15px]" />
            </Link>
          </div>
          {incidents.length === 0 ? (
            <div className="py-6 text-center text-xs text-ink-muted">No incident data — sync Huntress to populate</div>
          ) : (
            incidents.map((inc) => {
              const tone = toneForState(inc.severity)
              return (
                <div key={inc.incident_id} className="flex items-center gap-3 border-t border-white/[0.07] py-3.5">
                  <span
                    className="flex h-8 w-8 flex-none items-center justify-center rounded-lg"
                    style={{ color: TONE_FG[tone], background: `${TONE_FG[tone]}22` }}
                  >
                    <Icon name={severityIcon(tone)} className="text-[18px]" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[13.5px] font-semibold text-ink-primary">{inc.summary}</div>
                    <div className="mt-0.5 text-xs text-ink-faint">{inc.status}</div>
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
