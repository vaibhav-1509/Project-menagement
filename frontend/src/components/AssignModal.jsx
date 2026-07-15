import { useState } from 'react'
import Modal from './Modal'
import { eligibleWorkers } from '../utils/eligibleWorkers'

function workerLabel(u) {
  const flag = !u.isAvailable || u.isOnLeaveToday ? ' (unavailable)' : ''
  return `${u.Username} — ${u.pendingCount} pending${flag}`
}

export default function AssignModal({ file, stage, users, onAssign, onClose }) {
  const [userId, setUserId] = useState('')
  const [showUnavailable, setShowUnavailable] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const eligible = eligibleWorkers(users, stage.processTypeId, { includeUnavailable: showUnavailable })

  async function handleAssign() {
    if (!userId) return
    setLoading(true)
    setError('')
    try {
      await onAssign(file.FileID, Number(userId), stage.processTypeId)
      onClose()
    } catch (err) {
      setError(err.message || 'Assign failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title={`Assign "${file.FileName}" - ${stage.processTypeName}`} onClose={onClose}>
      {eligible.length === 0 && (
        <p>No active workers are enabled (with both folders configured) for {stage.processTypeName}.</p>
      )}
      <select value={userId} onChange={(e) => setUserId(e.target.value)}>
        <option value="">Select a worker...</option>
        {eligible.map((u) => (
          <option key={u.UserID} value={u.UserID}>
            {workerLabel(u)}
          </option>
        ))}
      </select>
      <label className="checkbox-row">
        <input
          type="checkbox"
          checked={showUnavailable}
          onChange={(e) => setShowUnavailable(e.target.checked)}
        />
        Show unavailable workers too
      </label>
      {error && <div className="error-banner">{error}</div>}
      <div className="modal-actions">
        <button onClick={onClose} className="secondary">
          Cancel
        </button>
        <button onClick={handleAssign} disabled={!userId || loading}>
          {loading ? 'Assigning...' : 'Assign'}
        </button>
      </div>
    </Modal>
  )
}
