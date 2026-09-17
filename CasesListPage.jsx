import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchCases } from '../api/cases'

const STATUS_LABELS = {
  ai_flagged: 'AI Flagged',
  under_review: 'Under Review',
  field_verification_requested: 'Field Verification Requested',
  field_verification_completed: 'Field Verification Completed',
  decision_pending: 'Decision Pending',
  no_issue_closed: 'No Issue — Closed',
  irregularity_escalated: 'Irregularity Escalated',
  action_taken: 'Action Taken',
  inconclusive_reverify: 'Inconclusive — Re-verify',
  closed: 'Closed',
}

export default function CasesListPage() {
  const { data: cases, isLoading, error } = useQuery({ queryKey: ['cases'], queryFn: fetchCases })

  return (
    <div className="mx-auto max-w-4xl px-8 py-8">
      <h1 className="font-display text-2xl font-semibold text-ink">Case Workspace</h1>
      <p className="mt-1 mb-6 text-sm text-slate">Investigation cases within your assigned scope.</p>

      {isLoading && <p className="text-sm text-slate">Loading…</p>}
      {error && <p className="text-sm text-risk-critical">Could not load cases.</p>}

      {cases && cases.length === 0 && (
        <p className="rounded-sm border border-hairline bg-paper-raised px-5 py-6 text-sm text-slate">
          No cases yet. Open one from a project's Risk Profile.
        </p>
      )}

      {cases && cases.length > 0 && (
        <div className="overflow-hidden rounded-sm border border-hairline bg-paper-raised">
          {cases.map((c) => (
            <Link
              key={c.id}
              to={`/cases/${c.id}`}
              className="flex items-center justify-between border-b border-hairline px-5 py-3 last:border-b-0 hover:bg-paper"
            >
              <div>
                <p className="text-sm font-medium text-ink">{c.project_code}</p>
                <p className="text-xs text-slate">Opened {new Date(c.created_at).toLocaleDateString()}</p>
              </div>
              <span className="rounded-sm bg-paper px-2 py-1 text-xs font-medium text-ink-soft">
                {STATUS_LABELS[c.status] || c.status}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
