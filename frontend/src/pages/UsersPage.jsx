import { useEffect, useState } from 'react'
import Sidebar from '../components/Sidebar'
import CreateUserModal from '../components/CreateUserModal'
import EditUserModal from '../components/EditUserModal'
import ResetPasswordModal from '../components/ResetPasswordModal'
import * as api from '../api/client'

const EMPTY_LOOKUPS = { phases: [], statuses: [], categories: [], subCategories: [], roles: [], processTypes: [] }

export default function UsersPage() {
  const [users, setUsers] = useState([])
  const [lookups, setLookups] = useState(EMPTY_LOOKUPS)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [editTarget, setEditTarget] = useState(null)
  const [resetTarget, setResetTarget] = useState(null)

  async function load() {
    setLoading(true)
    try {
      const [usersData, lookupsData] = await Promise.all([api.getUsers(), api.getLookups()])
      setUsers(usersData)
      setLookups(lookupsData)
    } catch (err) {
      setError(err.message || 'Failed to load users')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  function phaseName(phaseId) {
    if (!phaseId) return '-'
    return lookups.phases.find((p) => p.id === phaseId)?.name || `#${phaseId}`
  }

  async function handleDelete(user) {
    if (!window.confirm(`Delete user "${user.Username}"? This cannot be undone.`)) return
    setError('')
    try {
      await api.deleteUser(user.UserID)
      await load()
    } catch (err) {
      setError(err.message || 'Failed to delete user')
    }
  }

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h1>User Management</h1>
          <button onClick={() => setCreateOpen(true)}>+ New User</button>
        </div>
        {error && <div className="error-banner">{error}</div>}
        {loading ? (
          <div className="loading">Loading...</div>
        ) : (
          <table className="users-table">
            <thead>
              <tr>
                <th>Username</th>
                <th>Roles</th>
                <th>Phase</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.UserID}>
                  <td>{u.Username}</td>
                  <td>
                    <div className="role-pill-group">
                      {u.roleNames.map((name) => (
                        <span key={name} className="status-pill">
                          {name}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td>{phaseName(u.PhaseID)}</td>
                  <td>
                    <span className={`status-pill ${u.IsActive ? 'active' : 'inactive'}`}>
                      {u.IsActive ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td>
                    <div className="grid-actions">
                      <button onClick={() => setEditTarget(u)}>Edit</button>
                      <button className="secondary" onClick={() => setResetTarget(u)}>
                        Reset Password
                      </button>
                      <button className="secondary" onClick={() => handleDelete(u)}>
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </main>

      {createOpen && (
        <CreateUserModal
          lookups={lookups}
          onCreate={async (payload) => {
            await api.createUser(payload)
            await load()
          }}
          onClose={() => setCreateOpen(false)}
        />
      )}

      {editTarget && (
        <EditUserModal
          user={editTarget}
          lookups={lookups}
          onSave={async (userId, payload) => {
            await api.updateUser(userId, payload)
            await load()
          }}
          onClose={() => setEditTarget(null)}
        />
      )}

      {resetTarget && (
        <ResetPasswordModal
          user={resetTarget}
          onReset={async (userId, newPassword) => {
            await api.adminResetPassword(userId, newPassword)
          }}
          onClose={() => setResetTarget(null)}
        />
      )}
    </div>
  )
}
