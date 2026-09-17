import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchProjects } from '../api/projects'
import { fetchCases } from '../api/cases'

// Debounced project search (server-side, via the existing GET /projects?search=) plus a
// client-side match over the case list (there's no case search endpoint, and the existing
// Case Workspace page already fetches the full list this same way, so it's a small volume).
export default function GlobalSearch() {
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const [open, setOpen] = useState(false)
  const containerRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 250)
    return () => clearTimeout(t)
  }, [query])

  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const { data: projectMatches } = useQuery({
    queryKey: ['global-search-projects', debounced],
    queryFn: () => fetchProjects({ search: debounced, limit: 5 }),
    enabled: debounced.length >= 2,
  })

  const { data: allCases } = useQuery({
    queryKey: ['global-search-cases'],
    queryFn: fetchCases,
    enabled: debounced.length >= 2,
    staleTime: 60_000,
  })

  const caseMatches = (allCases || [])
    .filter((c) => c.id.toLowerCase().includes(debounced.toLowerCase()) || c.project_code.toLowerCase().includes(debounced.toLowerCase()))
    .slice(0, 5)

  const hasResults = (projectMatches?.length || 0) > 0 || caseMatches.length > 0

  function goTo(path) {
    setQuery('')
    setDebounced('')
    setOpen(false)
    navigate(path)
  }

  return (
    <div ref={containerRef} className="relative w-80">
      <input
        type="text"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        placeholder="Search project code, title, or case ID…"
        className="w-full rounded-sm border border-hairline bg-paper px-3 py-1.5 text-sm text-ink outline-none focus:border-secondary"
      />
      {open && debounced.length >= 2 && (
        <div className="absolute left-0 right-0 top-full z-40 mt-1 max-h-80 overflow-y-auto rounded-sm border border-hairline bg-card shadow-md">
          {!hasResults && <p className="px-3 py-3 text-sm text-slate">No matches for "{debounced}".</p>}
          {(projectMatches?.length || 0) > 0 && (
            <div>
              <p className="border-b border-hairline px-3 py-1.5 text-xs font-medium uppercase tracking-wide text-slate">Projects</p>
              {projectMatches.map((p) => (
                <button
                  key={p.id}
                  onClick={() => goTo(`/projects/${p.id}`)}
                  className="block w-full px-3 py-2 text-left text-sm hover:bg-paper"
                >
                  <span className="font-mono text-xs text-slate">{p.project_code}</span>
                  <span className="ml-2 text-ink">{p.title}</span>
                </button>
              ))}
            </div>
          )}
          {caseMatches.length > 0 && (
            <div>
              <p className="border-b border-t border-hairline px-3 py-1.5 text-xs font-medium uppercase tracking-wide text-slate">Cases</p>
              {caseMatches.map((c) => (
                <button
                  key={c.id}
                  onClick={() => goTo(`/cases/${c.id}`)}
                  className="block w-full px-3 py-2 text-left text-sm hover:bg-paper"
                >
                  <span className="font-mono text-xs text-slate">{c.id.slice(0, 8)}</span>
                  <span className="ml-2 text-ink">{c.project_code}</span>
                  <span className="ml-2 text-xs capitalize text-slate">{c.status.replace(/_/g, ' ')}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
