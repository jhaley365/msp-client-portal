import { useEffect, useState } from 'react'
import api from '../lib/api'
import KpiCard from '../components/KpiCard'
import DataTable, { Column } from '../components/DataTable'
import Badge from '../components/Badge'

interface Summary {
  total_licenses: number
  consumed_licenses: number
  available_licenses: number
  total_mailboxes: number
}

interface License {
  license_id: string
  sku_name: string
  total_units: number
  consumed_units: number
  available_units: number
}

interface Mailbox {
  mailbox_id: string
  display_name: string
  email: string
  account_enabled: boolean
  licensed: boolean
  license_names: string
  mailbox_size_mb: number
}

export default function O365Page() {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [licenses, setLicenses] = useState<License[]>([])
  const [mailboxes, setMailboxes] = useState<Mailbox[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.allSettled([
      api.get('/o365/summary'),
      api.get('/o365/licenses'),
      api.get('/o365/mailboxes'),
    ]).then(([sum, lic, mb]) => {
      if (sum.status === 'fulfilled') setSummary(sum.value.data)
      if (lic.status === 'fulfilled') setLicenses(lic.value.data?.items ?? lic.value.data ?? [])
      if (mb.status === 'fulfilled') {
        const items: Mailbox[] = mb.value.data?.items ?? mb.value.data ?? []
        setMailboxes(items.sort((a, b) => a.display_name.localeCompare(b.display_name)))
      }
    }).finally(() => setLoading(false))
  }, [])

  const licenseColumns: Column<License>[] = [
    { key: 'sku_name', header: 'License SKU' },
    { key: 'total_units', header: 'Total' },
    { key: 'consumed_units', header: 'Used' },
    { key: 'available_units', header: 'Available' },
    {
      key: 'utilization',
      header: 'Utilization',
      render: (row) => {
        const pct = row.total_units > 0
          ? Math.round((row.consumed_units / row.total_units) * 100)
          : 0
        const color = pct >= 90 ? 'bg-red-100 text-red-700'
          : pct >= 75 ? 'bg-orange-100 text-orange-700'
          : 'bg-green-100 text-green-700'
        return (
          <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${color}`}>
            {pct}%
          </span>
        )
      },
    },
  ]

  const fmtSize = (mb: number) => {
    if (!mb) return '—'
    if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`
    return `${mb} MB`
  }

  const mailboxColumns: Column<Mailbox>[] = [
    { key: 'display_name', header: 'Name' },
    { key: 'email', header: 'Email', className: 'font-mono text-xs' },
    {
      key: 'account_enabled',
      header: 'Status',
      render: (row) => <Badge state={row.account_enabled ? 'active' : 'disabled'} />,
    },
    {
      key: 'license_names',
      header: 'License',
      className: 'max-w-[160px] w-40',
      render: (row) => row.license_names
        ? <span className="text-xs text-gray-700 block truncate" title={row.license_names}>{row.license_names}</span>
        : <span className="text-xs text-gray-400">Not Licensed</span>,
    },
    {
      key: 'mailbox_size_mb',
      header: 'Mailbox Size',
      render: (row) => <span className="text-xs whitespace-nowrap">{fmtSize(row.mailbox_size_mb)}</span>,
    },
  ]

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-gray-800">Office 365</h1>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <KpiCard label="Total Licenses" value={summary?.total_licenses ?? '--'} accentColor="border-blue-500" />
        <KpiCard label="Licenses Used" value={summary?.consumed_licenses ?? '--'} accentColor="border-orange-500" />
        <KpiCard label="Licenses Available" value={summary?.available_licenses ?? '--'} accentColor="border-green-500" />
        <KpiCard label="Total Users" value={summary?.total_mailboxes ?? '--'} accentColor="border-gray-400" />
      </div>

      <div className="section-card">
        <div className="p-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700">License SKUs</h2>
          <span className="text-xs text-gray-400">{licenses.length} SKUs</span>
        </div>
        <DataTable<License>
          columns={licenseColumns}
          data={licenses}
          loading={loading}
          emptyMessage="No license data available."
          keyField="license_id"
        />
      </div>

      <div className="section-card">
        <div className="p-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700">Users</h2>
          <span className="text-xs text-gray-400">{mailboxes.length} total</span>
        </div>
        <div className="overflow-y-auto" style={{ maxHeight: '32rem' }}>
          <DataTable<Mailbox>
            columns={mailboxColumns}
            data={mailboxes}
            loading={loading}
            emptyMessage="No users found."
            keyField="mailbox_id"
          />
        </div>
      </div>
    </div>
  )
}
