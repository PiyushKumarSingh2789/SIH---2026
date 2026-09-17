import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { fetchAnalyticsSummary } from '../api/projects'
import { QueryStateHandler } from '../components/ui/States'

function formatCrore(amount) {
  if (!amount) return '₹0'
  return `₹${(amount / 10000000).toFixed(2)} Cr`
}

const RISK_CHART_COLORS = { critical: '#dc2626', high: '#ea580c', medium: '#d97706', low: '#16a34a', unscored: '#94a3b8' }

function KpiCard({ label, value, sub }) {
  return (
    <div className="rounded-sm border border-hairline bg-card px-5 py-4">
      <p className="text-xs text-slate">{label}</p>
      <p className="mt-1 font-display text-2xl font-semibold text-ink">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-slate">{sub}</p>}
    </div>
  )
}

export default function PortfolioAnalyticsPage() {
  const { data: summary, isLoading, error, refetch } = useQuery({
    queryKey: ['analytics-summary'],
    queryFn: fetchAnalyticsSummary,
  })

  const utilization = summary && summary.total_sanctioned_amount > 0
    ? (summary.total_utilized_amount / summary.total_sanctioned_amount) * 100
    : 0

  const riskChartData = summary
    ? Object.entries(summary.risk_level_counts).map(([level, count]) => ({ level, count }))
    : []

  const statusChartData = summary
    ? Object.entries(summary.status_counts).map(([status, count]) => ({ status: status.replace(/_/g, ' '), count }))
    : []

  const stateChartData = summary?.state_breakdown || []

  return (
    <div className="mx-auto max-w-6xl px-8 py-8">
      <h1 className="font-display text-2xl font-semibold text-ink">Portfolio Analytics</h1>
      <p className="mb-6 mt-1 text-sm text-slate">
        Aggregated across every project in your scope, from the most recent risk run.
      </p>

      <QueryStateHandler isLoading={isLoading} error={error} data={summary} onRetry={refetch}>
        {summary && (
          <>
            <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <KpiCard label="Total projects" value={summary.total_projects.toLocaleString()} />
              <KpiCard label="Sanctioned amount" value={formatCrore(summary.total_sanctioned_amount)} />
              <KpiCard label="Utilized amount" value={formatCrore(summary.total_utilized_amount)} />
              <KpiCard label="Utilization" value={`${utilization.toFixed(0)}%`} />
            </div>

            <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div className="rounded-sm border border-hairline bg-card p-5">
                <p className="mb-3 text-sm font-medium text-ink">Risk distribution</p>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={riskChartData} layout="vertical" margin={{ left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 12 }} />
                    <YAxis type="category" dataKey="level" tick={{ fontSize: 12 }} width={70} />
                    <Tooltip />
                    <Bar dataKey="count" radius={[0, 3, 3, 0]}>
                      {riskChartData.map((entry) => (
                        <Cell key={entry.level} fill={RISK_CHART_COLORS[entry.level] || '#64748b'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="rounded-sm border border-hairline bg-card p-5">
                <p className="mb-3 text-sm font-medium text-ink">Project status</p>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={statusChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="status" tick={{ fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={50} />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#2563eb" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {stateChartData.length > 0 && (
              <div className="rounded-sm border border-hairline bg-card p-5">
                <p className="mb-3 text-sm font-medium text-ink">Projects by state</p>
                <ResponsiveContainer width="100%" height={Math.max(180, stateChartData.length * 32)}>
                  <BarChart data={stateChartData} layout="vertical" margin={{ left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 12 }} />
                    <YAxis type="category" dataKey="state" tick={{ fontSize: 12 }} width={110} />
                    <Tooltip formatter={(value, name) => (name === 'total_sanctioned_amount' ? formatCrore(value) : value)} />
                    <Bar dataKey="project_count" name="Projects" fill="#1e3a5f" radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {summary.last_risk_run_at && (
              <p className="mt-6 text-xs text-slate">
                Based on the risk run completed {new Date(summary.last_risk_run_at).toLocaleString()}.
              </p>
            )}
          </>
        )}
      </QueryStateHandler>
    </div>
  )
}
