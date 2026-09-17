import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchCase, fetchCaseBrief } from '../api/cases'
import { fetchProjectRisk } from '../api/projects'

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

const FACTOR_LABELS = {
  COST_DEVIATION: 'Cost Deviation',
  PROGRESS_EXPENDITURE_MISMATCH: 'Progress–Expenditure Mismatch',
  DELAY_STALL: 'Delay / Stall',
  PAYMENT_ANOMALY: 'Payment Anomaly',
  DUPLICATE_SIMILARITY: 'Duplicate Similarity',
  PEER_DEVIATION: 'Peer Deviation',
  ML_ANOMALY: 'ML Anomaly (Isolation Forest)',
}

// Same 3-way grouping used to organize the page's "Findings" sections -- purely a presentation
// grouping over the same 7 factor codes the rest of the app already knows about.
const FINDING_GROUPS = [
  { title: 'Financial Findings', codes: ['COST_DEVIATION', 'PAYMENT_ANOMALY'] },
  { title: 'Execution Findings', codes: ['PROGRESS_EXPENDITURE_MISMATCH', 'DELAY_STALL', 'PEER_DEVIATION'] },
  { title: 'AI / Anomaly Findings', codes: ['ML_ANOMALY', 'DUPLICATE_SIMILARITY'] },
]

// Generic, non-project-specific investigative guidance, triggered only by which finding
// categories actually fired for this case -- never a claim about the project itself.
const GROUP_GUIDANCE = {
  'Financial Findings': 'Verify utilized-amount records against underlying vouchers and payment references.',
  'Execution Findings': 'Consider requesting field verification of physical progress against reported figures.',
  'AI / Anomaly Findings': 'Treat as a statistical signal only — confirm manually before drawing any conclusion.',
}

