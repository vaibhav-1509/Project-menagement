import { useState } from 'react'
import Modal from '../Modal'
import DateRangeCalendar from '../DateRangeCalendar'

function isoDaysAgo(days) {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString().slice(0, 10)
}

const PRESETS = [
  { key: 'last-week', label: 'Last Week', days: 6 },
  { key: 'last-month', label: 'Last Month', days: 29 },
  { key: 'last-3-months', label: 'Last 3 Months', days: 89 },
  { key: 'last-6-months', label: 'Last 6 Months', days: 181 },
]

export default function ExportReportModal({ initialStart, initialEnd, onExport, onClose }) {
  const [preset, setPreset] = useState('custom')
  const [range, setRange] = useState({ start: initialStart, end: initialEnd })
  const [exporting, setExporting] = useState('') // '' | 'excel' | 'pdf'
  const [error, setError] = useState('')

  function pickPreset(p) {
    setPreset(p.key)
    setRange({ start: isoDaysAgo(p.days), end: isoDaysAgo(0) })
  }

  async function handleExport(kind) {
    if (!range.start || !range.end) {
      setError('Pick a start and end date first.')
      return
    }
    setError('')
    setExporting(kind)
    try {
      await onExport(kind, range.start, range.end)
      onClose()
    } catch (err) {
      setError(err.message || `Failed to export ${kind}`)
    } finally {
      setExporting('')
    }
  }

  return (
    <Modal title="Export Report" onClose={onClose}>
      <div className="export-modal-body">
        <div className="export-presets">
          {PRESETS.map((p) => (
            <button
              type="button"
              key={p.key}
              className={`secondary ${preset === p.key ? 'export-preset-active' : ''}`}
              onClick={() => pickPreset(p)}
            >
              {p.label}
            </button>
          ))}
          <button
            type="button"
            className={`secondary ${preset === 'custom' ? 'export-preset-active' : ''}`}
            onClick={() => setPreset('custom')}
          >
            Custom Range
          </button>
        </div>

        {preset === 'custom' && (
          <DateRangeCalendar value={range} onChange={(start, end) => setRange({ start, end })} alwaysExpanded />
        )}

        {preset !== 'custom' && (
          <p className="hint">
            {range.start} to {range.end}
          </p>
        )}

        {error && <div className="error-banner">{error}</div>}

        <div className="modal-actions">
          <button type="button" onClick={onClose} className="secondary">
            Cancel
          </button>
          <button type="button" disabled={exporting !== ''} onClick={() => handleExport('excel')}>
            {exporting === 'excel' ? 'Exporting...' : 'Export Excel'}
          </button>
          <button type="button" disabled={exporting !== ''} onClick={() => handleExport('pdf')}>
            {exporting === 'pdf' ? 'Exporting...' : 'Export PDF'}
          </button>
        </div>
      </div>
    </Modal>
  )
}
