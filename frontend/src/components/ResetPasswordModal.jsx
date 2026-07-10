import { useState } from 'react'
import Modal from './Modal'

export default function ResetPasswordModal({ user, onReset, onClose }) {
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match')
      return
    }
    setLoading(true)
    try {
      await onReset(user.UserID, newPassword)
      onClose()
    } catch (err) {
      setError(err.message || 'Failed to reset password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title={`Reset password for "${user.Username}"`} onClose={onClose}>
      <form onSubmit={handleSubmit} className="modal-body" style={{ padding: 0 }}>
        <label>
          New password
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            autoFocus
          />
        </label>
        <label>
          Confirm new password
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
          />
        </label>
        {error && <div className="error-banner">{error}</div>}
        <div className="modal-actions">
          <button type="button" onClick={onClose} className="secondary">
            Cancel
          </button>
          <button type="submit" disabled={loading}>
            {loading ? 'Resetting...' : 'Reset Password'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
