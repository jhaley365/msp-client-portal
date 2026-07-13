import { useEffect, useState } from 'react'
import api from '../lib/api'
import DataTable, { Column } from '../components/DataTable'
import Badge from '../components/Badge'

type Tab = 'Instances' | 'Volumes' | 'Snapshots' | 'RDS' | 'Aurora' | 'Backup Vaults' | 'Backup Jobs' | 'FSx' | 'Route 53'

interface Instance {
  instance_id: string; name_tag: string; instance_type: string; state: string
  region: string; private_ip: string; public_ip: string; platform: string; launch_time: string
}
interface Volume {
  volume_id: string; size_gb: number; volume_type: string; state: string
  availability_zone: string; encrypted: boolean; attached_instance_id: string; create_time: string
}
interface Snapshot {
  snapshot_id: string; volume_id: string; size_gb: number; state: string
  progress: string; encrypted: boolean; description: string; start_time: string
}
interface RdsInstance {
  db_instance_id: string; engine: string; engine_version: string; status: string
  instance_class: string; region: string; multi_az: boolean; storage_gb: number
  storage_type: string; encrypted: boolean; endpoint_address: string; endpoint_port: number
  instance_create_time: string
}
interface RdsCluster {
  db_cluster_id: string; engine: string; engine_version: string; status: string
  region: string; multi_az: boolean; member_count: number; endpoint: string
  reader_endpoint: string; port: number; encrypted: boolean; cluster_create_time: string
}
interface BackupVault {
  vault_arn: string; vault_name: string; region: string; recovery_points: number
  encryption_key_arn: string; creation_date: string
}
interface BackupJob {
  backup_job_id: string; vault_name: string; resource_name: string; resource_type: string; state: string
  status_message: string; region: string; backup_size_bytes: number
  creation_date: string; completion_date: string
}
interface FsxFs {
  file_system_id: string; file_system_type: string; lifecycle: string
  storage_capacity_gb: number; throughput_capacity_mbps: number
  dns_name: string; region: string; creation_time: string
}
interface Route53Zone {
  zone_id: string; name: string; private_zone: boolean; comment: string
  record_count: number; caller_reference: string
}

