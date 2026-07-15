import { useState } from 'react'
import Modal from './Modal'
import { eligibleWorkers } from '../utils/eligibleWorkers'

function workerLabel(u) {
  const flag = !u.isAvailable || u.isOnLeaveToday ? ' (unavailable)' : ''
  return `${u.Username} — ${u.pendingCount} pending${flag}`
}

export default function RejectModal({ file, stage, users, onReject, onClose }) {
  const [reason, setReason] = useState('')
  const [sameUser, setSameUser] = useState(true)
  const [userId, setUserId] = useState('')
  const [showUnavailable, setShowUnavailable] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const eligible = eligibleWorkers(users, stage.processTypeId, { includeUnavailable: showUnavailable })

  async function handleSubmit(e) {
    e.preventDefault()
    if (!reason.trim()) {
      setError('A reason is required so the worker knows what to fix.')
      return
    }
    if (!sameUser && !userId) {
      setError('Choose who to reassign this to.')
      return
    }
    setLoading(true)
    setError('')
    try {
      await onReject(reason.trim(), sameUser ? null : Number(userId))
      onClose()
    } catch (err) {
      setError(err.message || 'Reject failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title={`Reject "${file.FileName}" - ${stage.processTypeName}`} onClose={onClose}>
      <form onSubmit={handleSubmit} className="modal-body" style={{ padding: 0 }}>
        <label>
          Reason
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="What needs fixing? The worker will see this."
            rows={4}
            autoFocus
            required
          />
        </label>
        <label className="checkbox-row">
          <input type="checkbox" checked={sameUser} onChange={(e) => setSameUser(e.target.checked)} />
          Assign back to the same worker
        </label>
        {!sameUser && (
          <>
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
          </>
        )}
        {error && <div className="error-banner">{error}</div>}
        <div className="modal-actions">
          <button type="button" onClick={onClose} className="secondary">
            Cancel
          </button>
          <button type="submit" disabled={loading}>
            {loading ? 'Submitting...' : 'Reject & Reassign'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
