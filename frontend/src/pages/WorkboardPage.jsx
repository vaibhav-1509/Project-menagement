import { useEffect, useState } from 'react'
import Sidebar from '../components/Sidebar'
import RejectModal from '../components/RejectModal'
import * as api from '../api/client'

export default function WorkboardPage() {
  const [board, setBoard] = useState(null)
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyKey, setBusyKey] = useState('') // `${fileId}:${processTypeId}` currently being approved
  const [rejectTarget, setRejectTarget] = useState(null) // { file, stage }
  const [lowWorkloadInput, setLowWorkloadInput] = useState('')
  const [staleDaysInput, setStaleDaysInput] = useState('')
  const [settingsSaving, setSettingsSaving] = useState(false)
  const [settingsError, setSettingsError] = useState('')



  async function load() {
    setError('')
    try {
      const [boardData, usersData] = await Promise.all([
        api.getAdminWorkboard(),
        api.getUsers(),
      ])
      setBoard(boardData)
      setUsers(usersData)
      setLowWorkloadInput(String(boardData.lowWorkloadThreshold))
      setStaleDaysInput(String(boardData.staleAssignmentDays))
    } catch (err) {
      setError(err.message || 'Failed to load workboard')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function handleApprove(item) {
    const key = `${item.fileId}:${item.processTypeId}`
    setBusyKey(key)
    setError('')
    try {
      await api.approveFile(item.fileId, item.processTypeId)
      await load()
    } catch (err) {
      setError(err.message || 'Failed to approve')
    } finally {
      setBusyKey('')
    }
  }

  async function handleReject(reason, reassignToUserId) {
    await api.rejectFile(rejectTarget.file.FileID, rejectTarget.stage.processTypeId, reason, reassignToUserId)
    await load()
  }

  async function handleSaveSettings(e) {
    e.preventDefault()
    const lowWorkload = Number(lowWorkloadInput)
    const staleDays = Number(staleDaysInput)
    if (!Number.isInteger(lowWorkload) || lowWorkload < 1 || !Number.isInteger(staleDays) || staleDays < 1) {
      setSettingsError('Both values must be whole numbers of at least 1.')
      return
    }
    setSettingsSaving(true)
    setSettingsError('')
    try {
      // Fetch current settings first so we don't wipe the folder paths
      // (allPendingPath etc.) that are managed in User Management, not here.
      const current = await api.getSettings()
      await api.updateSettings(lowWorkload, staleDays, {
        allPendingPath: current.allPendingPath,
        adminPendingPath: current.adminPendingPath,
        adminCompletePath: current.adminCompletePath,
      })
      await load()
    } catch (err) {
      setSettingsError(err.message || 'Failed to save settings')
    } finally {
      setSettingsSaving(false)
    }
  }

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h1>Workboard</h1>
        </div>
        <p className="hint">Everything currently waiting on you - pending approvals, workers running low on files, and stale assignments.</p>

        {error && <div className="error-banner">{error}</div>}
        {loading || !board ? (
          <div className="loading">Loading...</div>
        ) : (
          <>
            <div className="reports-panel">
              <h3>Workboard Settings</h3>
              <form onSubmit={handleSaveSettings} className="settings-form">
                <label>
                  Low workload threshold (fewer than N pending files)
                  <input
                    type="number"
                    min="1"
                    value={lowWorkloadInput}
                    onChange={(e) => setLowWorkloadInput(e.target.value)}
                  />
                </label>
                <label>
                  Stale after (days assigned without submission)
                  <input
                    type="number"
                    min="1"
                    value={staleDaysInput}
                    onChange={(e) => setStaleDaysInput(e.target.value)}
                  />
                </label>
                {settingsError && <div className="error-banner">{settingsError}</div>}
                <button type="submit" disabled={settingsSaving}>
                  {settingsSaving ? 'Saving...' : 'Save'}
                </button>
              </form>


            </div>

            <div className="reports-grid">
              <div className="reports-panel reports-panel-wide">
                <h3>Pending Approvals ({board.pendingApprovals.length})</h3>
                {board.pendingApprovals.length === 0 ? (
                  <p className="hint">Nothing waiting on review right now.</p>
                ) : (
                  <div className="taxonomy-tree">
                    {board.pendingApprovals.map((item) => {
                      const key = `${item.fileId}:${item.processTypeId}`
                      return (
                        <div key={key} className="taxonomy-node taxonomy-subcategory">
                          <div className="taxonomy-node-header">
                            <strong>{item.fileName}</strong>
                            <span className="status-pill warning">{item.processTypeName}</span>
                            <span className="hint">submitted by {item.submittedByUsername}</span>
                            <span className="hint">
                              {item.submittedAt ? new Date(item.submittedAt).toLocaleString() : ''}
                            </span>
                          </div>
                          <div className="grid-actions">
                            <button disabled={busyKey === key} onClick={() => handleApprove(item)}>
                              {busyKey === key ? 'Approving...' : 'Approve'}
                            </button>
                            <button
                              className="secondary"
                              disabled={busyKey === key}
                              onClick={() =>
                                setRejectTarget({
                                  file: { FileID: item.fileId, FileName: item.fileName },
                                  stage: { processTypeId: item.processTypeId, processTypeName: item.processTypeName },
                                })
                              }
                            >
                              Reject
                            </button>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              <div className="reports-panel reports-panel-wide">
                <h3>Workers Running Low on Files (fewer than {board.lowWorkloadThreshold})</h3>
                {board.checkedWorkerCount === 0 ? (
                  <p className="hint">
                    No workers are configured yet - a worker only shows up here once they have an active Pending/Complete
                    folder pair for at least one process type. Set that up on the User Management page first.
                  </p>
                ) : board.lowWorkloadWorkers.length === 0 ? (
                  <p className="hint">Everyone has enough queued up.</p>
                ) : (
                  <table className="users-table">
                    <thead>
                      <tr>
                        <th>Worker</th>
                        <th>Pending Files</th>
                      </tr>
                    </thead>
                    <tbody>
                      {board.lowWorkloadWorkers.map((w) => (
                        <tr key={w.userId}>
                          <td>{w.username}</td>
                          <td>{w.pendingCount}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              <div className="reports-panel reports-panel-wide">
                <h3>Stale Assignments (assigned over {board.staleAssignmentDays} day{board.staleAssignmentDays === 1 ? '' : 's'} ago, not yet submitted)</h3>
                {board.staleAssignments.length === 0 ? (
                  <p className="hint">Nothing has been sitting idle too long.</p>
                ) : (
                  <table className="users-table">
                    <thead>
                      <tr>
                        <th>File</th>
                        <th>Stage</th>
                        <th>Worker</th>
                        <th>Assigned On</th>
                        <th>Days Elapsed</th>
                      </tr>
                    </thead>
                    <tbody>
                      {board.staleAssignments.map((s) => (
                        <tr key={s.assignmentId}>
                          <td>{s.fileName}</td>
                          <td>{s.processTypeName}</td>
                          <td>{s.assignedToUsername}</td>
                          <td>{new Date(s.assignedTs).toLocaleDateString()}</td>
                          <td>{s.ageDays}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </>
        )}
      </main>



      {rejectTarget && (
        <RejectModal
          file={rejectTarget.file}
          stage={rejectTarget.stage}
          users={users}
          onReject={handleReject}
          onClose={() => setRejectTarget(null)}
        />
      )}
    </div>
  )
}
