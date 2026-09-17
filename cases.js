import client from './client'

export async function fetchCases() {
  const { data } = await client.get('/cases')
  return data
}

export async function fetchCase(caseId) {
  const { data } = await client.get(`/cases/${caseId}`)
  return data
}

export async function createCase(projectId, riskScoreId = null) {
  const { data } = await client.post('/cases', { project_id: projectId, risk_score_id: riskScoreId })
  return data
}

export async function changeCaseStatus(caseId, newStatus, remark) {
  const { data } = await client.patch(`/cases/${caseId}/status`, { new_status: newStatus, remark })
  return data
}

export async function addCaseComment(caseId, body) {
  const { data } = await client.post(`/cases/${caseId}/comments`, { body })
  return data
}

export async function addCaseEvidence(caseId, evidenceCategory, description, fileReference) {
  const { data } = await client.post(`/cases/${caseId}/evidence`, {
    evidence_category: evidenceCategory,
    description,
    file_reference: fileReference || null,
  })
  return data
}

export async function fetchCaseBrief(caseId) {
  const { data } = await client.get(`/cases/${caseId}/brief`)
  return data
}
