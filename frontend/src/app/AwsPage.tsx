import { useEffect, useState } from 'react'
import api from '../lib/api'
import DataTable, { Column } from '../components/DataTable'
import Badge from '../components/Badge'

type Tab = 'Instances' | 'Volumes' | 'Snapshots' | 'RDS' | 'Aurora' | 'Backup Vaults' | 'Backup Jobs' | 'Coverage' | 'FSx' | 'Route 53' | 'VPN'

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
interface CoverageRecord {
  instance_id: string; instance_name: string; state: string; region: string
  is_covered: boolean; last_backup_date: string; first_detected_at: string; checked_at: string
}
interface VpnConnection {
  vpn_id: string; name: string; state: string; type: string; region: string
  customer_gateway_id: string; vpn_gateway_id: string; routing: string
  tunnel1_outside_ip: string; tunnel1_status: string; tunnel1_last_change: string
  tunnel2_outside_ip: string; tunnel2_status: string; tunnel2_last_change: string
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

function useTabData<T>(tab: Tab, targetTab: Tab, endpoint: string, sortKey?: keyof T) {
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
      setItems((prev) => {
        const merged = append ? [...prev, ...data.items] : data.items
        if (sortKey) {
          merged.sort((a, b) => {
            const av = ((a[sortKey] as unknown) as string) ?? ''
            const bv = ((b[sortKey] as unknown) as string) ?? ''
            return av.toLowerCase().localeCompare(bv.toLowerCase())
          })
        }
        return merged
      })
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

  const instances = useTabData<Instance>(activeTab, 'Instances', '/inventory/instances', 'name_tag')
  const volumes = useTabData<Volume>(activeTab, 'Volumes', '/inventory/volumes')
  const snapshots = useTabData<Snapshot>(activeTab, 'Snapshots', '/inventory/snapshots')
  const rdsInstances = useTabData<RdsInstance>(activeTab, 'RDS', '/inventory/rds/instances', 'db_instance_id')
  const rdsClusters = useTabData<RdsCluster>(activeTab, 'Aurora', '/inventory/rds/clusters', 'db_cluster_id')
  const backupVaults = useTabData<BackupVault>(activeTab, 'Backup Vaults', '/inventory/backup/vaults', 'vault_name')
  const backupJobs = useTabData<BackupJob>(activeTab, 'Backup Jobs', '/inventory/backup/jobs')
  const [coverage, setCoverage] = useState<CoverageRecord[]>([])
  const [coverageLoading, setCoverageLoading] = useState(false)
  useEffect(() => {
    if (activeTab !== 'Coverage') return
    setCoverageLoading(true)
    api.get('/inventory/backup/coverage')
      .then(({ data }) => setCoverage(data.items))
      .catch(() => setCoverage([]))
      .finally(() => setCoverageLoading(false))
  }, [activeTab])
  const fsx = useTabData<FsxFs>(activeTab, 'FSx', '/inventory/fsx', 'file_system_id')
  const route53 = useTabData<Route53Zone>(activeTab, 'Route 53', '/inventory/route53', 'name')
  const vpn = useTabData<VpnConnection>(activeTab, 'VPN', '/inventory/vpn', 'name')

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

  function TunnelStatus({ ip, status, lastChange }: { ip: string; status: string; lastChange: string }) {
    const up = status.toLowerCase() === 'up'
    return (
      <div className="space-y-0.5">
        <div className="flex items-center gap-1.5">
          <span className={`inline-block h-2 w-2 rounded-full ${up ? 'bg-tone-ok' : 'bg-tone-crit'}`} />
          <span className="font-mono text-[12px]">{ip || '—'}</span>
        </div>
        {lastChange && <div className="text-[11px] text-ink-faint">{new Date(lastChange).toLocaleString()}</div>}
      </div>
    )
  }

  const vpnColumns: Column<VpnConnection>[] = [
    { key: 'name', header: 'Name', render: (r) => r.name || <span className="italic text-ink-muted">—</span> },
    { key: 'vpn_id', header: 'VPN ID' },
    { key: 'state', header: 'State', render: (r) => <Badge state={r.state} /> },
    { key: 'routing', header: 'Routing' },
    { key: 'region', header: 'Region' },
    { key: 'customer_gateway_id', header: 'Customer GW' },
    {
      key: 'tunnel1_status',
      header: 'Tunnel 1',
      render: (r) => <TunnelStatus ip={r.tunnel1_outside_ip} status={r.tunnel1_status} lastChange={r.tunnel1_last_change} />,
    },
    {
      key: 'tunnel2_status',
      header: 'Tunnel 2',
      render: (r) => <TunnelStatus ip={r.tunnel2_outside_ip} status={r.tunnel2_status} lastChange={r.tunnel2_last_change} />,
    },
  ]

  const route53Columns: Column<Route53Zone>[] = [
    { key: 'name', header: 'Zone Name' },
    { key: 'zone_id', header: 'Zone ID' },
    { key: 'private_zone', header: 'Type', render: (r) => r.private_zone ? 'Private' : 'Public' },
    { key: 'record_count', header: 'Records' },
    { key: 'comment', header: 'Comment', render: (r) => r.comment || '—' },
  ]

  const uncoveredCount = coverage.filter(r => !r.is_covered).length

  const coverageColumns: Column<CoverageRecord>[] = [
    {
      key: 'instance_name', header: 'Instance',
      render: (r) => (
        <div>
          <div className="font-medium">{r.instance_name || r.instance_id}</div>
          <div className="font-mono text-[11px] text-ink-muted">{r.instance_id}</div>
        </div>
      ),
    },
    { key: 'state', header: 'State', render: (r) => <Badge state={r.state} /> },
    { key: 'region', header: 'Region' },
    {
      key: 'is_covered', header: 'Backup Status',
      render: (r) => r.is_covered
        ? <span className="inline-flex items-center gap-1.5 rounded-full bg-tone-ok/[0.12] px-2.5 py-0.5 text-[12px] font-semibold text-tone-ok"><span className="h-1.5 w-1.5 rounded-full bg-tone-ok" />Protected</span>
        : <span className="inline-flex items-center gap-1.5 rounded-full bg-tone-crit/[0.12] px-2.5 py-0.5 text-[12px] font-semibold text-tone-crit"><span className="h-1.5 w-1.5 rounded-full bg-tone-crit" />Not Backed Up</span>,
    },
    { key: 'last_backup_date', header: 'Last Backup', render: (r) => r.last_backup_date ? fmtDate(r.last_backup_date) : <span className="text-tone-crit">Never</span> },
    { key: 'first_detected_at', header: 'Gap Since', render: (r) => r.first_detected_at ? fmtDate(r.first_detected_at) : '—' },
    { key: 'checked_at', header: 'Last Checked', render: (r) => fmtDate(r.checked_at) },
  ]

  const isAdmin = !!JSON.parse(localStorage.getItem('user') || '{}')?.is_admin
  const tabs: Tab[] = ['Instances', 'Volumes', 'Snapshots', 'RDS', 'Aurora', 'Backup Vaults', 'Backup Jobs', ...(isAdmin ? ['Coverage' as Tab] : []), 'FSx', 'VPN', 'Route 53']

  return (
    <div className="space-y-5">
      <h1 className="font-display text-xl font-bold text-white">AWS</h1>

      <div className="flex flex-wrap gap-2">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`tab-btn ${activeTab === tab ? 'active' : ''} relative`}
          >
            {tab}
            {tab === 'Coverage' && uncoveredCount > 0 && (
              <span className="ml-1.5 inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-tone-crit px-1 text-[10px] font-bold text-white">
                {uncoveredCount}
              </span>
            )}
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
        {activeTab === 'Coverage' && (
          <>
            {!coverageLoading && coverage.length > 0 && uncoveredCount > 0 && (
              <div className="mx-4 mt-4 flex items-center gap-3 rounded-lg border border-tone-crit/[0.3] bg-tone-crit/[0.08] px-4 py-3 text-[13px]">
                <span className="h-2 w-2 rounded-full bg-tone-crit" />
                <span className="font-semibold text-tone-crit">{uncoveredCount} instance{uncoveredCount !== 1 ? 's' : ''} not covered by AWS Backup</span>
                <span className="text-ink-muted">— an alert email has been sent</span>
              </div>
            )}
            <DataTable<CoverageRecord> columns={coverageColumns} data={coverage} loading={coverageLoading}
              emptyMessage="No coverage data yet. Run the backup coverage sync to populate." />
          </>
        )}
        {activeTab === 'Backup Jobs' && (
          <DataTable<BackupJob> columns={jobColumns} data={backupJobs.items} loading={backupJobs.loading}
            emptyMessage="No backup jobs found." hasMore={backupJobs.hasMore} onLoadMore={backupJobs.loadMore} />
        )}
        {activeTab === 'FSx' && (
          <DataTable<FsxFs> columns={fsxColumns} data={fsx.items} loading={fsx.loading}
            emptyMessage="No FSx file systems found." hasMore={fsx.hasMore} onLoadMore={fsx.loadMore} />
        )}
        {activeTab === 'VPN' && (
          <DataTable<VpnConnection> columns={vpnColumns} data={vpn.items} loading={vpn.loading}
            emptyMessage="No VPN connections found." hasMore={vpn.hasMore} onLoadMore={vpn.loadMore} />
        )}
        {activeTab === 'Route 53' && (
          <DataTable<Route53Zone> columns={route53Columns} data={route53.items} loading={route53.loading}
            emptyMessage="No hosted zones found." hasMore={route53.hasMore} onLoadMore={route53.loadMore} />
        )}
      </div>
    </div>
  )
}
