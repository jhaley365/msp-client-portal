import Icon from './Icon'
import { Tone, TONE_FG } from '../lib/tone'

export interface KpiCell {
  label: string
  value: string | number
  sub?: string
  icon?: string
  tone?: Tone
}

interface Props {
  cells: KpiCell[]
}

// One bordered container with hairline dividers between cells.
// Replaces the individual-card grid on dashboard and tickets.
export default function KpiStrip({ cells }: Props) {
  return (
    <div className="flex overflow-hidden rounded-lg border border-panel-border bg-panel">
      {cells.map((cell, i) => {
        const tone = cell.tone ?? 'info'
        const valueFg =
          tone === 'info' || tone === 'muted'
            ? 'var(--color-ink-primary)'
            : TONE_FG[tone]

        return (
          <div
            key={cell.label}
            className={`flex flex-1 flex-col gap-2 p-[17px] ${
              i > 0 ? 'border-l border-divider' : ''
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="eyebrow">{cell.label}</span>
              {cell.icon && (
                <Icon
                  name={cell.icon}
                  className="text-[16px]"
                  style={{ color: TONE_FG[tone] }}
                />
              )}
            </div>
            <div
              className="font-mono text-[34px] font-medium leading-none tabular-nums"
              style={{ color: valueFg }}
            >
              {cell.value}
            </div>
            {cell.sub && (
              <div className="text-[11.5px] text-ink-faint">{cell.sub}</div>
            )}
          </div>
        )
      })}
    </div>
  )
}
