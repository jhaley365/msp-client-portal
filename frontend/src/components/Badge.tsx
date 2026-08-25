import { toneForState, TONE_FG } from '../lib/tone'

// Squarish chip — radius 4, 10.5px mono, alpha background.
export default function Badge({ state }: { state: string }) {
  const tone = toneForState(state)
  const fg = TONE_FG[tone]
  return (
    <span
      className="pill"
      style={{ color: fg, background: `${fg}20` }}
    >
      {state}
    </span>
  )
}
