import { BarChart, Bar, ResponsiveContainer, Tooltip, XAxis } from 'recharts'

interface Props {
  data: Array<{ label: string; value: number }>
  color?: string
  height?: number
}

export default function MiniBarChart({ data, color = '#0078d4', height = 80 }: Props) {
  const chartData = data.map(d => ({ name: d.label, value: d.value }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={chartData} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
        <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={{ fontSize: 12, borderRadius: 6, border: '1px solid #e5e7eb' }}
          cursor={{ fill: '#f3f4f6' }}
        />
        <Bar dataKey="value" fill={color} radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
