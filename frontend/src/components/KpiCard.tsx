import Icon from './Icon'
import { Tone, TONE_VAR } from '../lib/tone'

interface Props {
  label: string
  value: string | number
  sub?: string
  icon?: string
  tone?: Tone
}

// Flat panel variant — tone is carried by the value colour, not a top border.
export default function KpiCard({ label, value, sub, icon, tone = 'info' }: Props) {
  const toneColor = TONE_VAR[tone]
  const valueFg = tone === 'info' || tone === 'muted' ? 'var(--color-ink-primary)' : toneColor
  return (
    <div className="kpi-card flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="eyebrow">{label}</span>
        {icon && (
          <Icon
            name={icon}
            className="text-[16px]"
            style={{ color: toneColor }}
          />
        )}
      </div>
      <div
        className="font-mono text-[34px] font-medium leading-none tabular-nums"
        style={{ color: valueFg }}
      >
        {value}
      </div>
      {sub && <div className="text-[11.5px] text-ink-faint">{sub}</div>}
    </div>
  )
}
