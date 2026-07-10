import { useState } from 'react'
import Modal from './Modal'

export default function FailAssignmentModal({ file, onFail, onClose }) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!reason.trim()) {
      setError('A reason is required so whoever picks this up next knows what went wrong.')
      return
    }
    setLoading(true)
    setError('')
    try {
      await onFail(reason.trim())
      onClose()
    } catch (err) {
      setError(err.message || 'Failed to mark as failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title={`Mark "${file.FileName}" as Failed`} onClose={onClose}>
      <form onSubmit={handleSubmit} className="modal-body" style={{ padding: 0 }}>
        <label>
          Reason
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="What went wrong? This stays visible to whoever this gets reassigned to."
            rows={4}
            autoFocus
            required
          />
        </label>
        {error && <div className="error-banner">{error}</div>}
        <div className="modal-actions">
          <button type="button" onClick={onClose} className="secondary">
            Cancel
          </button>
          <button type="submit" disabled={loading}>
            {loading ? 'Submitting...' : 'Mark Failed'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
