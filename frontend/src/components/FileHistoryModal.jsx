import { useEffect, useState } from 'react'
import Modal from './Modal'
import * as api from '../api/client'

function StatusPill({ statusName, failureReason }) {
  const cls = statusName === 'Complete' ? 'active' : statusName === 'Failed' ? 'inactive' : ''
  return (
    <span className={`status-pill ${cls}`} title={failureReason || ''}>
      {statusName}
    </span>
  )
}

export default function FileHistoryModal({ fileId, onClose }) {
  const [history, setHistory] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .getProcessHistory(fileId)
      .then(setHistory)
      .catch((err) => setError(err.message || 'Failed to load history'))
      .finally(() => setLoading(false))
  }, [fileId])

  return (
    <Modal title={history ? `History - ${history.fileName}` : 'History'} onClose={onClose} wide>
      {error && <div className="error-banner">{error}</div>}
      {loading ? (
        <div className="loading">Loading...</div>
      ) : (
        <div className="taxonomy-tree">
          {history.stages.map((stage) => (
            <div key={stage.processTypeId} className="taxonomy-node taxonomy-phase">
              <div className="taxonomy-node-header">
                <strong>{stage.processTypeName}</strong>
                <StatusPill statusName={stage.statusName} failureReason={stage.lastFailureReason} />
              </div>
              {stage.lastFailureReason && (
                <p className="hint">Last failure reason: {stage.lastFailureReason}</p>
              )}
              <div className="taxonomy-children">
                {stage.attempts.length === 0 ? (
                  <p className="hint">No attempts yet.</p>
                ) : (
                  stage.attempts.map((a) => (
                    <div key={a.assignmentId} className="taxonomy-node taxonomy-subcategory">
                      <div className="taxonomy-node-header">
                        <span>{a.assignedToUsername}</span>
                        <StatusPill statusName={a.statusName} />
                        <span className="hint">
                          {new Date(a.assignedTs).toLocaleString()}
                          {a.completionTs ? ` -> ${new Date(a.completionTs).toLocaleString()}` : ' (in progress)'}
                        </span>
                      </div>
                      {a.failureReason && <p className="hint">Reason: {a.failureReason}</p>}
                    </div>
                  ))
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      <div className="modal-actions">
        <button onClick={onClose}>Close</button>
      </div>
    </Modal>
  )
}
