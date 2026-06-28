import { useEffect, useState } from 'react'
import api from '../lib/api'
import Badge from '../components/Badge'

interface Instance {
  instance_id: string
  instance_type: string
  state: string
  region: string
  availability_zone: string
  private_ip: string
  public_ip: string
  platform: string
  launch_time: string
  vpc_id: string
}

export default function InstancesPage() {
  const [items, setItems] = useState<Instance[]>([])
  const [nextKey, setNextKey] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = (key?: string) => {
    setLoading(true)
    const params = key ? { last_key: key } : {}
    api.get('/inventory/instances', { params })
      .then((r) => {
        setItems((prev) => key ? [...prev, ...r.data.items] : r.data.items)
        setNextKey(r.data.next_key ?? null)
      })
      .catch(() => setError('Failed to load instances.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 mb-6">EC2 Instances</h1>
      {error && <p className="text-red-500 mb-4">{error}</p>}

      <div className="bg-white rounded-xl shadow overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                {['Instance ID','Type','State','Region','Private IP','Public IP','Platform','Launched'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.map((inst) => (
                <tr key={inst.instance_id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-mono text-xs text-gray-700 whitespace-nowrap">{inst.instance_id}</td>
                  <td className="px-4 py-3 whitespace-nowrap">{inst.instance_type}</td>
                  <td className="px-4 py-3 whitespace-nowrap"><Badge state={inst.state} /></td>
                  <td className="px-4 py-3 whitespace-nowrap">{inst.region}</td>
                  <td className="px-4 py-3 font-mono text-xs whitespace-nowrap">{inst.private_ip || '—'}</td>
                  <td className="px-4 py-3 font-mono text-xs whitespace-nowrap">{inst.public_ip || '—'}</td>
                  <td className="px-4 py-3 whitespace-nowrap capitalize">{inst.platform || 'linux'}</td>
                  <td className="px-4 py-3 whitespace-nowrap text-gray-500">
                    {inst.launch_time ? new Date(inst.launch_time).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
              {!loading && items.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">No instances found.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {loading && <p className="text-gray-400 mt-4">Loading…</p>}
      {nextKey && !loading && (
        <button
          onClick={() => load(nextKey)}
          className="mt-4 px-5 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-sm transition-colors"
        >
          Load more
        </button>
      )}
    </div>
  )
}
