const LEVEL_STYLES = {
  low: { bg: 'bg-risk-low-bg', text: 'text-risk-low', label: 'Low' },
  medium: { bg: 'bg-risk-medium-bg', text: 'text-risk-medium', label: 'Medium' },
  high: { bg: 'bg-risk-high-bg', text: 'text-risk-high', label: 'High' },
  critical: { bg: 'bg-risk-critical-bg', text: 'text-risk-critical', label: 'Critical' },
}

export default function RiskBadge({ level, score }) {
  const style = LEVEL_STYLES[level?.toLowerCase()] || LEVEL_STYLES.low
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-sm px-2 py-0.5 text-xs font-medium ${style.bg} ${style.text}`}>
      <span className={`h-1.5 w-1.5 ${style.text.replace('text-', 'bg-')}`} />
      {style.label}
      {typeof score === 'number' && <span className="font-mono">({score.toFixed(0)})</span>}
    </span>
  )
}
