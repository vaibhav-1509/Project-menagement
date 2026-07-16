import { useEffect, useState } from 'react'
import Sidebar from '../components/Sidebar'
import RejectModal from '../components/RejectModal'
import FolderBrowserModal from '../components/FolderBrowserModal'
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

  // The admin's own folder pair (Pending/Complete, same shape as a worker's
  // shared WorkerProcessPath folders) plus the raw, unregistered, loose-file
  // intake pool that exists before anything is imported into the system.
  const [allPendingPath, setAllPendingPath] = useState('')
  const [adminPendingPath, setAdminPendingPath] = useState('')
  const [adminCompletePath, setAdminCompletePath] = useState('')
  const [browserField, setBrowserField] = useState(null) // 'allPending' | 'adminPending' | 'adminComplete'

  async function load() {
    setError('')
    try {
      const [boardData, usersData, settingsData] = await Promise.all([
        api.getAdminWorkboard(),
        api.getUsers(),
        api.getSettings(),
      ])
      setBoard(boardData)
      setUsers(usersData)
      setLowWorkloadInput(String(boardData.lowWorkloadThreshold))
      setStaleDaysInput(String(boardData.staleAssignmentDays))
      setAllPendingPath(settingsData.allPendingPath || '')
      setAdminPendingPath(settingsData.adminPendingPath || '')
      setAdminCompletePath(settingsData.adminCompletePath || '')
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
      await api.updateSettings(lowWorkload, staleDays, { allPendingPath, adminPendingPath, adminCompletePath })
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

              <h3>Admin Folders</h3>
              <p className="hint">
                The admin's own Pending/Complete folder pair - same shape as a worker's shared folders - plus the raw
                intake pool where all unsorted files land before anything is imported into the system.
              </p>
              <div className="settings-form">
                <label>
                  All Pending <span className="hint">(raw intake pool - all categories, before import)</span>
                  <div className="path-input-row">
                    <input value={allPendingPath} onChange={(e) => setAllPendingPath(e.target.value)} placeholder="All Pending folder" />
                    <button type="button" className="secondary" onClick={() => setBrowserField('allPending')}>
                      Choose...
                    </button>
                  </div>
                </label>
                <label>
                  Admin Pending
                  <div className="path-input-row">
                    <input value={adminPendingPath} onChange={(e) => setAdminPendingPath(e.target.value)} placeholder="Admin Pending folder" />
                    <button type="button" className="secondary" onClick={() => setBrowserField('adminPending')}>
                      Choose...
                    </button>
                  </div>
                </label>
                <label>
                  Admin Complete
                  <div className="path-input-row">
                    <input value={adminCompletePath} onChange={(e) => setAdminCompletePath(e.target.value)} placeholder="Admin Complete folder" />
                    <button type="button" className="secondary" onClick={() => setBrowserField('adminComplete')}>
                      Choose...
                    </button>
                  </div>
                </label>
                <button type="button" onClick={handleSaveSettings} disabled={settingsSaving}>
                  {settingsSaving ? 'Saving...' : 'Save Admin Folders'}
                </button>
              </div>
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

      {browserField && (
        <FolderBrowserModal
          startPath={
            browserField === 'allPending' ? allPendingPath : browserField === 'adminPending' ? adminPendingPath : adminCompletePath
          }
          onClose={() => setBrowserField(null)}
          onSelect={(path) => {
            if (browserField === 'allPending') setAllPendingPath(path)
            else if (browserField === 'adminPending') setAdminPendingPath(path)
            else setAdminCompletePath(path)
            setBrowserField(null)
          }}
        />
      )}

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
