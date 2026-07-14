import { useState } from 'react'
import Modal from './Modal'

export default function RejectModal({ file, stage, users, onReject, onClose }) {
  const [reason, setReason] = useState('')
  const [sameUser, setSameUser] = useState(true)
  const [userId, setUserId] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const eligible = users.filter((u) => u.IsActive && u.enabledProcessTypeIds.includes(stage.processTypeId))

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
                  {u.Username}
                </option>
              ))}
            </select>
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
