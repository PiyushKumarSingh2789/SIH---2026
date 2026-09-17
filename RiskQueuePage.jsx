import { useState, useEffect, useMemo } from 'react'
import { useSearchParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { fetchAlerts } from '../api/projects'
import { createCase } from '../api/cases'
import { useToast } from '../components/ui/Toast'
import { LoadingState, ErrorState, EmptyState } from '../components/ui/States'
import RiskBadge from '../components/RiskBadge'

const PAGE_SIZE = 15

export default function RiskQueuePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const presetLevel = searchParams.get('level')
  const [minLevel, setMinLevel] = useState(presetLevel || 'medium')
  const [search, setSearch] = useState('')
  const [sortDir, setSortDir] = useState('desc')
  const [page, setPage] = useState(1)
  const navigate = useNavigate()
  const { showToast } = useToast()

  useEffect(() => {
    if (presetLevel) setMinLevel(presetLevel)
  }, [presetLevel])

  useEffect(() => {
    setPage(1) // reset to page 1 whenever the filter set changes
  }, [minLevel, search])

  const { data: alerts, isLoading, error, refetch } = useQuery({
    queryKey: ['alerts', minLevel],
    queryFn: () => fetchAlerts(minLevel, 200),
  })

  const caseMutation = useMutation({
    mutationFn: (projectId) => createCase(projectId),
    onSuccess: (c) => navigate(`/cases/${c.id}`),
    onError: () => showToast('Could not open a case for this project.', 'error'),
  })

  const filtered = useMemo(() => {
    const bySearch = (alerts || []).filter(
      (a) =>
        !search ||
        a.title.toLowerCase().includes(search.toLowerCase()) ||
        a.project_code.toLowerCase().includes(search.toLowerCase())
    )
    return [...bySearch].sort((a, b) => (sortDir === 'desc' ? b.final_score - a.final_score : a.final_score - b.final_score))
  }, [alerts, search, sortDir])

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  function handleLevelChange(value) {
    setMinLevel(value)
    setSearchParams(value === 'medium' ? {} : { level: value })
  }

  const activeChips = []
  if (minLevel !== 'medium') activeChips.push({ label: `${minLevel} and above`, onClear: () => handleLevelChange('medium') })
  if (search) activeChips.push({ label: `"${search}"`, onClear: () => setSearch('') })

  return (
    <div className="mx-auto max-w-5xl px-8 py-8">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-ink">Risk Queue</h1>
          <p className="mt-1 text-sm text-slate">Which project should be investigated first?</p>
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Search project code or title…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="rounded-sm border border-hairline bg-paper-raised px-3 py-2 text-sm text-ink outline-none focus:border-accent"
          />
          <select
            value={minLevel}
            onChange={(e) => handleLevelChange(e.target.value)}
            className="rounded-sm border border-hairline bg-paper-raised px-3 py-2 text-sm text-ink outline-none focus:border-accent"
          >
            <option value="low">Show all levels</option>
            <option value="medium">Medium and above</option>
            <option value="high">High and above</option>
            <option value="critical">Critical only</option>
          </select>
          <button
            onClick={() => setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'))}
            className="rounded-sm border border-hairline bg-paper-raised px-3 py-2 text-sm text-ink hover:bg-paper"
            title="Toggle sort order"
          >
            Score {sortDir === 'desc' ? '↓' : '↑'}
          </button>
        </div>
      </div>

      {activeChips.length > 0 && (
        <div className="mb-4 flex gap-2">
          {activeChips.map((chip, i) => (
            <button
              key={i}
              onClick={chip.onClear}
              className="flex items-center gap-1 rounded-full border border-accent bg-blue-50 px-3 py-1 text-xs font-medium text-accent"
            >
              {chip.label} <span aria-hidden>×</span>
            </button>
          ))}
        </div>
      )}

      {isLoading && <LoadingState />}
      {error && <ErrorState message="Could not load the queue. Try a recompute from the Dashboard." onRetry={refetch} />}

      {alerts && filtered.length === 0 && (
        <EmptyState
          title={search ? 'No projects match your search' : 'Nothing matches this filter'}
          description="Try widening the risk level filter or clearing your search."
        />
      )}

      {pageItems.length > 0 && (
        <>
          <div className="overflow-hidden rounded-sm border border-hairline bg-paper-raised">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-hairline text-xs text-slate">
                  <th className="px-5 py-3 font-medium">Project</th>
                  <th className="px-5 py-3 font-medium">Top signal</th>
                  <th className="px-5 py-3 font-medium">Risk</th>
                  <th className="px-5 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pageItems.map((a) => (
                  <tr key={a.project_id} className="border-b border-hairline last:border-b-0 hover:bg-paper">
                    <td className="px-5 py-3">
                      <Link to={`/projects/${a.project_id}`} className="font-medium text-ink hover:underline">
                        {a.title}
                      </Link>
                      <p className="font-mono text-xs text-slate">{a.project_code}</p>
                    </td>
                    <td className="px-5 py-3 text-xs text-slate">{a.top_factor_explanation || '—'}</td>
                    <td className="px-5 py-3">
                      <RiskBadge level={a.risk_level} score={a.final_score} />
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex gap-3 text-xs">
                        <Link to={`/projects/${a.project_id}`} className="font-medium text-accent hover:underline">
                          View Project
                        </Link>
                        <button
                          onClick={() => caseMutation.mutate(a.project_id)}
                          disabled={caseMutation.isPending}
                          className="font-medium text-ink-soft hover:underline disabled:opacity-50"
                        >
                          Review Case
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 flex items-center justify-between text-sm text-slate">
            <span>
              Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, filtered.length)} of {filtered.length}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="rounded-sm border border-hairline bg-paper-raised px-3 py-1.5 disabled:opacity-40"
              >
                Previous
              </button>
              <span className="px-2 py-1.5">Page {page} of {totalPages}</span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="rounded-sm border border-hairline bg-paper-raised px-3 py-1.5 disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
