import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchProjectsPaged } from '../api/projects'
import { QueryStateHandler, EmptyState } from '../components/ui/States'
import RiskBadge from '../components/RiskBadge'

const PAGE_SIZE = 25
const RISK_LEVELS = ['low', 'medium', 'high', 'critical']
const SORT_OPTIONS = [
  { value: 'created_at', label: 'Recently added' },
  { value: 'final_score', label: 'Risk score' },
  { value: 'sanctioned_amount', label: 'Sanctioned amount' },
  { value: 'sanction_date', label: 'Sanction date' },
  { value: 'project_code', label: 'Project code' },
]

export default function ProjectExplorerPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [state, setState] = useState('')
  const [district, setDistrict] = useState('')
  const [workType, setWorkType] = useState('')
  const [status, setStatus] = useState('')
  const [riskLevel, setRiskLevel] = useState('')
  const [sortBy, setSortBy] = useState('created_at')
  const [sortDir, setSortDir] = useState('desc')
  const [offset, setOffset] = useState(0)

  const params = {
    search: search || undefined,
    state: state || undefined,
    district: district || undefined,
    work_type: workType || undefined,
    status: status || undefined,
    risk_level: riskLevel || undefined,
    sort_by: sortBy,
    sort_dir: sortDir,
    limit: PAGE_SIZE,
    offset,
  }

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['project-explorer', params],
    queryFn: () => fetchProjectsPaged(params),
  })

  function resetPage(setter) {
    return (value) => {
      setter(value)
      setOffset(0)
    }
  }

  function clearFilters() {
    setSearch('')
    setState('')
    setDistrict('')
    setWorkType('')
    setStatus('')
    setRiskLevel('')
    setOffset(0)
  }

  const hasFilters = search || state || district || workType || status || riskLevel
  const projects = data?.data || []
  const totalCount = data?.totalCount ?? 0

  return (
    <div className="mx-auto max-w-6xl px-8 py-8">
      <h1 className="font-display text-2xl font-semibold text-ink">Project Explorer</h1>
      <p className="mb-6 mt-1 text-sm text-slate">Search and filter every project in your scope.</p>

      <div className="mb-6 flex flex-wrap items-end gap-3">
        <div>
          <label className="mb-1 block text-xs text-slate">Search</label>
          <input
            type="text"
            placeholder="Project code or title…"
            value={search}
            onChange={(e) => resetPage(setSearch)(e.target.value)}
            className="rounded-sm border border-hairline bg-card px-3 py-2 text-sm text-ink outline-none focus:border-secondary"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate">State</label>
          <input
            type="text"
            value={state}
            onChange={(e) => resetPage(setState)(e.target.value)}
            className="w-32 rounded-sm border border-hairline bg-card px-3 py-2 text-sm text-ink outline-none focus:border-secondary"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate">District</label>
          <input
            type="text"
            value={district}
            onChange={(e) => resetPage(setDistrict)(e.target.value)}
            className="w-32 rounded-sm border border-hairline bg-card px-3 py-2 text-sm text-ink outline-none focus:border-secondary"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate">Work type</label>
          <input
            type="text"
            value={workType}
            onChange={(e) => resetPage(setWorkType)(e.target.value)}
            className="w-32 rounded-sm border border-hairline bg-card px-3 py-2 text-sm text-ink outline-none focus:border-secondary"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate">Status</label>
          <input
            type="text"
            value={status}
            onChange={(e) => resetPage(setStatus)(e.target.value)}
            className="w-32 rounded-sm border border-hairline bg-card px-3 py-2 text-sm text-ink outline-none focus:border-secondary"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate">Risk level</label>
          <select
            value={riskLevel}
            onChange={(e) => resetPage(setRiskLevel)(e.target.value)}
            className="rounded-sm border border-hairline bg-card px-3 py-2 text-sm capitalize text-ink outline-none focus:border-secondary"
          >
            <option value="">Any</option>
            {RISK_LEVELS.map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate">Sort by</label>
          <div className="flex gap-1">
            <select
              value={sortBy}
              onChange={(e) => resetPage(setSortBy)(e.target.value)}
              className="rounded-sm border border-hairline bg-card px-3 py-2 text-sm text-ink outline-none focus:border-secondary"
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <button
              onClick={() => resetPage(setSortDir)(sortDir === 'desc' ? 'asc' : 'desc')}
              className="rounded-sm border border-hairline bg-card px-2 text-sm text-ink-soft hover:border-secondary"
              title="Toggle sort direction"
            >
              {sortDir === 'desc' ? '↓' : '↑'}
            </button>
          </div>
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

      <QueryStateHandler
        isLoading={isLoading}
        error={error}
        data={projects}
        onRetry={refetch}
        emptyCheck={(d) => !d || d.length === 0}
        emptyState={
          <EmptyState
            title={hasFilters ? 'No projects match these filters' : 'No projects yet'}
            description={hasFilters ? 'Try widening your search.' : 'Import a dataset to get started.'}
          />
        }
      >
        <div className="overflow-hidden rounded-sm border border-hairline bg-card">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-hairline text-xs text-slate">
                <th className="px-4 py-3 font-medium">Code</th>
                <th className="px-4 py-3 font-medium">Title</th>
                <th className="px-4 py-3 font-medium">Work type</th>
                <th className="px-4 py-3 font-medium">Location</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Sanctioned</th>
                <th className="px-4 py-3 font-medium">Risk</th>
              </tr>
            </thead>
            <tbody>
              {projects.map((p) => (
                <tr
                  key={p.id}
                  onClick={() => navigate(`/projects/${p.id}`)}
                  className="cursor-pointer border-b border-hairline last:border-b-0 hover:bg-paper"
                >
                  <td className="px-4 py-3 font-mono text-xs text-slate">{p.project_code}</td>
                  <td className="max-w-xs truncate px-4 py-3 text-ink">{p.title}</td>
                  <td className="px-4 py-3 text-ink-soft">{p.work_type}</td>
                  <td className="px-4 py-3 text-xs text-slate">{p.district ? `${p.district}, ${p.state}` : '—'}</td>
                  <td className="px-4 py-3 text-xs capitalize text-ink-soft">{p.status?.replace(/_/g, ' ')}</td>
                  <td className="px-4 py-3 font-mono text-xs text-ink-soft">
                    {p.sanctioned_amount != null ? `₹${(p.sanctioned_amount / 100000).toFixed(1)}L` : '—'}
                  </td>
                  <td className="px-4 py-3">
                    {p.risk_level ? <RiskBadge level={p.risk_level} score={p.final_score} /> : <span className="text-xs text-slate">Unscored</span>}
                  </td>
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
          <span>
            Showing {totalCount === 0 ? 0 : offset + 1}–{Math.min(offset + PAGE_SIZE, totalCount)} of {totalCount}
          </span>
          <button
            onClick={() => setOffset((o) => o + PAGE_SIZE)}
            disabled={offset + PAGE_SIZE >= totalCount}
            className="rounded-sm border border-hairline px-3 py-1.5 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </QueryStateHandler>
    </div>
  )
}
