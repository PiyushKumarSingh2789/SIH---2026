import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchComplianceResults } from '../api/projects'
import { QueryStateHandler, EmptyState } from '../components/ui/States'

const RESULT_STYLES = {
  PASS: 'bg-risk-low-bg text-risk-low',
  WARNING: 'bg-risk-medium-bg text-risk-medium',
  FAIL: 'bg-risk-critical-bg text-risk-critical',
}

const CHECK_LABELS = {
  'CMP-001': 'Sanctioned amount vs. estimate',
  'CMP-002': 'Utilized amount within sanction',
  'CMP-003': 'Expected completion after sanction',
  'CMP-004': 'Actual completion after sanction',
  'CMP-005': 'Payments after sanction date',
  'CMP-006': 'Completed status matches full progress',
  'CMP-007': 'Location coordinates present',
}

export default function CompliancePage() {
  const navigate = useNavigate()
  const [resultFilter, setResultFilter] = useState('')

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['compliance', resultFilter],
    queryFn: () => fetchComplianceResults({ result: resultFilter || undefined, limit: 500 }),
  })

  const results = data || []
  const failCount = results.filter((r) => r.result === 'FAIL').length
  const warningCount = results.filter((r) => r.result === 'WARNING').length

  return (
    <div className="mx-auto max-w-6xl px-8 py-8">
      <h1 className="font-display text-2xl font-semibold text-ink">Compliance Center</h1>
      <p className="mb-1 mt-1 text-sm text-slate">
        Rule-based data-quality and consistency checks, computed live from project records.
      </p>
      <p className="mb-6 text-xs italic text-slate">
        These are review flags, not statutory findings — verify against official MPLADS guidelines before acting.
      </p>

      <div className="mb-6 flex gap-1">
        {[
          { value: '', label: `All (${results.length})` },
          { value: 'FAIL', label: `Fail (${failCount})` },
          { value: 'WARNING', label: `Warning (${warningCount})` },
          { value: 'PASS', label: 'Pass' },
        ].map((opt) => (
          <button
            key={opt.value}
            onClick={() => setResultFilter(opt.value)}
            className={`rounded-sm border px-3 py-1.5 text-xs font-medium ${
              resultFilter === opt.value ? 'border-ink bg-ink text-paper' : 'border-hairline text-slate hover:border-ink hover:text-ink'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <QueryStateHandler
        isLoading={isLoading}
        error={error}
        data={results}
        onRetry={refetch}
        emptyCheck={(d) => !d || d.length === 0}
        emptyState={<EmptyState title="No results" description="No compliance checks match this filter." />}
      >
        <div className="overflow-hidden rounded-sm border border-hairline bg-card">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-hairline text-xs text-slate">
                <th className="px-4 py-3 font-medium">Rule</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Evidence</th>
                <th className="px-4 py-3 font-medium">Project</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => (
                <tr key={`${r.project_id}-${r.check_code}-${i}`} className="border-b border-hairline last:border-b-0 hover:bg-paper">
                  <td className="px-4 py-3 text-ink">
                    <span className="font-mono text-xs text-slate">{r.check_code}</span>
                    <span className="block text-xs text-ink-soft">{CHECK_LABELS[r.check_code] || ''}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`rounded-sm px-2 py-0.5 text-xs font-medium ${RESULT_STYLES[r.result]}`}>{r.result}</span>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate">
                    {Object.keys(r.evidence).length === 0 ? '—' : (
                      Object.entries(r.evidence).map(([k, v]) => (
                        <span key={k} className="mr-3 inline-block">
                          {k.replace(/_/g, ' ')}: <span className="font-mono text-ink-soft">{String(v)}</span>
                        </span>
                      ))
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => navigate(`/projects/${r.project_id}`)}
                      className="font-mono text-xs text-secondary underline underline-offset-2"
                    >
                      {r.project_code}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </QueryStateHandler>
    </div>
  )
}
