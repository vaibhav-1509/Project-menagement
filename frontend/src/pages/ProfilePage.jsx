import { useEffect, useState } from 'react'
import Sidebar from '../components/Sidebar'
import * as api from '../api/client'

export default function ProfilePage() {
  const [profile, setProfile] = useState(null)
  const [lookups, setLookups] = useState({ phases: [] })
  const [leave, setLeave] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [availabilitySaving, setAvailabilitySaving] = useState(false)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [leaveError, setLeaveError] = useState('')
  const [leaveSaving, setLeaveSaving] = useState(false)

  async function load() {
    setError('')
    try {
      const [profileData, lookupsData, leaveData] = await Promise.all([
        api.getProfile(),
        api.getLookups(),
        api.getMyLeave(),
      ])
      setProfile(profileData)
      setLookups(lookupsData)
      setLeave(leaveData)
    } catch (err) {
      setError(err.message || 'Failed to load profile')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function handleToggleAvailability() {
    if (!profile) return
    setAvailabilitySaving(true)
    setError('')
    try {
      const updated = await api.updateAvailability(!profile.isAvailable)
      setProfile(updated)
    } catch (err) {
      setError(err.message || 'Failed to update availability')
    } finally {
      setAvailabilitySaving(false)
    }
  }

  async function handleAddLeave(e) {
    e.preventDefault()
    if (!startDate || !endDate) {
      setLeaveError('Both a start and end date are required.')
      return
    }
    if (endDate < startDate) {
      setLeaveError('End date must not be before the start date.')
      return
    }
    setLeaveSaving(true)
    setLeaveError('')
    try {
      await api.addMyLeave(startDate, endDate)
      setStartDate('')
      setEndDate('')
      setLeave(await api.getMyLeave())
    } catch (err) {
      setLeaveError(err.message || 'Failed to add leave')
    } finally {
      setLeaveSaving(false)
    }
  }

  async function handleCancelLeave(id) {
    if (!window.confirm('Cancel this leave period?')) return
    try {
      await api.cancelMyLeave(id)
      setLeave(await api.getMyLeave())
    } catch (err) {
      setError(err.message || 'Failed to cancel leave')
    }
  }

  const phaseName = profile?.phaseId != null ? lookups.phases.find((p) => p.id === profile.phaseId)?.name : null

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h1>My Profile</h1>
        </div>
        {error && <div className="error-banner">{error}</div>}
        {loading || !profile ? (
          <div className="loading">Loading...</div>
        ) : (
          <div className="reports-grid">
            <div className="reports-panel">
              <h3>Account</h3>
              <p>
                <strong>{profile.username}</strong>
              </p>
              <div className="role-pill-group">
                {profile.roleNames.map((r) => (
                  <span key={r} className="role-badge">
                    {r}
                  </span>
                ))}
              </div>
              {phaseName && <p className="hint">Phase: {phaseName}</p>}
            </div>

            <div className="reports-panel">
              <h3>My Availability</h3>
              <p className="hint">
                Toggle this off if you're not taking new work right now - it won't deactivate your account, it just
                hides you from the Assign/Reject worker picker by default.
              </p>
              <span className={`status-pill ${profile.isAvailable ? 'active' : 'inactive'}`}>
                {profile.isAvailable ? 'Available' : 'Unavailable'}
              </span>
              <div className="modal-actions" style={{ justifyContent: 'flex-start', marginTop: 12 }}>
                <button onClick={handleToggleAvailability} disabled={availabilitySaving}>
                  {availabilitySaving
                    ? 'Saving...'
                    : profile.isAvailable
                    ? 'Mark as Unavailable'
                    : 'Mark as Available'}
                </button>
              </div>
            </div>

            <div className="reports-panel reports-panel-wide">
              <h3>My Leave</h3>
              <form onSubmit={handleAddLeave} className="settings-form">
                <label>
                  Start date
                  <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
                </label>
                <label>
                  End date
                  <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
                </label>
                <button type="submit" disabled={leaveSaving}>
                  {leaveSaving ? 'Adding...' : 'Add Leave'}
                </button>
              </form>
              {leaveError && <div className="error-banner">{leaveError}</div>}

              {leave.length === 0 ? (
                <p className="hint">No leave periods recorded.</p>
              ) : (
                <table className="users-table">
                  <thead>
                    <tr>
                      <th>Start</th>
                      <th>End</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {leave.map((l) => (
                      <tr key={l.id}>
                        <td>{l.startDate}</td>
                        <td>{l.endDate}</td>
                        <td>
                          <button className="secondary" onClick={() => handleCancelLeave(l.id)}>
                            Cancel
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
