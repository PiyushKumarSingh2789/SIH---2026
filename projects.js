import client from './client'

export async function fetchProjects(params = {}) {
  const { data } = await client.get('/projects', { params })
  return data
}

// Same endpoint, but also surfaces the X-Total-Count header for pages that need real
// pagination (Project Explorer) -- kept separate from fetchProjects so existing callers
// (Map Intelligence, etc.) that expect a bare array back are untouched.
export async function fetchProjectsPaged(params = {}) {
  const { data, headers } = await client.get('/projects', { params })
  const totalCount = headers['x-total-count'] ? parseInt(headers['x-total-count'], 10) : data.length
  return { data, totalCount }
}

export async function fetchProjectRisk(projectId) {
  const { data } = await client.get(`/projects/${projectId}/risk`)
  return data
}

export async function fetchProjectDuplicates(projectId) {
  const { data } = await client.get(`/projects/${projectId}/duplicates`)
  return data
}

export async function fetchProjectBenchmark(projectId) {
  const { data } = await client.get(`/projects/${projectId}/benchmark`)
  return data
}

export async function fetchProjectCompliance(projectId) {
  const { data } = await client.get(`/projects/${projectId}/compliance`)
  return data
}

export async function fetchProjectRelationships(projectId) {
  const { data } = await client.get(`/projects/${projectId}/relationships`)
  return data
}

export async function fetchComplianceResults(params = {}) {
  const { data } = await client.get('/compliance', { params })
  return data
}

export async function fetchAlerts(minLevel = 'high', limit = 50) {
  const { data } = await client.get('/alerts', { params: { min_level: minLevel, limit } })
  return data
}

export async function fetchAnalyticsSummary() {
  const { data } = await client.get('/analytics/summary')
  return data
}

export async function recomputeRisk() {
  const { data } = await client.post('/risk/recompute')
  return data
}
