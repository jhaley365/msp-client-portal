import { ReactNode } from 'react'

export interface Column<T> {
  key: string
  header: string
  render?: (row: T) => ReactNode
  className?: string
  /** When true, the cell value is rendered in accent blue mono (e.g. ticket #) */
  accent?: boolean
  /** When true, the cell value is rendered in muted mono (e.g. dates) */
  mono?: boolean
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
          <div className="h-3.5 w-3/4 animate-pulse rounded bg-white/10" />
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
        <table className="min-w-full text-[12.5px]">
          {/* Mono uppercase headers, tighter cells */}
          <thead style={{ background: 'var(--color-ctrl-bg)' }}>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`px-4 py-3 text-left font-mono text-[10px] font-medium uppercase tracking-[0.13em] text-ink-mono whitespace-nowrap border-b border-panel-border ${col.className ?? ''}`}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
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
                <tr
                  key={(row[keyField] as string) ?? i}
                  className="border-b border-row-hairline transition-colors hover:bg-white/[0.025] last:border-0"
                  style={{ verticalAlign: 'top' }}
                >
                  {columns.map((col) => {
                    const cellClass = col.accent
                      ? 'font-mono text-icon-blue'
                      : col.mono
                      ? 'font-mono text-ink-muted'
                      : 'text-ink-secondary'
                    return (
                      <td
                        key={col.key}
                        className={`px-4 py-3 leading-[1.5] ${cellClass} ${col.className ? col.className + ' overflow-hidden' : 'whitespace-nowrap'}`}
                      >
                        {col.render ? col.render(row) : String(row[col.key] ?? '')}
                      </td>
                    )
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {hasMore && onLoadMore && !loading && (
        <div className="border-t border-panel-border px-4 py-3">
          <button
            onClick={onLoadMore}
            className="text-[12.5px] font-medium text-icon-blue hover:text-ink-primary"
          >
            Load more →
          </button>
        </div>
      )}
      {loading && data.length > 0 && (
        <div className="border-t border-panel-border px-4 py-3 text-[12.5px] text-ink-muted">
          Loading…
        </div>
      )}
    </div>
  )
}
