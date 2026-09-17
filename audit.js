import client from './client'

export async function fetchAuditLogs(params = {}) {
  const { data } = await client.get('/audit', { params })
  return data
}
