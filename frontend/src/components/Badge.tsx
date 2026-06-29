const STATE_COLORS: Record<string, string> = {
  // green — resolved / healthy
  running: 'bg-green-100 text-green-700',
  active: 'bg-green-100 text-green-700',
  online: 'bg-green-100 text-green-700',
  completed: 'bg-green-100 text-green-700',
  enabled: 'bg-green-100 text-green-700',
  available: 'bg-green-100 text-green-700',
  resolved: 'bg-green-100 text-green-700',
  closed: 'bg-green-100 text-green-700',
  // yellow — needs attention / waiting
  stopped: 'bg-yellow-100 text-yellow-700',
  offline: 'bg-yellow-100 text-yellow-700',
  warning: 'bg-yellow-100 text-yellow-700',
  pending: 'bg-yellow-100 text-yellow-700',
  'waiting on customer': 'bg-yellow-100 text-yellow-700',
  'customer reply': 'bg-yellow-100 text-yellow-700',
  scheduled: 'bg-yellow-100 text-yellow-700',
  // red — errors / critical
  terminated: 'bg-red-100 text-red-700',
  error: 'bg-red-100 text-red-700',
  critical: 'bg-red-100 text-red-700',
  // blue — open / active work
  new: 'bg-blue-100 text-blue-700',
  open: 'bg-blue-100 text-blue-700',
  'in-use': 'bg-blue-100 text-blue-700',
  'in-progress': 'bg-blue-100 text-blue-700',
  'in progress': 'bg-blue-100 text-blue-700',
  investigating: 'bg-blue-100 text-blue-700',
  // purple / orange / gray — severity
  high: 'bg-purple-100 text-purple-700',
  medium: 'bg-orange-100 text-orange-700',
  low: 'bg-gray-100 text-gray-600',
}

export default function Badge({ state }: { state: string }) {
  const key = (state ?? '').toLowerCase()
  const cls = STATE_COLORS[key] ?? 'bg-gray-100 text-gray-600'
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold capitalize ${cls}`}>
      {state}
    </span>
  )
}
