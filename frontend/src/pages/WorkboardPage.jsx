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

  async function load() {
    setError('')
    try {
      const [boardData, usersData] = await Promise.all([api.getAdminWorkboard(), api.getUsers()])
      setBoard(boardData)
      setUsers(usersData)
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

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h1>Workboard</h1>
        </div>
        <p className="hint">Everything currently waiting on you - pending approvals and workers running low on files.</p>

        {error && <div className="error-banner">{error}</div>}
        {loading || !board ? (
          <div className="loading">Loading...</div>
        ) : (
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
              {board.lowWorkloadWorkers.length === 0 ? (
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
          </div>
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
