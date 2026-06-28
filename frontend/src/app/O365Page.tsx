import { useEffect, useState } from 'react'
import api from '../lib/api'
import KpiCard from '../components/KpiCard'
import DataTable, { Column } from '../components/DataTable'
import Badge from '../components/Badge'

interface License {
  sku_part_number: string
  total: number
  used: number
}

interface Mailbox {
  display_name: string
  email: string
  mailbox_type: string
  size_mb: number
  item_count: number
}

export default function O365Page() {
  const [licenses, setLicenses] = useState<License[]>([])
  const [mailboxes, setMailboxes] = useState<Mailbox[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.allSettled([
      api.get('/o365/licenses'),
      api.get('/o365/mailboxes'),
    ]).then(([lic, mb]) => {
      if (lic.status === 'fulfilled') setLicenses(lic.value.data?.items ?? lic.value.data ?? [])
      if (mb.status === 'fulfilled') setMailboxes(mb.value.data?.items ?? mb.value.data ?? [])
    }).finally(() => setLoading(false))
  }, [])

  const totalLicenses = licenses.reduce((s, l) => s + (l.total ?? 0), 0)
  const usedLicenses = licenses.reduce((s, l) => s + (l.used ?? 0), 0)
  const availableLicenses = totalLicenses - usedLicenses

  const licenseColumns: Column<License>[] = [
    { key: 'sku_part_number', header: 'SKU Name' },
    { key: 'total', header: 'Total' },
    { key: 'used', header: 'Used' },
    { key: 'available', header: 'Available', render: (row) => String(row.total - row.used) },
    {
      key: 'utilization',
      header: 'Utilization %',
      render: (row) => row.total > 0 ? `${Math.round((row.used / row.total) * 100)}%` : '—',
    },
  ]

  const mailboxColumns: Column<Mailbox>[] = [
    { key: 'display_name', header: 'Display Name' },
    { key: 'email', header: 'Email' },
    { key: 'mailbox_type', header: 'Type', render: (row) => <Badge status={row.mailbox_type} /> },
    { key: 'size_mb', header: 'Size MB' },
    { key: 'item_count', header: 'Items' },
  ]

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-gray-800">Office 365</h1>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <KpiCard
          label="Total Licenses"
          value={loading ? '…' : (licenses.length ? totalLicenses : '--')}
          color="border-blue-500"
        />
        <KpiCard
          label="Used Licenses"
          value={loading ? '…' : (licenses.length ? usedLicenses : '--')}
          color="border-orange-500"
        />
        <KpiCard
          label="Available"
          value={loading ? '…' : (licenses.length ? availableLicenses : '--')}
          color="border-green-500"
        />
      </div>

      <div className="section-card">
        <div className="p-4 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-700">Licenses</h2>
        </div>
        <DataTable<License>
          columns={licenseColumns}
          data={licenses}
          loading={loading}
          emptyMessage="No license data available."
        />
      </div>

      <div className="section-card">
        <div className="p-4 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-700">Mailboxes</h2>
        </div>
        <DataTable<Mailbox>
          columns={mailboxColumns}
          data={mailboxes}
          loading={loading}
          emptyMessage="No mailbox data available."
        />
      </div>
    </div>
  )
}
