import Icon from './Icon'
import { Tone, TONE_FG } from '../lib/tone'

interface Props {
  label: string
  value: string | number
  sub?: string
  icon?: string
  tone?: Tone
}

export default function KpiCard({ label, value, sub, icon, tone = 'info' }: Props) {
  const fg = TONE_FG[tone]
  return (
    <div className="kpi-card" style={{ borderTop: `3px solid ${fg}` }}>
      <div className="flex items-start justify-between">
        <span className="text-[11.5px] font-semibold uppercase tracking-wider text-ink-muted">
          {label}
        </span>
        {icon && <Icon name={icon} className="text-[22px]" style={{ color: fg }} />}
      </div>
      <div className="mt-3.5 font-mono text-[34px] font-semibold leading-none tabular-nums text-white">
        {value}
      </div>
      {sub && <div className="mt-2.5 text-xs text-ink-muted">{sub}</div>}
    </div>
  )
}
