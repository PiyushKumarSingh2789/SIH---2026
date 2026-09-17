import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { fetchAlerts, fetchAnalyticsSummary, recomputeRisk } from '../api/projects'
import { useAuth } from '../auth/AuthContext'
import { useToast } from '../components/ui/Toast'
import { QueryStateHandler, EmptyState } from '../components/ui/States'
import RiskBadge from '../components/RiskBadge'

function formatCrore(amount) {
  if (!amount) return '₹0'
  return `₹${(amount / 10000000).toFixed(2)} Cr`
}

const RISK_CHART_COLORS = { critical: '#dc2626', high: '#ea580c', medium: '#d97706', low: '#16a34a' }

export default function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const canRecompute = user?.roles?.some((r) => ['system_administrator', 'ministry_administrator'].includes(r))

  const { data: summary, isLoading: summaryLoading, error: summaryError, refetch } = useQuery({
    queryKey: ['analytics-summary'],
    queryFn: fetchAnalyticsSummary,
  })

  const { data: topAlerts } = useQuery({
    queryKey: ['alerts', 'high'],
    queryFn: () => fetchAlerts('high', 8),
  })

  const recomputeMutation = useMutation({
    mutationFn: recomputeRisk,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analytics-summary'] })
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
      showToast('Risk scores recomputed successfully.')
    },
    onError: () => showToast('Recompute failed. Check your permissions and try again.', 'error'),
  })

  const counts = summary?.risk_level_counts || { critical: 0, high: 0, medium: 0, low: 0, unscored: 0 }
  const statusCounts = summary?.status_counts || {}

  const riskChartData = [
    { name: 'Critical', value: counts.critical || 0, key: 'critical' },
    { name: 'High', value: counts.high || 0, key: 'high' },
    { name: 'Medium', value: counts.medium || 0, key: 'medium' },
    { name: 'Low', value: counts.low || 0, key: 'low' },
  ]
  const hasRiskData = riskChartData.some((d) => d.value > 0)

  const statusChartData = Object.entries(statusCounts).map(([status, count]) => ({
    name: status.replace(/_/g, ' '),
    count,
  }))

  const financeChartData = summary
    ? [
        { name: 'Sanctioned', amount: summary.total_sanctioned_amount / 10000000 },
        { name: 'Utilized', amount: summary.total_utilized_amount / 10000000 },
      ]
    : []

  return (
    <div className="mx-auto max-w-5xl px-8 py-8">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-ink">Executive Dashboard</h1>
          <p className="mt-1 text-sm text-slate">What requires attention right now, across your assigned scope.</p>
          {summary?.last_risk_run_at && (
            <p className="mt-1 text-xs text-slate-light">
              Last risk run: {new Date(summary.last_risk_run_at).toLocaleString()}
            </p>
          )}
        </div>
        {canRecompute && (
          <button
            onClick={() => recomputeMutation.mutate()}
            disabled={recomputeMutation.isPending}
            className="rounded-sm bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {recomputeMutation.isPending ? 'Recomputing…' : 'Recompute risk scores'}
          </button>
        )}
      </div>

      <QueryStateHandler isLoading={summaryLoading} error={summaryError} data={summary} onRetry={refetch}>
        {summary && (
          <>
            {/* Portfolio totals */}
            <div className="mb-4 grid grid-cols-3 gap-px overflow-hidden rounded-sm border border-hairline bg-hairline">
              <div className="bg-paper-raised px-5 py-4">
                <p className="text-xs font-medium text-slate">Total Projects</p>
                <p className="mt-1 font-mono text-2xl font-semibold text-ink">{summary.total_projects.toLocaleString()}</p>
              </div>
              <div className="bg-paper-raised px-5 py-4">
                <p className="text-xs font-medium text-slate">Total Sanctioned</p>
                <p className="mt-1 font-mono text-2xl font-semibold text-ink">{formatCrore(summary.total_sanctioned_amount)}</p>
              </div>
              <div className="bg-paper-raised px-5 py-4">
                <p className="text-xs font-medium text-slate">Total Utilized</p>
                <p className="mt-1 font-mono text-2xl font-semibold text-ink">{formatCrore(summary.total_utilized_amount)}</p>
              </div>
            </div>

            {/* Risk distribution - clickable, each navigates to the Risk Queue pre-filtered */}
            <div className="mb-8 grid grid-cols-4 gap-px overflow-hidden rounded-sm border border-hairline bg-hairline">
              {[
                ['critical', 'Critical Risk'],
                ['high', 'High Risk'],
                ['medium', 'Medium Risk'],
                ['low', 'Low Risk'],
              ].map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => navigate(`/queue?level=${key}`)}
                  className="bg-paper-raised px-5 py-4 text-left transition-colors hover:bg-paper"
                >
                  <p className="text-xs font-medium text-slate">{label}</p>
                  <p className="mt-1 font-mono text-3xl font-semibold text-ink">{counts[key] || 0}</p>
                </button>
              ))}
            </div>

            {/* Charts */}
            <div className="mb-8 grid grid-cols-2 gap-4">
              <div className="rounded-sm border border-hairline bg-paper-raised p-5">
                <h3 className="mb-3 text-sm font-semibold text-ink">Risk distribution</h3>
                {hasRiskData ? (
                  <ResponsiveContainer width="100%" height={220}>
                    <PieChart>
                      <Pie
                        data={riskChartData}
                        dataKey="value"
                        nameKey="name"
                        innerRadius={55}
                        outerRadius={85}
                        paddingAngle={2}
                        onClick={(d) => navigate(`/queue?level=${d.key}`)}
                        style={{ cursor: 'pointer' }}
                      >
                        {riskChartData.map((entry) => (
                          <Cell key={entry.key} fill={RISK_CHART_COLORS[entry.key]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value, name) => [`${value} projects`, name]} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <EmptyState title="No scored projects" description="Run a recompute to see the risk distribution." />
                )}
              </div>

              <div className="rounded-sm border border-hairline bg-paper-raised p-5">
                <h3 className="mb-3 text-sm font-semibold text-ink">Sanctioned vs utilized (₹ Cr)</h3>
                {financeChartData.length > 0 && summary.total_sanctioned_amount > 0 ? (
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={financeChartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                      <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={{ stroke: '#e2e8f0' }} />
                      <YAxis tick={{ fontSize: 12, fill: '#64748b' }} axisLine={{ stroke: '#e2e8f0' }} />
                      <Tooltip formatter={(v) => `₹${v.toFixed(1)} Cr`} />
                      <Bar dataKey="amount" fill="#2563eb" radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <EmptyState title="No financial data yet" />
                )}
              </div>
            </div>

            {/* Status distribution chart */}
            <div className="mb-8 rounded-sm border border-hairline bg-paper-raised p-5">
              <h3 className="mb-3 text-sm font-semibold text-ink">Project status</h3>
              {statusChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={statusChartData} layout="vertical" margin={{ left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={{ stroke: '#e2e8f0' }} />
                    <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: '#64748b' }} width={90} axisLine={{ stroke: '#e2e8f0' }} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#1e3a5f" radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <EmptyState title="No projects yet" />
              )}
            </div>

            <h2 className="mb-3 font-display text-lg font-semibold text-ink">Top priorities</h2>
            {!topAlerts || topAlerts.length === 0 ? (
              <EmptyState title="No critical or high-risk projects" description="The current run found nothing that needs immediate attention." />
            ) : (
              <div className="overflow-hidden rounded-sm border border-hairline bg-paper-raised">
                {topAlerts.map((a) => (
                  <Link
                    key={a.project_id}
                    to={`/projects/${a.project_id}`}
                    className="flex items-center justify-between border-b border-hairline px-5 py-3 last:border-b-0 hover:bg-paper"
                  >
                    <div>
                      <p className="text-sm font-medium text-ink">{a.title}</p>
                      <p className="font-mono text-xs text-slate">{a.project_code}</p>
                      {a.top_factor_explanation && <p className="mt-1 text-xs text-slate">{a.top_factor_explanation}</p>}
                    </div>
                    <RiskBadge level={a.risk_level} score={a.final_score} />
                  </Link>
                ))}
              </div>
            )}
          </>
        )}
      </QueryStateHandler>
    </div>
  )
}
