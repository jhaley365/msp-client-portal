const STATE_COLORS: Record<string, string> = {
  running:    'bg-green-100 text-green-800',
  available:  'bg-green-100 text-green-800',
  completed:  'bg-green-100 text-green-800',
  stopped:    'bg-yellow-100 text-yellow-800',
  'in-use':   'bg-blue-100 text-blue-800',
  pending:    'bg-blue-100 text-blue-800',
  terminated: 'bg-red-100 text-red-800',
  error:      'bg-red-100 text-red-800',
}

export default function Badge({ state }: { state: string }) {
  const cls = STATE_COLORS[state] ?? 'bg-gray-100 text-gray-700'
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${cls}`}>
      {state}
    </span>
  )
}
