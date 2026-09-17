import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  fetchProjectRisk, fetchProjectBenchmark, fetchProjectDuplicates,
  fetchProjectRelationships, fetchProjectCompliance,
} from '../api/projects'
import { createCase } from '../api/cases'
import RiskBadge from '../components/RiskBadge'
import { EmptyState } from '../components/ui/States'

const FACTOR_LABELS = {
  COST_DEVIATION: 'Cost Deviation',
  PROGRESS_EXPENDITURE_MISMATCH: 'Progress–Expenditure Mismatch',
  DELAY_STALL: 'Delay / Stall',
  PAYMENT_ANOMALY: 'Payment Anomaly',
  DUPLICATE_SIMILARITY: 'Duplicate Similarity',
  PEER_DEVIATION: 'Peer Deviation',
  ML_ANOMALY: 'ML Anomaly (Isolation Forest)',
}

function EvidenceRow({ label, value }) {
  if (value === null || value === undefined) return null
  const display = typeof value === 'number' ? Number(value.toFixed(2)).toString() : String(value)
  return (
    <div className="flex justify-between border-b border-hairline py-1.5 text-xs last:border-b-0">
      <span className="text-slate">{label.replace(/_/g, ' ')}</span>
      <span className="font-mono text-ink">{display}</span>
    </div>
  )
}

// Same 4-band thresholds as the backend's RiskLevel (0-29 low / 30-59 medium / 60-79 high / 80-100
// critical) -- used here to color-code individual factor severity, not just the overall score.
function severityStyle(score) {
  if (score >= 80) return { text: 'text-risk-critical', bar: 'bg-risk-critical' }
  if (score >= 60) return { text: 'text-risk-high', bar: 'bg-risk-high' }
  if (score >= 30) return { text: 'text-risk-medium', bar: 'bg-risk-medium' }
  return { text: 'text-risk-low', bar: 'bg-risk-low' }
}

// STEP 1: "Why was this project flagged?" -- automatically picks the 2-3 strongest
// *already-computed* factors (by contribution, which the page already sorts by) and
// surfaces them prominently. No new data, no new endpoint -- purely a presentation
// layer over risk.factors, which the Factor Evidence section below already renders in full.
function WhyFlaggedSection({ factors }) {
  const top = factors.filter((f) => f.contribution > 0).slice(0, 3)

  return (
    <div className="mb-8 rounded-sm border-2 border-ink bg-paper-raised p-5">
      <h2 className="font-display text-lg font-semibold text-ink">Why was this project flagged?</h2>
      {top.length === 0 ? (
        <p className="mt-2 text-sm text-slate">
          No individual factor contributed meaningfully to this project's score.
        </p>
      ) : (
        <ol className="mt-3 space-y-4">
          {top.map((f, i) => {
            const style = severityStyle(f.normalized_score)
            return (
              <li key={f.factor_code} className="flex gap-3">
                <span className={`font-display text-xl font-semibold leading-none ${style.text}`}>{i + 1}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5">
                    <p className="text-sm font-semibold text-ink">{FACTOR_LABELS[f.factor_code] || f.factor_code}</p>
                    <p className="font-mono text-xs text-slate">+{f.contribution.toFixed(1)} pts</p>
                  </div>
                  <p className="mt-0.5 text-sm text-ink-soft">{f.explanation}</p>
                  <div className="mt-1.5 h-1 w-full max-w-xs bg-hairline">
                    <div className={`h-full ${style.bar}`} style={{ width: `${Math.min(100, f.normalized_score)}%` }} />
                  </div>
                </div>
              </li>
            )
          })}
        </ol>
      )}
    </div>
  )
}

// STEP 2: Early Warning. Built entirely from evidence already embedded in existing factors --
// no new endpoint, no invented dates:
//   - "current progress" comes from PROGRESS_EXPENDITURE_MISMATCH's evidence (when that factor
//     was computed for this project).
//   - "expected progress" / "progress gap" can ONLY be derived when PEER_DEVIATION also ran AND
//     its progress_lag metric qualified (it needs a peer group of >=10 comparable projects) --
//     expected = current + progress_lag. If that isn't available, we don't guess: we fall back
//     to whatever DELAY_STALL evidence exists, which is the strongest signal still available.
//   - Projected completion DATE is never shown: nothing in the API returns expected/actual
//     completion dates today, so a date would have to be invented. Per spec, we show the
//     strongest available evidence instead.
function deriveEarlyWarning(factors) {
  const mismatch = factors.find((f) => f.factor_code === 'PROGRESS_EXPENDITURE_MISMATCH')
  const stall = factors.find((f) => f.factor_code === 'DELAY_STALL')
  const peerDeviation = factors.find((f) => f.factor_code === 'PEER_DEVIATION')

  const currentProgress = mismatch?.evidence?.physical_progress_percent ?? null
  const lagMetric = peerDeviation?.evidence?.metrics?.find((m) => m.metric === 'progress_lag')
  const progressLag = lagMetric?.value ?? null
  const expectedProgress = currentProgress != null && progressLag != null ? currentProgress + progressLag : null
  const progressGap = expectedProgress != null ? currentProgress - expectedProgress : null

  return { currentProgress, expectedProgress, progressGap, stall }
}

