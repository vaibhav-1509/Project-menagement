import { useState } from 'react'
import Modal from './Modal'
import * as api from '../api/client'

export default function ChangePasswordModal({ onClose }) {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (newPassword.length < 8) {
      setError('New password must be at least 8 characters')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('New passwords do not match')
      return
    }
    setLoading(true)
    try {
      await api.changePassword(currentPassword, newPassword)
      setDone(true)
    } catch (err) {
      setError(err.message || 'Failed to change password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title="Change Password" onClose={onClose}>
      {done ? (
        <>
          <p>Password changed successfully.</p>
          <div className="modal-actions">
            <button onClick={onClose}>Done</button>
          </div>
        </>
      ) : (
        <form onSubmit={handleSubmit} className="modal-body" style={{ padding: 0 }}>
          <label>
            Current password
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              autoFocus
            />
          </label>
          <label>
            New password
            <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required />
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
              {loading ? 'Changing...' : 'Change Password'}
            </button>
          </div>
        </form>
      )}
    </Modal>
  )
}
