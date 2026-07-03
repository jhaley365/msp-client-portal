import { ReactNode } from 'react'

export interface Column<T> {
  key: string
  header: string
  render?: (row: T) => ReactNode
  className?: string
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
interface Props<T extends Record<string, any>> {
  columns: Column<T>[]
  data: T[]
  loading?: boolean
  emptyMessage?: string
  onLoadMore?: () => void
  hasMore?: boolean
  keyField?: string
}

function SkeletonRow({ cols }: { cols: number }) {
  return (
    <tr>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 w-3/[0.04] animate-pulse rounded bg-white/10" />
        </td>
      ))}
    </tr>
  )
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export default function DataTable<T extends Record<string, any>>({
  columns, data, loading, emptyMessage = 'No data found.', onLoadMore, hasMore, keyField = 'id',
}: Props<T>) {
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-white/[0.07] text-sm">
          <thead className="bg-white/[0.04]">
            <tr>
              {columns.map(col => (
                <th key={col.key} className={`px-4 py-3 text-left text-xs font-semibold text-ink-muted uppercase tracking-wider whitespace-nowrap ${col.className ?? ''}`}>
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.07]">
            {loading && data.length === 0 ? (
              Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} cols={columns.length} />)
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-10 text-center text-ink-muted">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              data.map((row, i) => (
                <tr key={(row[keyField] as string) ?? i} className="transition-colors hover:bg-white/[0.04]">
                  {columns.map(col => (
                    <td key={col.key} className={`px-4 py-3 text-ink-secondary ${col.className ? col.className + ' overflow-hidden' : 'whitespace-nowrap'}`}>
                      {col.render ? col.render(row) : String(row[col.key] ?? '—')}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {hasMore && onLoadMore && !loading && (
        <div className="border-t border-white/[0.07] px-4 py-3">
          <button
            onClick={onLoadMore}
            className="text-sm font-medium text-icon-blue hover:text-white"
          >
            Load more →
          </button>
        </div>
      )}
      {loading && data.length > 0 && (
        <div className="border-t border-white/[0.07] px-4 py-3 text-sm text-ink-muted">Loading…</div>
      )}
    </div>
  )
}
