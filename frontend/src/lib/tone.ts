export type Tone = 'ok' | 'warn' | 'crit' | 'info' | 'purple' | 'muted'

export const TONE_FG: Record<Tone, string> = {
  ok: '#4ade80',
  warn: '#fbbf24',
  crit: '#f87171',
  info: '#7cb0ff',
  purple: '#c4b5fd',
  muted: '#9aa6b8',
}

const STATE_TONES: Record<string, Tone> = {
  // ok — resolved / healthy
  running: 'ok',
  active: 'ok',
  online: 'ok',
  completed: 'ok',
  enabled: 'ok',
  available: 'ok',
  resolved: 'ok',
  closed: 'ok',
  // warn — needs attention / waiting
  stopped: 'warn',
  offline: 'warn',
  warning: 'warn',
  pending: 'warn',
  'customer reply': 'warn',
  // purple — waiting on someone else
  'waiting on customer': 'purple',
  'waiting for parts': 'purple',
  // crit — errors / critical
  terminated: 'crit',
  error: 'crit',
  critical: 'crit',
  disabled: 'crit',
  'escalated to msp': 'crit',
  // info — open / active work
  new: 'info',
  open: 'info',
  'in-use': 'info',
  'in-progress': 'info',
  'in progress': 'info',
  investigating: 'info',
  scheduled: 'info',
  // severity
  high: 'purple',
  medium: 'warn',
  low: 'muted',
  // fallback
  abandoned: 'muted',
}

export function toneForState(state: string | undefined | null): Tone {
  return STATE_TONES[(state ?? '').toLowerCase()] ?? 'muted'
}
