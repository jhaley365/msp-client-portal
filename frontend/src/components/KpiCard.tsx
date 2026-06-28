interface Props {
  label: string
  value: string | number
  trend?: number
  trendLabel?: string
  icon?: string
  accentColor?: string
}

export default function KpiCard({ label, value, trend, trendLabel, icon, accentColor = 'border-blue-500' }: Props) {
  const hasTrend = trend !== undefined && trend !== null
  const trendPositive = (trend ?? 0) >= 0

  return (
    <div className={`kpi-card border-l-4 ${accentColor} flex flex-col gap-2`}>
      <div className="flex items-start justify-between">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{label}</p>
        {icon && <span className="text-2xl text-gray-300">{icon}</span>}
      </div>
      <p className="text-3xl font-bold text-gray-800 leading-none">{value}</p>
      {hasTrend && (
        <div className="flex items-center gap-1.5">
          <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs font-semibold ${
            trendPositive ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
          }`}>
            {trendPositive ? '↑' : '↓'} {Math.abs(trend ?? 0)}%
          </span>
          {trendLabel && <span className="text-xs text-gray-400">{trendLabel}</span>}
        </div>
      )}
    </div>
  )
}
