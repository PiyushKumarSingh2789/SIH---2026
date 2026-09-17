import { useState } from 'react'
import { uploadImportFile, previewImport, confirmImport } from '../api/imports'

export default function ImportPage() {
  const [file, setFile] = useState(null)
  const [importRecord, setImportRecord] = useState(null)
  const [preview, setPreview] = useState(null)
  const [confirmResult, setConfirmResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  async function handleUpload(e) {
    e.preventDefault()
    if (!file) return
    setBusy(true)
    setErrorMsg('')
    try {
      const result = await uploadImportFile(file)
      setImportRecord(result)
      setPreview(null)
      setConfirmResult(null)
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Upload failed.')
    } finally {
      setBusy(false)
    }
  }

  async function handlePreview() {
    setBusy(true)
    setErrorMsg('')
    try {
      const result = await previewImport(importRecord.id)
      setPreview(result)
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Preview failed.')
    } finally {
      setBusy(false)
    }
  }

  async function handleConfirm() {
    setBusy(true)
    setErrorMsg('')
    try {
      const result = await confirmImport(importRecord.id)
      setConfirmResult(result)
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Confirm failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-8 py-8">
      <h1 className="font-display text-2xl font-semibold text-ink">Import Console</h1>
      <p className="mt-1 mb-6 text-sm text-slate">Upload → map columns → preview → confirm. Admin roles only.</p>

      <form onSubmit={handleUpload} className="mb-6 rounded-sm border border-hairline bg-paper-raised p-5">
        <label className="mb-2 block text-xs font-medium text-slate">CSV or XLSX file</label>
        <input
          type="file"
          accept=".csv,.xlsx,.xls"
          onChange={(e) => setFile(e.target.files[0])}
          className="mb-3 block w-full text-sm text-ink"
        />
        <button
          type="submit"
          disabled={!file || busy}
          className="rounded-sm bg-ink px-4 py-2 text-sm font-medium text-paper hover:opacity-90 disabled:opacity-50"
        >
          Upload
        </button>
      </form>

      {errorMsg && <p className="mb-4 text-sm text-risk-critical">{errorMsg}</p>}

      {importRecord && (
        <div className="mb-6 rounded-sm border border-hairline bg-paper-raised p-5">
          <p className="mb-2 text-sm font-medium text-ink">{importRecord.original_filename}</p>
          <p className="text-xs text-slate">
            Status: <span className="font-mono">{importRecord.status}</span> · {importRecord.total_rows} rows detected
          </p>
          <p className="mt-2 text-xs text-slate">Mapped fields</p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {Object.entries(importRecord.column_mapping || {}).map(([source, target]) => (
              <span key={source} className="rounded-sm bg-paper px-2 py-1 text-xs">
                <span className="font-mono text-slate">{source}</span>
                <span className="mx-1 text-slate">→</span>
                <span className="font-mono text-ink">{target}</span>
              </span>
            ))}
            {Object.keys(importRecord.column_mapping || {}).length === 0 && (
              <span className="text-xs text-slate">No columns were auto-mapped.</span>
            )}
          </div>
          <button
            onClick={handlePreview}
            disabled={busy}
            className="mt-3 rounded-sm border border-ink px-4 py-2 text-sm font-medium text-ink hover:bg-ink hover:text-paper disabled:opacity-50"
          >
            Run validation preview
          </button>
        </div>
      )}

      {preview && (
        <div className="mb-6 rounded-sm border border-hairline bg-paper-raised p-5">
          <div className="mb-3 flex gap-6 text-sm">
            <span>Total: <span className="font-mono">{preview.total_rows}</span></span>
            <span className="text-risk-low">Valid: <span className="font-mono">{preview.valid_rows}</span></span>
            <span className="text-risk-critical">Errors: <span className="font-mono">{preview.error_rows}</span></span>
          </div>

          {preview.error_summary.length > 0 && (
            <div className="mb-4">
              <p className="mb-1 text-xs font-medium text-slate">Validation findings</p>
              <div className="max-h-48 overflow-y-auto rounded-sm bg-paper p-2">
                {preview.error_summary.map((e, i) => (
                  <p key={i} className="py-0.5 text-xs">
                    <span className="font-mono text-slate">Row {e.row_number} · {e.rule_code}</span>{' '}
                    <span className={e.severity === 'ERROR' ? 'text-risk-critical' : 'text-risk-medium'}>{e.message}</span>
                  </p>
                ))}
              </div>
            </div>
          )}

          {preview.sample_rows?.length > 0 && (
            <div className="mb-4">
              <p className="mb-1 text-xs font-medium text-slate">Row preview ({preview.sample_rows.length} of {preview.total_rows})</p>
              <div className="max-h-64 overflow-auto rounded-sm border border-hairline">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-hairline bg-paper text-slate">
                      <th className="px-2 py-1.5 font-medium">Row</th>
                      <th className="px-2 py-1.5 font-medium">Valid</th>
                      {Object.keys(preview.sample_rows[0].raw_data).map((col) => (
                        <th key={col} className="whitespace-nowrap px-2 py-1.5 font-medium">{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.sample_rows.map((row) => (
                      <tr key={row.row_number} className={`border-b border-hairline last:border-b-0 ${row.is_valid ? '' : 'bg-risk-critical-bg'}`}>
                        <td className="px-2 py-1.5 font-mono text-slate">{row.row_number}</td>
                        <td className="px-2 py-1.5">{row.is_valid ? <span className="text-risk-low">✓</span> : <span className="text-risk-critical">✗</span>}</td>
                        {Object.values(row.raw_data).map((val, i) => (
                          <td key={i} className="whitespace-nowrap px-2 py-1.5 text-ink-soft">{String(val ?? '—')}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <button
            onClick={handleConfirm}
            disabled={busy || preview.valid_rows === 0}
            className="rounded-sm bg-ink px-4 py-2 text-sm font-medium text-paper hover:opacity-90 disabled:opacity-50"
          >
            Confirm and create {preview.valid_rows} project{preview.valid_rows === 1 ? '' : 's'}
          </button>
        </div>
      )}

      {confirmResult && (
        <div className="rounded-sm border border-risk-low bg-risk-low-bg p-5">
          <p className="text-sm text-risk-low">
            {confirmResult.projects_created} project{confirmResult.projects_created === 1 ? '' : 's'} created.
            Run a risk recompute from the Dashboard to score {confirmResult.projects_created === 1 ? 'it' : 'them'}.
          </p>
        </div>
      )}
    </div>
  )
}
