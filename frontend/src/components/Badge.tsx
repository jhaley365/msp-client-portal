import { toneForState, TONE_VAR } from '../lib/tone'

// Squarish chip — radius 4, 10.5px mono, alpha background.
// Uses CSS variables so tone colors automatically adapt to light/dark mode.
export default function Badge({ state }: { state: string }) {
  const tone = toneForState(state)
  const fg = TONE_VAR[tone]
  return (
    <span
      className="pill"
      style={{ color: fg, background: `color-mix(in srgb, ${fg} 15%, transparent)` }}
    >
      {state}
    </span>
  )
}