function EarlyWarningSection({ factors }) {
  const { currentProgress, expectedProgress, progressGap, stall } = deriveEarlyWarning(factors)
  const stalled = stall?.evidence?.stalled === true
  const hasAnything = currentProgress != null || stall

  return (
    <div className="mb-8 rounded-sm border border-hairline bg-paper-raised p-5">
      <h2 className="font-display text-lg font-semibold text-ink">Early warning</h2>

      {!hasAnything && (
        <p className="mt-2 text-sm text-slate">
          Not enough progress history is available yet to assess early-warning signals for this project.
        </p>
      )}

      {expectedProgress != null && (
        <div className="mt-4 space-y-3">
          <div>
            <div className="flex justify-between text-xs text-slate">
              <span>Current progress</span>
              <span className="font-mono text-ink">{currentProgress.toFixed(0)}%</span>
            </div>
            <div className="mt-1 h-2 w-full bg-hairline">
              <div className="h-full bg-ink" style={{ width: `${Math.min(100, currentProgress)}%` }} />
            </div>
          </div>
          <div>
            <div className="flex justify-between text-xs text-slate">
              <span>Expected progress</span>
              <span className="font-mono text-ink">{expectedProgress.toFixed(0)}%</span>
            </div>
            <div className="mt-1 h-2 w-full bg-hairline">
              <div className="h-full bg-slate-light" style={{ width: `${Math.min(100, expectedProgress)}%` }} />
            </div>
          </div>
          <div className="flex justify-between border-t border-hairline pt-2 text-sm">
            <span className="text-slate">Progress gap</span>
            <span className={`font-mono font-medium ${progressGap < 0 ? 'text-risk-high' : 'text-risk-low'}`}>
              {progressGap > 0 ? '+' : ''}
              {progressGap.toFixed(0)} pts
            </span>
          </div>
        </div>
      )}

      {stall && (
        <div className={expectedProgress != null ? 'mt-4 border-t border-hairline pt-4' : 'mt-3'}>
          <p className="text-sm text-ink-soft">{stall.explanation}</p>
        </div>
      )}

      {hasAnything && (
        <p className={`mt-4 text-sm font-medium ${stalled ? 'text-risk-high' : 'text-risk-low'}`}>
          {stalled
            ? '⚠ Completion delay risk — execution has not moved meaningfully in the recent reporting window.'
            : expectedProgress != null && progressGap < -15
            ? '⚠ Behind expected pace for its stage.'
            : '✓ No stall or pace warning currently flagged.'}
        </p>
      )}
    </div>
  )
}

const RESULT_STYLES = {
  PASS: 'bg-risk-low-bg text-risk-low',
  WARNING: 'bg-risk-medium-bg text-risk-medium',
  FAIL: 'bg-risk-critical-bg text-risk-critical',
}

