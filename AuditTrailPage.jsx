import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchAuditLogs } from '../api/audit'

const PAGE_SIZE = 50

export default function AuditTrailPage() {
  const [search, setSearch] = useState('')
  const [action, setAction] = useState('')
  const [entityType, setEntityType] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [offset, setOffset] = useState(0)

  const params = {
    limit: PAGE_SIZE,
    offset,
    search: search || undefined,
    action: action || undefined,
    entity_type: entityType || undefined,
    date_from: dateFrom ? new Date(dateFrom).toISOString() : undefined,
    date_to: dateTo ? new Date(dateTo).toISOString() : undefined,
  }

  const { data: logs, isLoading, error } = useQuery({
    queryKey: ['audit-logs', params],
    queryFn: () => fetchAuditLogs(params),
  })

  function handleFilterChange(setter) {
    return (e) => {
      setter(e.target.value)
      setOffset(0) // any filter change restarts pagination from the first page
    }
  }

  function clearFilters() {
    setSearch('')
    setAction('')
    setEntityType('')
    setDateFrom('')
    setDateTo('')
    setOffset(0)
  }

  const hasFilters = search || action || entityType || dateFrom || dateTo

  return (
    <div className="mx-auto max-w-5xl px-8 py-8">
      <h1 className="font-display text-2xl font-semibold text-ink">Audit Trail</h1>
      <p className="mt-1 mb-6 text-sm text-slate">
        Every sensitive action recorded across the system — an append-only log, not just case history.
      </p>

      <div className="mb-6 flex flex-wrap items-end gap-3">
        <div>
          <label className="mb-1 block text-xs text-slate">Search</label>
          <input
            type="text"
            placeholder="Action, entity, remark…"
            value={search}
            onChange={handleFilterChange(setSearch)}
            className="rounded-sm border border-hairline bg-paper-raised px-3 py-2 text-sm text-ink outline-none focus:border-ink"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate">Action</label>
          <input
            type="text"
            placeholder="e.g. case.status_changed"
            value={action}
            onChange={handleFilterChange(setAction)}
            className="rounded-sm border border-hairline bg-paper-raised px-3 py-2 text-sm text-ink outline-none focus:border-ink"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate">Entity type</label>
          <input
            type="text"
            placeholder="e.g. case"
            value={entityType}
            onChange={handleFilterChange(setEntityType)}
            className="rounded-sm border border-hairline bg-paper-raised px-3 py-2 text-sm text-ink outline-none focus:border-ink"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate">From</label>
          <input
            type="date"
            value={dateFrom}
            onChange={handleFilterChange(setDateFrom)}
            className="rounded-sm border border-hairline bg-paper-raised px-3 py-2 text-sm text-ink outline-none focus:border-ink"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate">To</label>
          <input
            type="date"
            value={dateTo}
            onChange={handleFilterChange(setDateTo)}
            className="rounded-sm border border-hairline bg-paper-raised px-3 py-2 text-sm text-ink outline-none focus:border-ink"
          />
        </div>
        {hasFilters && (
          <button
            onClick={clearFilters}
            className="rounded-sm border border-hairline px-3 py-2 text-xs text-slate hover:border-ink hover:text-ink"
          >
            Clear filters
          </button>
        )}
      </div>

      {isLoading && <p className="text-sm text-slate">Loading…</p>}
      {error && (
        <p className="text-sm text-risk-critical">
          {error.response?.status === 403
            ? 'You do not have permission to view the system-wide audit trail.'
            : 'Could not load the audit trail.'}
        </p>
      )}

      {logs && logs.length === 0 && (
        <p className="rounded-sm border border-hairline bg-paper-raised px-5 py-6 text-sm text-slate">
          {hasFilters ? 'No audit entries match these filters.' : 'No audit entries recorded yet.'}
        </p>
      )}

      {logs && logs.length > 0 && (
        <>
          <div className="overflow-hidden rounded-sm border border-hairline bg-paper-raised">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-hairline text-xs text-slate">
                  <th className="px-4 py-3 font-medium">Timestamp</th>
                  <th className="px-4 py-3 font-medium">User</th>
                  <th className="px-4 py-3 font-medium">Role</th>
                  <th className="px-4 py-3 font-medium">Action</th>
                  <th className="px-4 py-3 font-medium">Entity</th>
                  <th className="px-4 py-3 font-medium">Description</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id} className="border-b border-hairline last:border-b-0 hover:bg-paper">
                    <td className="px-4 py-3 whitespace-nowrap font-mono text-xs text-slate">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-ink">{log.user_name || '—'}</td>
                    <td className="px-4 py-3 text-xs capitalize text-ink-soft">
                      {log.role_at_time ? log.role_at_time.replace(/_/g, ' ').replace(/,/g, ', ') : '—'}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-ink-soft">{log.action}</td>
                    <td className="px-4 py-3 text-xs text-slate">
                      {log.entity_type || '—'}
                      {log.entity_id && <span className="block font-mono text-slate-light">{log.entity_id.slice(0, 8)}</span>}
                    </td>
                    <td className="px-4 py-3 text-ink-soft">{log.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 flex items-center justify-between text-xs text-slate">
            <button
              onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
              disabled={offset === 0}
              className="rounded-sm border border-hairline px-3 py-1.5 disabled:opacity-40"
            >
              Previous
            </button>
            <span>Showing {offset + 1}–{offset + logs.length}</span>
            <button
              onClick={() => setOffset((o) => o + PAGE_SIZE)}
              disabled={logs.length < PAGE_SIZE}
              className="rounded-sm border border-hairline px-3 py-1.5 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  )
}
