import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchCase, changeCaseStatus, addCaseComment, addCaseEvidence } from '../api/cases'

const ALL_STATUSES = [
  'ai_flagged', 'under_review', 'field_verification_requested', 'field_verification_completed',
  'decision_pending', 'no_issue_closed', 'irregularity_escalated', 'action_taken',
  'inconclusive_reverify', 'closed',
]

const EVIDENCE_CATEGORIES = ['financial', 'execution', 'field', 'ai', 'public']

export default function CaseDetailPage() {
  const { caseId } = useParams()
  const queryClient = useQueryClient()
  const [newStatus, setNewStatus] = useState('')
  const [remark, setRemark] = useState('')
  const [comment, setComment] = useState('')
  const [statusError, setStatusError] = useState('')
  const [evidenceCategory, setEvidenceCategory] = useState('field')
  const [evidenceDescription, setEvidenceDescription] = useState('')
  const [evidenceFileRef, setEvidenceFileRef] = useState('')

  const { data: caseDetail, isLoading } = useQuery({ queryKey: ['case', caseId], queryFn: () => fetchCase(caseId) })

  const statusMutation = useMutation({
    mutationFn: () => changeCaseStatus(caseId, newStatus, remark),
    onSuccess: () => {
      setRemark('')
      setNewStatus('')
      setStatusError('')
      queryClient.invalidateQueries({ queryKey: ['case', caseId] })
    },
    onError: (err) => setStatusError(err.response?.data?.detail || 'Transition failed.'),
  })

  const commentMutation = useMutation({
    mutationFn: () => addCaseComment(caseId, comment),
    onSuccess: () => {
      setComment('')
      queryClient.invalidateQueries({ queryKey: ['case', caseId] })
    },
  })

  const evidenceMutation = useMutation({
    mutationFn: () => addCaseEvidence(caseId, evidenceCategory, evidenceDescription, evidenceFileRef),
    onSuccess: () => {
      setEvidenceDescription('')
      setEvidenceFileRef('')
      queryClient.invalidateQueries({ queryKey: ['case', caseId] })
    },
  })

  if (isLoading) return <div className="px-8 py-8 text-sm text-slate">Loading…</div>
  if (!caseDetail) return null

  return (
    <div className="mx-auto max-w-3xl px-8 py-8">
      <p className="font-mono text-xs text-slate">{caseDetail.project_code}</p>
      <h1 className="mb-1 font-display text-2xl font-semibold text-ink">Case</h1>
      <p className="mb-6 text-sm text-ink-soft">Current status: <span className="font-medium">{caseDetail.status.replace(/_/g, ' ')}</span></p>

      <div className="mb-6 rounded-sm border border-hairline bg-paper-raised p-5">
        <p className="mb-2 text-sm font-medium text-ink">Change status</p>
        <div className="flex gap-2">
          <select
            value={newStatus}
            onChange={(e) => setNewStatus(e.target.value)}
            className="rounded-sm border border-hairline bg-paper px-2 py-2 text-sm outline-none focus:border-ink"
          >
            <option value="">Select new status…</option>
            {ALL_STATUSES.map((s) => (
              <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
            ))}
          </select>
        </div>
        <textarea
          value={remark}
          onChange={(e) => setRemark(e.target.value)}
          placeholder="Remark (required for every transition)"
          className="mt-2 w-full rounded-sm border border-hairline bg-paper px-3 py-2 text-sm outline-none focus:border-ink"
          rows={2}
        />
        {statusError && <p className="mt-1 text-xs text-risk-critical">{statusError}</p>}
        <button
          onClick={() => statusMutation.mutate()}
          disabled={!newStatus || !remark.trim() || statusMutation.isPending}
          className="mt-2 rounded-sm bg-ink px-4 py-2 text-sm font-medium text-paper hover:opacity-90 disabled:opacity-50"
        >
          Apply transition
        </button>
      </div>

      <div className="mb-6 rounded-sm border border-hairline bg-paper-raised p-5">
        <p className="mb-1 text-sm font-medium text-ink">Field verification</p>
        <p className="mb-3 text-xs text-slate">
          Requested: <span className="text-ink-soft">{['field_verification_requested', 'field_verification_completed', 'decision_pending', 'no_issue_closed', 'irregularity_escalated', 'action_taken', 'inconclusive_reverify', 'closed'].includes(caseDetail.status) ? 'Yes' : 'Not yet'}</span>
          {' · '}
          Completed: <span className="text-ink-soft">{['field_verification_completed', 'decision_pending', 'no_issue_closed', 'irregularity_escalated', 'action_taken', 'closed'].includes(caseDetail.status) ? 'Yes' : 'No'}</span>
        </p>
        {caseDetail.assignments?.length > 0 ? (
          <p className="mb-3 text-xs text-slate">
            Assigned officer: <span className="font-mono text-ink-soft">{caseDetail.assignments[caseDetail.assignments.length - 1].assigned_to_user_id.slice(0, 8)}…</span>
          </p>
        ) : (
          <p className="mb-3 text-xs text-slate">No officer assignment recorded.</p>
        )}
        {(caseDetail.state || caseDetail.district) && (
          <p className="mb-3 text-xs text-slate">
            Location: <span className="text-ink-soft">{caseDetail.district ? `${caseDetail.district}, ` : ''}{caseDetail.state || '—'}</span>
          </p>
        )}
        {caseDetail.evidence.filter((e) => e.evidence_category === 'field').length === 0 ? (
          <p className="text-xs text-slate">No field evidence submitted yet.</p>
        ) : (
          <div className="space-y-2">
            {caseDetail.evidence.filter((e) => e.evidence_category === 'field').map((e, i) => (
              <div key={i} className="rounded-sm border border-hairline bg-card p-2.5 text-xs">
                <p className="text-ink">{e.description}</p>
                {e.file_reference && <p className="font-mono text-slate">{e.file_reference}</p>}
                <p className="mt-1 font-mono text-slate-light">{new Date(e.created_at).toLocaleString()}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="mb-6 rounded-sm border border-hairline bg-paper-raised p-5">
        <p className="mb-2 text-sm font-medium text-ink">Evidence</p>
        {caseDetail.evidence.length === 0 && <p className="text-xs text-slate">No evidence recorded yet.</p>}
        <div className="space-y-2">
          {caseDetail.evidence.map((e, i) => (
            <div key={i} className="rounded-sm border border-hairline bg-card p-2.5 text-xs">
              <p className="font-medium capitalize text-ink">{e.evidence_category}</p>
              <p className="mt-0.5 text-ink-soft">{e.description}</p>
              {e.file_reference && <p className="mt-0.5 font-mono text-slate">{e.file_reference}</p>}
            </div>
          ))}
        </div>
        <div className="mt-3 flex gap-2">
          <select
            value={evidenceCategory}
            onChange={(e) => setEvidenceCategory(e.target.value)}
            className="rounded-sm border border-hairline bg-paper px-2 py-2 text-sm capitalize outline-none focus:border-ink"
          >
            {EVIDENCE_CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <input
            type="text"
            value={evidenceFileRef}
            onChange={(e) => setEvidenceFileRef(e.target.value)}
            placeholder="File reference (optional)"
            className="flex-1 rounded-sm border border-hairline bg-paper px-3 py-2 text-sm outline-none focus:border-ink"
          />
        </div>
        <textarea
          value={evidenceDescription}
          onChange={(e) => setEvidenceDescription(e.target.value)}
          placeholder="Describe this evidence…"
          className="mt-2 w-full rounded-sm border border-hairline bg-paper px-3 py-2 text-sm outline-none focus:border-ink"
          rows={2}
        />
        <button
          onClick={() => evidenceMutation.mutate()}
          disabled={!evidenceDescription.trim() || evidenceMutation.isPending}
          className="mt-2 rounded-sm border border-ink px-4 py-2 text-sm font-medium text-ink hover:bg-ink hover:text-paper disabled:opacity-50"
        >
          Add evidence
        </button>
      </div>

      <div className="mb-6 rounded-sm border border-hairline bg-paper-raised p-5">
        <p className="mb-1 text-sm font-medium text-ink">Investigation brief</p>
        <p className="mb-3 text-xs text-slate">
          A polished, print-friendly summary of this case — project information, risk assessment, why it
          was flagged, findings, evidence, and recommended actions.
        </p>
        <Link
          to={`/cases/${caseId}/brief`}
          className="inline-block rounded-sm bg-ink px-4 py-2 text-sm font-medium text-paper hover:opacity-90"
        >
          Open investigation brief
        </Link>
      </div>

      <div className="mb-6 rounded-sm border border-hairline bg-paper-raised p-5">
        <p className="mb-2 text-sm font-medium text-ink">Comments</p>
        {caseDetail.comments.map((c, i) => (
          <p key={i} className="mb-1 text-sm text-ink-soft">{c.body}</p>
        ))}
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Add a remark…"
          className="mt-2 w-full rounded-sm border border-hairline bg-paper px-3 py-2 text-sm outline-none focus:border-ink"
          rows={2}
        />
        <button
          onClick={() => commentMutation.mutate()}
          disabled={!comment.trim() || commentMutation.isPending}
          className="mt-2 rounded-sm border border-ink px-4 py-2 text-sm font-medium text-ink hover:bg-ink hover:text-paper disabled:opacity-50"
        >
          Add comment
        </button>
      </div>

      <div className="rounded-sm border border-hairline bg-paper-raised p-5">
        <p className="mb-2 text-sm font-medium text-ink">Audit trail</p>
        {caseDetail.status_history.map((h, i) => (
          <div key={i} className="border-b border-hairline py-2 text-xs last:border-b-0">
            <p className="text-ink">{h.from_status ? `${h.from_status} → ${h.to_status}` : `Created as ${h.to_status}`}</p>
            <p className="text-slate">{h.remark}</p>
            <p className="font-mono text-slate-light">{new Date(h.created_at).toLocaleString()}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
