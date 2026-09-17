import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'
import { Link } from 'react-router-dom'
import { fetchProjects } from '../api/projects'
import { LoadingState, ErrorState } from '../components/ui/States'
import 'leaflet/dist/leaflet.css'

const RISK_COLORS = { low: '#16a34a', medium: '#d97706', high: '#ea580c', critical: '#dc2626' }
const RISK_RANK = { critical: 3, high: 2, medium: 1, low: 0 }

// Coordinates are rounded to ~11m precision before grouping -- two projects at the "same site"
// in real data will rarely be bit-for-bit identical floats, but will agree at this precision.
function coordKey(lat, lon) {
  return `${lat.toFixed(4)},${lon.toFixed(4)}`
}

export default function MapPage() {
  const [minLevel, setMinLevel] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [unscoredOnly, setUnscoredOnly] = useState(false)
  const [search, setSearch] = useState('')
  const { data: projects, isLoading, error, refetch } = useQuery({
    queryKey: ['projects-map'],
    queryFn: () => fetchProjects({ limit: 200 }),
  })

  const statusOptions = useMemo(
    () => Array.from(new Set((projects || []).map((p) => p.status).filter(Boolean))).sort(),
    [projects]
  )

  const grouped = useMemo(() => {
    const withCoords = (projects || []).filter((p) => p.latitude != null && p.longitude != null)
    const bySearch = withCoords.filter(
      (p) =>
        !search ||
        p.title.toLowerCase().includes(search.toLowerCase()) ||
        p.project_code.toLowerCase().includes(search.toLowerCase())
    )
    const byLevel = minLevel === 'all' ? bySearch : bySearch.filter((p) => p.risk_level === minLevel)
    const byStatus = statusFilter === 'all' ? byLevel : byLevel.filter((p) => p.status === statusFilter)
    const byScored = unscoredOnly ? byStatus.filter((p) => !p.risk_level) : byStatus

    const groups = new Map()
    for (const p of byScored) {
      const key = coordKey(p.latitude, p.longitude)
      if (!groups.has(key)) groups.set(key, { latitude: p.latitude, longitude: p.longitude, projects: [] })
      groups.get(key).projects.push(p)
    }
    return Array.from(groups.values())
  }, [projects, minLevel, statusFilter, unscoredOnly, search])

  const totalVisible = grouped.reduce((sum, g) => sum + g.projects.length, 0)
  const center =
    grouped.length > 0 ? [grouped[0].latitude, grouped[0].longitude] : [22.9734, 78.6569]

  function markerColorFor(group) {
    // A cluster's marker reflects its MOST severe member -- an officer scanning the map should
    // never have a critical project hidden behind a low-risk one at the same coordinate.
    const worst = group.projects.reduce(
      (acc, p) => (RISK_RANK[p.risk_level] > RISK_RANK[acc] ? p.risk_level : acc),
      'low'
    )
    return RISK_COLORS[worst] || '#64748b'
  }

  return (
    <div className="flex h-screen flex-col">
      <div className="flex items-center justify-between gap-4 border-b border-hairline bg-paper-raised px-8 py-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-ink">Map Intelligence</h1>
          <p className="text-sm text-slate">{totalVisible} projects across {grouped.length} locations in view.</p>
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Search project code or title…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="rounded-sm border border-hairline bg-paper px-3 py-2 text-sm text-ink outline-none focus:border-accent"
          />
          <select
            value={minLevel}
            onChange={(e) => setMinLevel(e.target.value)}
            className="rounded-sm border border-hairline bg-paper px-3 py-2 text-sm text-ink outline-none focus:border-accent"
          >
            <option value="all">All risk levels</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-sm border border-hairline bg-paper px-3 py-2 text-sm capitalize text-ink outline-none focus:border-accent"
          >
            <option value="all">All statuses</option>
            {statusOptions.map((s) => (
              <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
            ))}
          </select>
          <label className="flex items-center gap-1.5 rounded-sm border border-hairline bg-paper px-3 py-2 text-sm text-ink-soft">
            <input type="checkbox" checked={unscoredOnly} onChange={(e) => setUnscoredOnly(e.target.checked)} />
            Unscored only
          </label>
        </div>
      </div>

      {isLoading && <LoadingState />}
      {error && <div className="p-8"><ErrorState message="Could not load projects for the map." onRetry={refetch} /></div>}

      {!isLoading && !error && (
        <div className="relative flex-1">
          {/* Legend */}
          <div className="absolute bottom-6 left-4 z-[1000] rounded-sm border border-hairline bg-paper-raised p-3 text-xs shadow-sm">
            <p className="mb-1.5 font-semibold text-ink">Risk level</p>
            {Object.entries(RISK_COLORS).map(([level, color]) => (
              <div key={level} className="flex items-center gap-2 py-0.5">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
                <span className="capitalize text-slate">{level}</span>
              </div>
            ))}
          </div>

          <MapContainer center={center} zoom={5} style={{ height: '100%', width: '100%' }}>
            <TileLayer
              attribution='&copy; OpenStreetMap contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {grouped.map((group, i) => (
              <CircleMarker
                key={i}
                center={[group.latitude, group.longitude]}
                radius={group.projects.length > 1 ? 9 : 6}
                pathOptions={{
                  color: markerColorFor(group),
                  fillColor: markerColorFor(group),
                  fillOpacity: 0.75,
                  weight: group.projects.length > 1 ? 2 : 1,
                }}
              >
                <Popup>
                  {group.projects.length > 1 ? (
                    <div className="min-w-[220px]">
                      <p className="mb-2 font-medium">{group.projects.length} Projects at this location</p>
                      {group.projects.map((p) => (
                        <div key={p.id} className="mb-2 border-b border-gray-200 pb-2 last:border-b-0 last:pb-0">
                          <p className="text-sm font-medium">{p.title}</p>
                          <p className="font-mono text-xs">{p.project_code}</p>
                          {p.risk_level && <p className="text-xs">Risk: {p.risk_level} ({p.final_score?.toFixed(0)})</p>}
                          <Link to={`/projects/${p.id}`} className="text-xs text-blue-600 underline">
                            View risk profile
                          </Link>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div>
                      <p className="font-medium">{group.projects[0].title}</p>
                      <p className="font-mono text-xs">{group.projects[0].project_code}</p>
                      {group.projects[0].risk_level && (
                        <p className="text-xs">
                          Risk: {group.projects[0].risk_level} ({group.projects[0].final_score?.toFixed(0)})
                        </p>
                      )}
                      <Link to={`/projects/${group.projects[0].id}`} className="text-xs text-blue-600 underline">
                        View risk profile
                      </Link>
                    </div>
                  )}
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        </div>
      )}
    </div>
  )
}
