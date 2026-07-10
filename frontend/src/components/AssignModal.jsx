import { useState } from 'react'
import Modal from './Modal'

export default function AssignModal({ file, stage, users, onAssign, onClose }) {
  const [userId, setUserId] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const eligible = users.filter((u) => u.IsActive && u.enabledProcessTypeIds.includes(stage.processTypeId))

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
            {u.Username}
          </option>
        ))}
      </select>
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
