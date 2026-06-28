import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../lib/api'
import StatCard from '../components/StatCard'
import { useAuthContext } from './AuthContext'

interface Summary {
  instances: number
  volumes: number
  snapshots: number
}

export default function DashboardPage() {
  const { user } = useAuthContext()
  const [summary, setSummary] = useState<Summary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/inventory/summary')
      .then((r) => setSummary(r.data))
      .catch(() => setError('Failed to load summary.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 mb-1">
        Welcome back, {user?.name || user?.email}
      </h1>
      <p className="text-gray-500 mb-8">Here's an overview of your AWS resources.</p>

      {loading && <p className="text-gray-400">Loading…</p>}
      {error && <p className="text-red-500">{error}</p>}

      {summary && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-10">
            <StatCard label="EC2 Instances" value={summary.instances} icon="🖥️" color="border-blue-500" />
            <StatCard label="EBS Volumes"   value={summary.volumes}   icon="💾" color="border-purple-500" />
            <StatCard label="Snapshots"     value={summary.snapshots} icon="📸" color="border-green-500" />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              { to: '/instances', label: 'View Instances', icon: '🖥️' },
              { to: '/volumes',   label: 'View Volumes',   icon: '💾' },
              { to: '/snapshots', label: 'View Snapshots', icon: '📸' },
            ].map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className="flex items-center gap-3 bg-white hover:bg-brand-50 border border-gray-200 hover:border-brand-300 rounded-xl px-5 py-4 transition-colors shadow-sm"
              >
                <span className="text-2xl">{item.icon}</span>
                <span className="font-medium text-gray-700">{item.label}</span>
                <span className="ml-auto text-gray-400">→</span>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
