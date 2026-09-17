import client from './client'

export async function uploadImportFile(file) {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await client.post('/imports/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function mapImportColumns(importId, columnMapping) {
  const { data } = await client.post(`/imports/${importId}/map-columns`, { column_mapping: columnMapping })
  return data
}

export async function previewImport(importId) {
  const { data } = await client.get(`/imports/${importId}/preview`)
  return data
}

export async function confirmImport(importId) {
  const { data } = await client.post(`/imports/${importId}/confirm`)
  return data
}