export default function InvestigationBriefPage() {
  const { caseId } = useParams()
  const navigate = useNavigate()

  const { data: caseDetail, isLoading: caseLoading, error: caseError } = useQuery({
    queryKey: ['case', caseId],
    queryFn: () => fetchCase(caseId),
  })
  const { data: brief, isLoading: briefLoading, error: briefError } = useQuery({
    queryKey: ['case-brief', caseId],
    queryFn: () => fetchCaseBrief(caseId),
  })
  // Best-effort: the fuller factor breakdown is a bonus for the Findings sections below.
  // If the project hasn't been scored (or scope blocks it), the page still renders fine without it.
  const { data: risk } = useQuery({
    queryKey: ['project-risk', caseDetail?.project_id],
    queryFn: () => fetchProjectRisk(caseDetail.project_id),
    enabled: !!caseDetail?.project_id,
    retry: false,
  })

  if (caseLoading || briefLoading) {
    return <div className="px-8 py-8 text-sm text-slate">Loading…</div>
  }
  if (caseError || briefError) {
    return (
      <div className="px-8 py-8">
        <p className="text-sm text-risk-critical">
          {caseError?.response?.status === 403 || briefError?.response?.status === 403
            ? 'This case is outside your assigned scope.'
            : 'Could not load this investigation brief.'}
        </p>
        <button onClick={() => navigate(-1)} className="mt-3 text-sm text-ink underline">
          Go back
        </button>
      </div>
    )
  }

  const factors = risk?.factors ? [...risk.factors].sort((a, b) => b.contribution - a.contribution) : []
  const topFlagged = factors.filter((f) => f.contribution > 0).slice(0, 3)
  const activeGroups = FINDING_GROUPS
    .map((g) => ({ ...g, factors: factors.filter((f) => g.codes.includes(f.factor_code)) }))
    .filter((g) => g.factors.length > 0)

  return (
    <div className="min-h-screen bg-paper">
      <style>{`
        @media print {
          .no-print { display: none !important; }
          body { background: white; }
          .brief-section { break-inside: avoid; }
        }
      `}</style>

      <div className="no-print flex items-center justify-between border-b border-hairline bg-paper-raised px-8 py-4">
        <button onClick={() => navigate(`/cases/${caseId}`)} className="text-sm text-ink underline">
          ← Back to case
        </button>
        <button
          onClick={() => window.print()}
          className="rounded-sm bg-ink px-4 py-2 text-sm font-medium text-paper hover:opacity-90"
        >
          Print
        </button>
      </div>

      <div className="mx-auto max-w-3xl px-8 py-10">
        <p className="text-xs uppercase tracking-wide text-slate">Investigation Brief</p>
        <h1 className="mt-1 font-display text-3xl font-semibold text-ink">{brief.project_title}</h1>
        <p className="mt-1 font-mono text-sm text-slate">{brief.project_code}</p>

        {/* Project Information */}
        <section className="brief-section mt-8 border-t border-hairline pt-6">
          <h2 className="font-display text-lg font-semibold text-ink">Project Information</h2>
          <dl className="mt-2 grid grid-cols-2 gap-x-8 gap-y-1 text-sm">
            <div className="flex justify-between border-b border-hairline py-1">
              <dt className="text-slate">Project code</dt>
              <dd className="font-mono text-ink">{brief.project_code}</dd>
            </div>
            <div className="flex justify-between border-b border-hairline py-1">
              <dt className="text-slate">Title</dt>
              <dd className="text-ink">{brief.project_title}</dd>
            </div>
          </dl>
        </section>

        {/* Risk Assessment */}
        <section className="brief-section mt-6 border-t border-hairline pt-6">
          <h2 className="font-display text-lg font-semibold text-ink">Risk Assessment</h2>
          <p className="mt-2 text-sm text-ink">
            {brief.risk_score != null ? (
              <>
                Score <span className="font-mono font-semibold">{brief.risk_score.toFixed(0)}</span> —{' '}
                <span className="font-medium capitalize">{brief.risk_level}</span> risk
              </>
            ) : (
              'Not yet scored.'
            )}
          </p>
        </section>

        {/* Why Flagged */}
        <section className="brief-section mt-6 border-t border-hairline pt-6">
          <h2 className="font-display text-lg font-semibold text-ink">Why Flagged</h2>
          {brief.top_factors.length === 0 && topFlagged.length === 0 ? (
            <p className="mt-2 text-sm text-slate">No individual factor contributed meaningfully.</p>
          ) : (
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-ink-soft">
              {(topFlagged.length > 0 ? topFlagged.map((f) => f.explanation) : brief.top_factors).map((text, i) => (
                <li key={i}>{text}</li>
              ))}
            </ol>
          )}
        </section>

        {/* Financial / Execution / AI-Anomaly Findings */}
        {activeGroups.map((group) => (
          <section key={group.title} className="brief-section mt-6 border-t border-hairline pt-6">
            <h2 className="font-display text-lg font-semibold text-ink">{group.title}</h2>
            <div className="mt-2 space-y-2">
              {group.factors.map((f) => (
                <div key={f.factor_code} className="text-sm">
                  <p className="font-medium text-ink">{FACTOR_LABELS[f.factor_code] || f.factor_code}</p>
                  <p className="text-ink-soft">{f.explanation}</p>
                </div>
              ))}
            </div>
          </section>
        ))}

        {/* Evidence */}
        <section className="brief-section mt-6 border-t border-hairline pt-6">
          <h2 className="font-display text-lg font-semibold text-ink">Evidence</h2>
          {caseDetail.evidence.length === 0 ? (
            <p className="mt-2 text-sm text-slate">No evidence has been attached to this case yet.</p>
          ) : (
            <div className="mt-2 space-y-2">
              {caseDetail.evidence.map((e, i) => (
                <div key={i} className="border-b border-hairline pb-2 text-sm last:border-b-0">
                  <p className="text-xs font-medium uppercase text-slate">{e.evidence_category}</p>
                  <p className="text-ink-soft">{e.description}</p>
                  {e.file_reference && <p className="font-mono text-xs text-slate">{e.file_reference}</p>}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Recommended Review Actions */}
        <section className="brief-section mt-6 border-t border-hairline pt-6">
          <h2 className="font-display text-lg font-semibold text-ink">Recommended Review Actions</h2>
          <p className="mt-2 text-sm text-ink">
            Verification priority: <span className="font-semibold">{brief.recommended_verification_priority}</span>
          </p>
          {activeGroups.length > 0 && (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-soft">
              {activeGroups.map((g) => (
                <li key={g.title}>{GROUP_GUIDANCE[g.title]}</li>
              ))}
            </ul>
          )}
        </section>

        {/* Case Information */}
        <section className="brief-section mt-6 border-t border-hairline pt-6">
          <h2 className="font-display text-lg font-semibold text-ink">Case Information</h2>
          <dl className="mt-2 space-y-1 text-sm">
            <div className="flex justify-between border-b border-hairline py-1">
              <dt className="text-slate">Case ID</dt>
              <dd className="font-mono text-ink">{caseDetail.id}</dd>
            </div>
            <div className="flex justify-between border-b border-hairline py-1">
              <dt className="text-slate">Current status</dt>
              <dd className="text-ink">{STATUS_LABELS[caseDetail.status] || caseDetail.status}</dd>
            </div>
            <div className="flex justify-between border-b border-hairline py-1">
              <dt className="text-slate">Opened</dt>
              <dd className="text-ink">{new Date(caseDetail.created_at).toLocaleString()}</dd>
            </div>
          </dl>
        </section>

        {/* Audit / Decision History */}
        <section className="brief-section mt-6 border-t border-hairline pt-6">
          <h2 className="font-display text-lg font-semibold text-ink">Audit / Decision History</h2>
          {caseDetail.status_history.length === 0 ? (
            <p className="mt-2 text-sm text-slate">No status changes recorded yet.</p>
          ) : (
            <div className="mt-2 space-y-2">
              {caseDetail.status_history.map((h, i) => (
                <div key={i} className="border-b border-hairline pb-2 text-xs last:border-b-0">
                  <p className="text-ink">
                    {h.from_status
                      ? `${STATUS_LABELS[h.from_status] || h.from_status} → ${STATUS_LABELS[h.to_status] || h.to_status}`
                      : `Created as ${STATUS_LABELS[h.to_status] || h.to_status}`}
                  </p>
                  <p className="text-slate">{h.remark}</p>
                  <p className="font-mono text-slate-light">{new Date(h.created_at).toLocaleString()}</p>
                </div>
              ))}
            </div>
          )}
        </section>

        <p className="mt-8 border-t border-hairline pt-6 text-xs italic text-slate">{brief.disclaimer}</p>
      </div>
    </div>
  )
}
