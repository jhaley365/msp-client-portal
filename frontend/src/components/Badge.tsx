import { toneForState, TONE_FG } from '../lib/tone'

export default function Badge({ state }: { state: string }) {
  const tone = toneForState(state)
  return (
    <span
      className="pill"
      style={{ color: TONE_FG[tone], background: `${TONE_FG[tone]}22` }}
    >
      {state}
    </span>
  )
}
