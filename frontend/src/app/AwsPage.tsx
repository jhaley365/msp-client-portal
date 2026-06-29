import { useEffect, useState } from 'react'
import api from '../lib/api'
import DataTable, { Column } from '../components/DataTable'
import Badge from '../components/Badge'

type Tab = 'Instances' | 'Volumes' | 'Snapshots'

interface Instance {
  instance_id: string
  instance_type: string
  state: string
  region: string
  private_ip: string
  public_ip: string
  platform: string
  launch_time: string
}

interface Attachment {
  instance_id: string
}

interface Volume {
  volume_id: string
  size: number
  volume_type: string
  state: string
  availability_zone: string
  encrypted: boolean
  attachments?: Attachment[]
  create_time: string
}

interface Snapshot {
  snapshot_id: string
  volume_id: string
  volume_size: number
  state: string
  progress: string
  encrypted: boolean
  description: string
  start_time: string
}

export default function AwsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('Instances')
  const [instances, setInstances] = useState<Instance[]>([])
  const [volumes, setVolumes] = useState<Volume[]>([])
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])
  const [loading, setLoading] = useState(false)
  const [lastKeyInstances, setLastKeyInstances] = useState<string | null>(null)
  const [lastKeyVolumes, setLastKeyVolumes] = useState<string | null>(null)
  const [lastKeySnapshots, setLastKeySnapshots] = useState<string | null>(null)
  const [hasMoreInstances, setHasMoreInstances] = useState(false)
  const [hasMoreVolumes, setHasMoreVolumes] = useState(false)
  const [hasMoreSnapshots, setHasMoreSnapshots] = useState(false)

  const loadInstances = async (append = false) => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (append && lastKeyInstances) params.last_key = lastKeyInstances
      const { data } = await api.get('/inventory/instances', { params })
      setInstances((prev) => append ? [...prev, ...data.items] : data.items)
      setLastKeyInstances(data.last_key ?? null)
      setHasMoreInstances(!!data.last_key)
    } catch {
      if (!append) setInstances([])
    } finally {
      setLoading(false)
    }
  }

  const loadVolumes = async (append = false) => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (append && lastKeyVolumes) params.last_key = lastKeyVolumes
      const { data } = await api.get('/inventory/volumes', { params })
      setVolumes((prev) => append ? [...prev, ...data.items] : data.items)
      setLastKeyVolumes(data.last_key ?? null)
      setHasMoreVolumes(!!data.last_key)
    } catch {
      if (!append) setVolumes([])
    } finally {
      setLoading(false)
    }
  }

  const loadSnapshots = async (append = false) => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (append && lastKeySnapshots) params.last_key = lastKeySnapshots
      const { data } = await api.get('/inventory/snapshots', { params })
      setSnapshots((prev) => append ? [...prev, ...data.items] : data.items)
      setLastKeySnapshots(data.last_key ?? null)
      setHasMoreSnapshots(!!data.last_key)
    } catch {
      if (!append) setSnapshots([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (activeTab === 'Instances') loadInstances()
    if (activeTab === 'Volumes') loadVolumes()
    if (activeTab === 'Snapshots') loadSnapshots()
  }, [activeTab])

  const instanceColumns: Column<Instance>[] = [
    { key: 'instance_id', header: 'Instance ID' },
    { key: 'instance_type', header: 'Type' },
    { key: 'state', header: 'State', render: (row) => <Badge state={row.state} /> },
    { key: 'region', header: 'Region' },
    { key: 'private_ip', header: 'Private IP' },
    { key: 'public_ip', header: 'Public IP' },
    { key: 'platform', header: 'Platform' },
    { key: 'launch_time', header: 'Launched', render: (row) => new Date(row.launch_time).toLocaleDateString() },
  ]

  const volumeColumns: Column<Volume>[] = [
    { key: 'volume_id', header: 'Volume ID' },
    { key: 'size', header: 'Size', render: (row) => `${row.size} GB` },
    { key: 'volume_type', header: 'Type' },
    { key: 'state', header: 'State', render: (row) => <Badge state={row.state} /> },
    { key: 'availability_zone', header: 'AZ' },
    { key: 'encrypted', header: 'Encrypted', render: (row) => row.encrypted ? '🔒' : '—' },
    { key: 'attachments', header: 'Attached To', render: (row) => row.attachments?.[0]?.instance_id ?? '—' },
    { key: 'create_time', header: 'Created', render: (row) => new Date(row.create_time).toLocaleDateString() },
  ]

  const snapshotColumns: Column<Snapshot>[] = [
    { key: 'snapshot_id', header: 'Snapshot ID' },
    { key: 'volume_id', header: 'Volume ID' },
    { key: 'volume_size', header: 'Size', render: (row) => `${row.volume_size} GB` },
    { key: 'state', header: 'State', render: (row) => <Badge state={row.state} /> },
    { key: 'progress', header: 'Progress' },
    { key: 'encrypted', header: 'Encrypted', render: (row) => row.encrypted ? '🔒' : '—' },
    { key: 'description', header: 'Description' },
    { key: 'start_time', header: 'Date', render: (row) => new Date(row.start_time).toLocaleDateString() },
  ]

  const tabs: Tab[] = ['Instances', 'Volumes', 'Snapshots']

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-gray-800">AWS</h1>

      <div className="flex gap-2">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="section-card">
        {activeTab === 'Instances' && (
          <DataTable<Instance>
            columns={instanceColumns}
            data={instances}
            loading={loading}
            emptyMessage="No instances found."
            hasMore={hasMoreInstances}
            onLoadMore={() => loadInstances(true)}
          />
        )}
        {activeTab === 'Volumes' && (
          <DataTable<Volume>
            columns={volumeColumns}
            data={volumes}
            loading={loading}
            emptyMessage="No volumes found."
            hasMore={hasMoreVolumes}
            onLoadMore={() => loadVolumes(true)}
          />
        )}
        {activeTab === 'Snapshots' && (
          <DataTable<Snapshot>
            columns={snapshotColumns}
            data={snapshots}
            loading={loading}
            emptyMessage="No snapshots found."
            hasMore={hasMoreSnapshots}
            onLoadMore={() => loadSnapshots(true)}
          />
        )}
      </div>
    </div>
  )
}
