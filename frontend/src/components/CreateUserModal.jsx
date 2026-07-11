import { useState } from 'react'
import Modal from './Modal'
import RoleCheckboxGroup from './RoleCheckboxGroup'

function suggestPhaseId(roleName, phases) {
  if (!roleName) return null
  const match = phases.find((p) => roleName.toLowerCase().includes(p.name.toLowerCase()))
  return match ? match.id : null
}

export default function CreateUserModal({ lookups, onCreate, onClose }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [roleIds, setRoleIds] = useState([])
  const [phaseId, setPhaseId] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  function handleRoleIdsChange(nextIds) {
    const added = nextIds.find((id) => !roleIds.includes(id))
    setRoleIds(nextIds)
    if (added != null && !phaseId) {
      const role = lookups.roles.find((r) => r.id === added)
      if (role && role.name !== 'Admin') {
        const suggested = suggestPhaseId(role.name, lookups.phases)
        if (suggested) setPhaseId(String(suggested))
      }
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    if (roleIds.length === 0) {
      setError('Select at least one role')
      return
    }
    setLoading(true)
    try {
      await onCreate({
        username,
        password,
        role_ids: roleIds,
        phase_id: phaseId ? Number(phaseId) : null,
      })
      onClose()
    } catch (err) {
      setError(err.message || 'Failed to create user')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title="New User" onClose={onClose}>
      <form onSubmit={handleSubmit} className="modal-body" style={{ padding: 0 }}>
        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        <RoleCheckboxGroup roles={lookups.roles} value={roleIds} onChange={handleRoleIdsChange} />
        <label>
          Phase <span className="hint">(optional - for reference only, doesn't limit what they can be assigned)</span>
          <select value={phaseId} onChange={(e) => setPhaseId(e.target.value)}>
            <option value="">No phase</option>
            {lookups.phases.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        {error && <div className="error-banner">{error}</div>}
        <div className="modal-actions">
          <button type="button" onClick={onClose} className="secondary">
            Cancel
          </button>
          <button type="submit" disabled={!username || roleIds.length === 0 || loading}>
            {loading ? 'Creating...' : 'Create User'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
