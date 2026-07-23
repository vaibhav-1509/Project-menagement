import { useState, useMemo } from 'react'
import Modal from './Modal'
import { eligibleWorkers } from '../utils/eligibleWorkers'

function workerLabel(u) {
  const flag = !u.isAvailable || u.isOnLeaveToday ? ' (unavailable)' : ''
  return `${u.Username} — ${u.pendingCount} pending${flag}`
}

export default function AssignSelectedModal({
  selectedFiles,
  users,
  lookups,
  onAssign,
  onClose,
}) {
  const [userId, setUserId] = useState('')
  const [processTypeId, setProcessTypeId] = useState('')
  const [showUnavailable, setShowUnavailable] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const eligible = useMemo(
    () => eligibleWorkers(users, Number(processTypeId), { includeUnavailable: showUnavailable }),
    [users, processTypeId, showUnavailable]
  )

  const processTypeOptions = useMemo(
    () => lookups.processTypes,
    [lookups.processTypes]
  )

  async function handleAssign() {
    if (!userId || !processTypeId) return
    setLoading(true)
    setError('')
    try {
      const fileIds = selectedFiles.map((f) => f.FileID)
      const res = await onAssign(fileIds, Number(userId), Number(processTypeId))
      setResult(res)
    } catch (err) {
      setError(err.message || 'Assign failed')
    } finally {
      setLoading(false)
    }
  }

  if (!selectedFiles || selectedFiles.length === 0) return null

  return (
    <Modal title={`Assign ${selectedFiles.length} file(s)`} onClose={onClose} size="lg">
      <label>
        Process Type
        <select
          value={processTypeId}
          onChange={(e) => setProcessTypeId(e.target.value)}
          disabled={loading || result}
        >
          <option value="">Select a process type...</option>
          {processTypeOptions.map((pt) => (
            <option key={pt.id} value={pt.id}>
              {pt.name}
            </option>
          ))}
        </select>
      </label>

      <label>
        Worker
        <select
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          disabled={loading || result}
        >
          <option value="">Select a worker...</option>
          {eligible.map((u) => (
            <option key={u.UserID} value={u.UserID}>
              {workerLabel(u)}
            </option>
          ))}
        </select>
      </label>

      <label className="checkbox-row">
        <input
          type="checkbox"
          checked={showUnavailable}
          onChange={(e) => setShowUnavailable(e.target.checked)}
          disabled={loading || result}
        />
        Show unavailable workers too
      </label>

      {eligible.length === 0 && processTypeId && (
        <p className="hint">
          No active workers are enabled (with both folders configured) for the selected process type.
        </p>
      )}

      {error && <div className="error-banner">{error}</div>}

      {result && (
        <div className="notice-banner">
          <strong>Assigned {result.updated} file(s)</strong>
          {result.skipped.length > 0 && (
            <details style={{ marginTop: '8px' }}>
              <summary>Skipped {result.skipped.length} file(s)</summary>
              <ul style={{ marginTop: '4px', paddingLeft: '20px' }}>
                {result.skipped.map((s, i) => (
                  <li key={i}>
                    File {s.file_id}: {s.reason}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      <div className="modal-actions">
        <button onClick={onClose} className="secondary" disabled={loading}>
          {result ? 'Done' : 'Cancel'}
        </button>
        {!result && (
          <button onClick={handleAssign} disabled={!userId || !processTypeId || loading}>
            {loading ? 'Assigning...' : 'Assign All'}
          </button>
        )}
      </div>
    </Modal>
  )
}