// Item 5 / item 13: duplicate candidates, embedded here rather than as a separate page since
// the data is inherently project-scoped -- a standalone "Duplicate Review" page would need a
// project picker to do anything, which is just this section with extra steps.
function DuplicateCandidatesSection({ projectId }) {
  const { data, isLoading } = useQuery({
    queryKey: ['project-duplicates', projectId],
    queryFn: () => fetchProjectDuplicates(projectId),
  })

  if (isLoading || !data || data.length === 0) return null

  return (
    <div className="mb-8 rounded-sm border border-hairline bg-paper-raised p-5">
      <h2 className="font-display text-lg font-semibold text-ink">Duplicate candidates</h2>
      <p className="mt-1 text-xs text-slate">Potential duplicate — requires review. Never a confirmed finding of fraud.</p>
      <div className="mt-3 space-y-3">
        {data.map((d) => (
          <div key={d.candidate_project_id} className="rounded-sm border border-hairline bg-card p-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-slate">{d.candidate_project_id.slice(0, 8)}…</span>
              <span className="rounded-sm bg-risk-medium-bg px-2 py-0.5 text-xs font-medium text-risk-medium">
                {(d.combined_score * 100).toFixed(0)}% similar — requires review
              </span>
            </div>
            <div className="mt-2 grid grid-cols-3 gap-3 text-xs text-slate">
              <span>Title similarity: <span className="font-mono text-ink-soft">{(d.text_similarity * 100).toFixed(0)}%</span></span>
              <span>Location proximity: <span className="font-mono text-ink-soft">{(d.geographic_similarity * 100).toFixed(0)}%</span></span>
              <span>Attributes: <span className="font-mono text-ink-soft">{(d.attribute_similarity * 100).toFixed(0)}%</span></span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// Item 8: minimal relationship view -- Project -> Agency -> Location -> Payments -> Related
// Projects, using GET /projects/{id}/relationships (plain SQL joins on existing foreign keys,
// no graph DB).
function RelationshipsSection({ projectId }) {
  const navigate = useNavigate()
  const { data, isLoading } = useQuery({
    queryKey: ['project-relationships', projectId],
    queryFn: () => fetchProjectRelationships(projectId),
  })

  if (isLoading || !data) return null
  const nodes = [
    { label: 'Project', value: data.project.title },
    { label: 'Agency', value: data.agency?.name || 'Not recorded' },
    { label: 'Location', value: data.location ? `${data.location.district}, ${data.location.state}` : 'Not recorded' },
    { label: 'Payments', value: `${data.payment_summary.count} payment(s)` },
  ]

  return (
    <div className="mb-8 rounded-sm border border-hairline bg-paper-raised p-5">
      <h2 className="font-display text-lg font-semibold text-ink">Relationship intelligence</h2>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        {nodes.map((n, i) => (
          <div key={n.label} className="flex items-center gap-2">
            <div className="rounded-sm border border-hairline bg-card px-3 py-2">
              <p className="text-[10px] uppercase tracking-wide text-slate">{n.label}</p>
              <p className="text-ink">{n.value}</p>
            </div>
            {i < nodes.length - 1 && <span className="text-slate">→</span>}
          </div>
        ))}
      </div>
      {data.related_projects.length > 0 && (
        <div className="mt-4">
          <p className="mb-2 text-xs uppercase tracking-wide text-slate">Related projects</p>
          <div className="space-y-1.5">
            {data.related_projects.map((p) => (
              <button
                key={p.id}
                onClick={() => navigate(`/projects/${p.id}`)}
                className="block w-full rounded-sm border border-hairline bg-card px-3 py-2 text-left text-sm hover:border-secondary"
              >
                <span className="font-mono text-xs text-slate">{p.project_code}</span>
                <span className="ml-2 text-ink">{p.title}</span>
                <span className="ml-2 text-xs capitalize text-slate">({p.relationship_type.replace(/_/g, ' ')})</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// Item 9 / item 13: per-project compliance summary. The full cross-project view lives at
// /compliance -- this is a compact one-project echo of the same checks for in-context review.
function ComplianceSection({ projectId }) {
  const { data, isLoading } = useQuery({
    queryKey: ['project-compliance', projectId],
    queryFn: () => fetchProjectCompliance(projectId),
  })

  if (isLoading || !data || data.length === 0) return null
  const flagged = data.filter((c) => c.result !== 'PASS')

  return (
    <div className="mb-8 rounded-sm border border-hairline bg-paper-raised p-5">
      <h2 className="font-display text-lg font-semibold text-ink">Compliance checks</h2>
      <div className="mt-3 flex flex-wrap gap-2">
        {data.map((c) => (
          <span key={c.check_code} className={`rounded-sm px-2 py-1 text-xs font-medium ${RESULT_STYLES[c.result]}`}>
            {c.check_code}: {c.result}
          </span>
        ))}
      </div>
      {flagged.length === 0 && <p className="mt-2 text-xs text-slate">All checks pass for this project.</p>}
    </div>
  )
}

// Item 13: peer benchmark, embedded next to the score it explains.
function BenchmarkSection({ projectId }) {
  const { data, isLoading } = useQuery({
    queryKey: ['project-benchmark', projectId],
    queryFn: () => fetchProjectBenchmark(projectId),
    retry: false,
  })

  if (isLoading || !data) return null

  return (
    <div className="mb-8 rounded-sm border border-hairline bg-paper-raised p-5">
      <h2 className="font-display text-lg font-semibold text-ink">Peer benchmark</h2>
      <p className="mt-1 text-xs text-slate">
        Compared against {data.sample_count} peer project(s) with the same work type
        {data.group_value ? ` in ${data.group_value}` : ''}.
      </p>
      <div className="mt-3 grid grid-cols-3 gap-4 text-sm">
        <div>
          <p className="text-xs text-slate">This project</p>
          <p className="font-mono text-ink">₹{(data.project_cost / 100000).toFixed(1)}L</p>
        </div>
        <div>
          <p className="text-xs text-slate">Peer median</p>
          <p className="font-mono text-ink-soft">₹{(data.median_cost / 100000).toFixed(1)}L</p>
        </div>
        <div>
          <p className="text-xs text-slate">Peer range (IQR)</p>
          <p className="font-mono text-ink-soft">₹{(data.iqr_low / 100000).toFixed(1)}L – ₹{(data.iqr_high / 100000).toFixed(1)}L</p>
        </div>
      </div>
    </div>
  )
}

export default function ProjectProfilePage() {
  const { projectId } = useParams()
  const navigate = useNavigate()

  const { data: risk, isLoading, error } = useQuery({
    queryKey: ['project-risk', projectId],
    queryFn: () => fetchProjectRisk(projectId),
  })

  const caseMutation = useMutation({
    mutationFn: () => createCase(projectId),
    onSuccess: (c) => navigate(`/cases/${c.id}`),
  })

  if (isLoading) return <div className="px-8 py-8 text-sm text-slate">Loading…</div>
  if (error) {
    if (error.response?.status === 404) {
      return (
        <div className="mx-auto max-w-4xl px-8 py-8">
          <EmptyState title="Not yet scored" description="No risk score for this project yet — run a recompute from the Dashboard." />
        </div>
      )
    }
    return (
      <div className="px-8 py-8">
        <p className="text-sm text-risk-critical">
          {error.response?.status === 403
            ? 'This project is outside your assigned scope.'
            : 'Could not load this project.'}
        </p>
      </div>
    )
  }

  const sortedFactors = [...(risk.factors || [])].sort((a, b) => b.contribution - a.contribution)

  return (
    <div className="mx-auto max-w-4xl px-8 py-8">
      <div className="mb-2 flex items-start justify-between">
        <div>
          <p className="font-mono text-xs text-slate">{risk.project_code}</p>
          <h1 className="font-display text-2xl font-semibold text-ink">Project Risk Profile</h1>
        </div>
        <RiskBadge level={risk.risk_level} score={risk.final_score} />
      </div>

      <div className="mb-6 flex gap-6 border-b border-hairline pb-4 text-xs text-slate">
        <span>Evidence completeness: <span className="font-mono text-ink">{risk.evidence_completeness_percent}%</span></span>
        <span>Factors computed: <span className="font-mono text-ink">{risk.factors_computed_count} of 7</span></span>
        <span>Engine version: <span className="font-mono text-ink">{risk.engine_version}</span></span>
      </div>

      <div className="mb-6 rounded-sm border border-hairline bg-paper-raised p-4">
        <p className="text-sm font-medium text-ink">
          Risk score indicates review priority; it does not establish fraud.
        </p>
        <p className="mt-1 text-sm text-ink-soft">
          It reflects {risk.factors_computed_count} of 7 possible risk factors, each shown below with the
          evidence behind it.
        </p>
        <button
          onClick={() => caseMutation.mutate()}
          disabled={caseMutation.isPending}
          className="mt-3 rounded-sm bg-ink px-4 py-2 text-sm font-medium text-paper hover:opacity-90 disabled:opacity-50"
        >
          {caseMutation.isPending ? 'Opening…' : 'Open investigation case'}
        </button>
        {caseMutation.isError && (
          <p className="mt-2 text-xs text-risk-critical">Could not open a case — it may already exist, or this project is out of scope.</p>
        )}
      </div>

      <WhyFlaggedSection factors={sortedFactors} />

      <h2 className="mb-3 font-display text-lg font-semibold text-ink">Factor evidence</h2>
      <div className="mb-8 space-y-3">
        {sortedFactors.map((f) => (
          <div key={f.factor_code} className="rounded-sm border border-hairline bg-paper-raised p-4">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-sm font-semibold text-ink">{FACTOR_LABELS[f.factor_code] || f.factor_code}</p>
              <p className="font-mono text-xs text-slate">
                {f.normalized_score.toFixed(0)} × {(f.weight * 100).toFixed(0)}% = {f.contribution.toFixed(1)} pts
              </p>
            </div>
            <p className="mb-3 text-sm text-ink-soft">{f.explanation}</p>
            <details className="text-xs">
              <summary className="cursor-pointer text-slate hover:text-ink">Show underlying evidence</summary>
              <div className="mt-2 rounded-sm bg-paper p-3">
                {Object.entries(f.evidence || {}).map(([k, v]) => (
                  <EvidenceRow key={k} label={k} value={v} />
                ))}
              </div>
            </details>
          </div>
        ))}
        {sortedFactors.length === 0 && (
          <p className="rounded-sm border border-hairline bg-paper-raised px-5 py-6 text-sm text-slate">
            No factors could be computed for this project — likely missing data (see import validation warnings).
          </p>
        )}
      </div>

      <EarlyWarningSection factors={sortedFactors} />

      <BenchmarkSection projectId={projectId} />
      <DuplicateCandidatesSection projectId={projectId} />
      <RelationshipsSection projectId={projectId} />
      <ComplianceSection projectId={projectId} />
    </div>
  )
}
