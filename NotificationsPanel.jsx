import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchAlerts } from '../api/projects'
import RiskBadge from './RiskBadge'

export default function NotificationsPanel() {
  const [open, setOpen] = useState(false)
  const containerRef = useRef(null)
  const navigate = useNavigate()

  const { data: alerts } = useQuery({
    queryKey: ['notifications-alerts'],
    queryFn: () => fetchAlerts('medium', 15),
    refetchInterval: 60_000,
  })

  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const count = alerts?.length || 0
  const criticalCount = alerts?.filter((a) => a.risk_level === 'critical').length || 0

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative flex h-8 w-8 items-center justify-center rounded-sm border border-hairline bg-paper text-ink-soft hover:border-secondary hover:text-ink"
        aria-label="Notifications"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        {count > 0 && (
          <span
            className={`absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-semibold text-white ${
              criticalCount > 0 ? 'bg-risk-critical' : 'bg-risk-high'
            }`}
          >
            {count > 9 ? '9+' : count}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full z-40 mt-1 w-96 max-h-96 overflow-y-auto rounded-sm border border-hairline bg-card shadow-md">
          <p className="border-b border-hairline px-4 py-2.5 text-sm font-medium text-ink">
            Attention needed {count > 0 && <span className="text-slate">({count})</span>}
          </p>
          {count === 0 && <p className="px-4 py-6 text-center text-sm text-slate">No medium-or-higher alerts right now.</p>}
          {alerts?.map((a) => (
            <button
              key={a.project_id}
              onClick={() => {
                setOpen(false)
                navigate(`/projects/${a.project_id}`)
              }}
              className="block w-full border-b border-hairline px-4 py-3 text-left last:border-b-0 hover:bg-paper"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-xs text-slate">{a.project_code}</span>
                <RiskBadge level={a.risk_level} score={a.final_score} />
              </div>
              <p className="mt-1 truncate text-sm text-ink">{a.title}</p>
              {a.top_factor_explanation && (
                <p className="mt-0.5 truncate text-xs text-slate">{a.top_factor_explanation}</p>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
