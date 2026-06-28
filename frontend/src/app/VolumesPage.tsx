import { useEffect, useState } from 'react'
import api from '../lib/api'
import Badge from '../components/Badge'

interface Volume {
  volume_id: string
  size_gb: number
  volume_type: string
  state: string
  availability_zone: string
  encrypted: boolean
  attached_instance_id: string
  create_time: string
}

export default function VolumesPage() {
  const [items, setItems] = useState<Volume[]>([])
  const [nextKey, setNextKey] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = (key?: string) => {
    setLoading(true)
    const params = key ? { last_key: key } : {}
    api.get('/inventory/volumes', { params })
      .then((r) => {
        setItems((prev) => key ? [...prev, ...r.data.items] : r.data.items)
        setNextKey(r.data.next_key ?? null)
      })
      .catch(() => setError('Failed to load volumes.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 mb-6">EBS Volumes</h1>
      {error && <p className="text-red-500 mb-4">{error}</p>}

      <div className="bg-white rounded-xl shadow overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                {['Volume ID','Size','Type','State','AZ','Encrypted','Attached To','Created'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.map((vol) => (
                <tr key={vol.volume_id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-mono text-xs text-gray-700 whitespace-nowrap">{vol.volume_id}</td>
                  <td className="px-4 py-3 whitespace-nowrap">{vol.size_gb} GB</td>
                  <td className="px-4 py-3 whitespace-nowrap uppercase">{vol.volume_type}</td>
                  <td className="px-4 py-3 whitespace-nowrap"><Badge state={vol.state} /></td>
                  <td className="px-4 py-3 whitespace-nowrap">{vol.availability_zone}</td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span className={vol.encrypted ? 'text-green-600 font-medium' : 'text-gray-400'}>
                      {vol.encrypted ? '🔒 Yes' : 'No'}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs whitespace-nowrap">{vol.attached_instance_id || '—'}</td>
                  <td className="px-4 py-3 whitespace-nowrap text-gray-500">
                    {vol.create_time ? new Date(vol.create_time).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
              {!loading && items.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">No volumes found.</td></tr>
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