function fmtBytes(bytes: number): string {
  if (!bytes) return '—'
  if (bytes >= 1e12) return `${(bytes / 1e12).toFixed(1)} TB`
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`
  if (bytes >= 1e6) return `${(bytes / 1e6).toFixed(1)} MB`
  return `${bytes} B`
}

function fmtDate(iso: string): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString()
}

function useTabData<T>(tab: Tab, targetTab: Tab, endpoint: string, sortKey?: string) {
  const [items, setItems] = useState<T[]>([])
  const [loading, setLoading] = useState(false)
  const [nextKey, setNextKey] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(false)

  const load = async (append = false) => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (append && nextKey) params.last_key = nextKey
      const { data } = await api.get(endpoint, { params })
      setItems((prev) => append ? [...prev, ...data.items] : data.items)
      setNextKey(data.next_key ?? null)
      setHasMore(!!data.next_key)
    } catch {
      if (!append) setItems([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (tab === targetTab) load()
  }, [tab])

  return { items, loading, hasMore, loadMore: () => load(true) }
}

export default function AwsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('Instances')

  const instances = useTabData<Instance>(activeTab, 'Instances', '/inventory/instances')
  const volumes = useTabData<Volume>(activeTab, 'Volumes', '/inventory/volumes')
  const snapshots = useTabData<Snapshot>(activeTab, 'Snapshots', '/inventory/snapshots')
  const rdsInstances = useTabData<RdsInstance>(activeTab, 'RDS', '/inventory/rds/instances')
  const rdsClusters = useTabData<RdsCluster>(activeTab, 'Aurora', '/inventory/rds/clusters')
  const backupVaults = useTabData<BackupVault>(activeTab, 'Backup Vaults', '/inventory/backup/vaults')
  const backupJobs = useTabData<BackupJob>(activeTab, 'Backup Jobs', '/inventory/backup/jobs')
  const fsx = useTabData<FsxFs>(activeTab, 'FSx', '/inventory/fsx')
  const route53 = useTabData<Route53Zone>(activeTab, 'Route 53', '/inventory/route53')

  const instanceColumns: Column<Instance>[] = [
    { key: 'name_tag', header: 'Name', render: (r) => r.name_tag || <span className="italic text-ink-muted">—</span> },
    { key: 'instance_id', header: 'Instance ID' },
    { key: 'instance_type', header: 'Type' },
    { key: 'state', header: 'State', render: (r) => <Badge state={r.state} /> },
    { key: 'region', header: 'Region' },
    { key: 'private_ip', header: 'Private IP' },
    { key: 'public_ip', header: 'Public IP' },
    { key: 'platform', header: 'Platform' },
    { key: 'launch_time', header: 'Launched', render: (r) => fmtDate(r.launch_time) },
  ]

  const volumeColumns: Column<Volume>[] = [
    { key: 'volume_id', header: 'Volume ID' },
    { key: 'size_gb', header: 'Size', render: (r) => `${r.size_gb} GB` },
    { key: 'volume_type', header: 'Type' },
    { key: 'state', header: 'State', render: (r) => <Badge state={r.state} /> },
    { key: 'availability_zone', header: 'AZ' },
    { key: 'encrypted', header: 'Encrypted', render: (r) => r.encrypted ? '🔒' : '—' },
    { key: 'attached_instance_id', header: 'Attached To', render: (r) => r.attached_instance_id || '—' },
    { key: 'create_time', header: 'Created', render: (r) => fmtDate(r.create_time) },
  ]

  const snapshotColumns: Column<Snapshot>[] = [
    { key: 'snapshot_id', header: 'Snapshot ID' },
    { key: 'volume_id', header: 'Volume ID' },
    { key: 'size_gb', header: 'Size', render: (r) => `${r.size_gb} GB` },
    { key: 'state', header: 'State', render: (r) => <Badge state={r.state} /> },
    { key: 'progress', header: 'Progress' },
    { key: 'encrypted', header: 'Encrypted', render: (r) => r.encrypted ? '🔒' : '—' },
    { key: 'description', header: 'Description' },
    { key: 'start_time', header: 'Date', render: (r) => fmtDate(r.start_time) },
  ]

  const rdsInstanceColumns: Column<RdsInstance>[] = [
    { key: 'db_instance_id', header: 'DB Instance ID' },
    { key: 'engine', header: 'Engine', render: (r) => `${r.engine} ${r.engine_version}` },
    { key: 'status', header: 'Status', render: (r) => <Badge state={r.status} /> },
    { key: 'instance_class', header: 'Class' },
    { key: 'region', header: 'Region' },
    { key: 'storage_gb', header: 'Storage', render: (r) => `${r.storage_gb} GB ${r.storage_type}` },
    { key: 'multi_az', header: 'Multi-AZ', render: (r) => r.multi_az ? 'Yes' : 'No' },
    { key: 'encrypted', header: 'Encrypted', render: (r) => r.encrypted ? '🔒' : '—' },
    { key: 'endpoint_address', header: 'Endpoint', render: (r) => r.endpoint_address ? `${r.endpoint_address}:${r.endpoint_port}` : '—' },
    { key: 'instance_create_time', header: 'Created', render: (r) => fmtDate(r.instance_create_time) },
  ]

  const rdsClusterColumns: Column<RdsCluster>[] = [
    { key: 'db_cluster_id', header: 'Cluster ID' },
    { key: 'engine', header: 'Engine', render: (r) => `${r.engine} ${r.engine_version}` },
    { key: 'status', header: 'Status', render: (r) => <Badge state={r.status} /> },
    { key: 'region', header: 'Region' },
    { key: 'member_count', header: 'Members' },
    { key: 'multi_az', header: 'Multi-AZ', render: (r) => r.multi_az ? 'Yes' : 'No' },
    { key: 'encrypted', header: 'Encrypted', render: (r) => r.encrypted ? '🔒' : '—' },
    { key: 'endpoint', header: 'Writer Endpoint', render: (r) => r.endpoint || '—' },
    { key: 'cluster_create_time', header: 'Created', render: (r) => fmtDate(r.cluster_create_time) },
  ]

  const vaultColumns: Column<BackupVault>[] = [
    { key: 'vault_name', header: 'Vault Name' },
    { key: 'region', header: 'Region' },
    { key: 'recovery_points', header: 'Recovery Points' },
    { key: 'encryption_key_arn', header: 'Encrypted', render: (r) => r.encryption_key_arn ? '🔒' : '—' },
    { key: 'creation_date', header: 'Created', render: (r) => fmtDate(r.creation_date) },
  ]

  const jobColumns: Column<BackupJob>[] = [
    { key: 'backup_job_id', header: 'Job ID', render: (r) => <span className="font-mono text-[11px]">{r.backup_job_id.slice(0, 8)}…</span> },
    { key: 'vault_name', header: 'Vault' },
    { key: 'resource_name', header: 'Resource Name', render: (r) => r.resource_name || '—' },
    { key: 'resource_type', header: 'Resource Type' },
    { key: 'state', header: 'State', render: (r) => <Badge state={r.state} /> },
    { key: 'region', header: 'Region' },
    { key: 'backup_size_bytes', header: 'Size', render: (r) => fmtBytes(r.backup_size_bytes) },
    { key: 'creation_date', header: 'Started', render: (r) => fmtDate(r.creation_date) },
    { key: 'completion_date', header: 'Completed', render: (r) => fmtDate(r.completion_date) },
  ]

  const fsxColumns: Column<FsxFs>[] = [
    { key: 'file_system_id', header: 'File System ID' },
    { key: 'file_system_type', header: 'Type' },
    { key: 'lifecycle', header: 'Status', render: (r) => <Badge state={r.lifecycle} /> },
    { key: 'storage_capacity_gb', header: 'Storage', render: (r) => `${r.storage_capacity_gb} GB` },
    { key: 'throughput_capacity_mbps', header: 'Throughput', render: (r) => r.throughput_capacity_mbps ? `${r.throughput_capacity_mbps} MB/s` : '—' },
    { key: 'region', header: 'Region' },
    { key: 'dns_name', header: 'DNS Name', render: (r) => r.dns_name || '—' },
    { key: 'creation_time', header: 'Created', render: (r) => fmtDate(r.creation_time) },
  ]

  const route53Columns: Column<Route53Zone>[] = [
    { key: 'name', header: 'Zone Name' },
    { key: 'zone_id', header: 'Zone ID' },
    { key: 'private_zone', header: 'Type', render: (r) => r.private_zone ? 'Private' : 'Public' },
    { key: 'record_count', header: 'Records' },
    { key: 'comment', header: 'Comment', render: (r) => r.comment || '—' },
  ]

  const tabs: Tab[] = ['Instances', 'Volumes', 'Snapshots', 'RDS', 'Aurora', 'Backup Vaults', 'Backup Jobs', 'FSx', 'Route 53']

  return (
    <div className="space-y-5">
      <h1 className="font-display text-xl font-bold text-white">AWS</h1>

      <div className="flex flex-wrap gap-2">
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
          <DataTable<Instance> columns={instanceColumns} data={instances.items} loading={instances.loading}
            emptyMessage="No instances found." hasMore={instances.hasMore} onLoadMore={instances.loadMore} />
        )}
        {activeTab === 'Volumes' && (
          <DataTable<Volume> columns={volumeColumns} data={volumes.items} loading={volumes.loading}
            emptyMessage="No volumes found." hasMore={volumes.hasMore} onLoadMore={volumes.loadMore} />
        )}
        {activeTab === 'Snapshots' && (
          <DataTable<Snapshot> columns={snapshotColumns} data={snapshots.items} loading={snapshots.loading}
            emptyMessage="No snapshots found." hasMore={snapshots.hasMore} onLoadMore={snapshots.loadMore} />
        )}
        {activeTab === 'RDS' && (
          <DataTable<RdsInstance> columns={rdsInstanceColumns} data={rdsInstances.items} loading={rdsInstances.loading}
            emptyMessage="No RDS instances found." hasMore={rdsInstances.hasMore} onLoadMore={rdsInstances.loadMore} />
        )}
        {activeTab === 'Aurora' && (
          <DataTable<RdsCluster> columns={rdsClusterColumns} data={rdsClusters.items} loading={rdsClusters.loading}
            emptyMessage="No Aurora clusters found." hasMore={rdsClusters.hasMore} onLoadMore={rdsClusters.loadMore} />
        )}
        {activeTab === 'Backup Vaults' && (
          <DataTable<BackupVault> columns={vaultColumns} data={backupVaults.items} loading={backupVaults.loading}
            emptyMessage="No backup vaults found." hasMore={backupVaults.hasMore} onLoadMore={backupVaults.loadMore} />
        )}
        {activeTab === 'Backup Jobs' && (
          <DataTable<BackupJob> columns={jobColumns} data={backupJobs.items} loading={backupJobs.loading}
            emptyMessage="No backup jobs found." hasMore={backupJobs.hasMore} onLoadMore={backupJobs.loadMore} />
        )}
        {activeTab === 'FSx' && (
          <DataTable<FsxFs> columns={fsxColumns} data={fsx.items} loading={fsx.loading}
            emptyMessage="No FSx file systems found." hasMore={fsx.hasMore} onLoadMore={fsx.loadMore} />
        )}
        {activeTab === 'Route 53' && (
          <DataTable<Route53Zone> columns={route53Columns} data={route53.items} loading={route53.loading}
            emptyMessage="No hosted zones found." hasMore={route53.hasMore} onLoadMore={route53.loadMore} />
        )}
      </div>
    </div>
  )
}
