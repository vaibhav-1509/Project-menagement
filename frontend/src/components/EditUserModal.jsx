import { useEffect, useState } from 'react'
import Modal from './Modal'
import FolderBrowserModal from './FolderBrowserModal'
import RoleCheckboxGroup from './RoleCheckboxGroup'
import * as api from '../api/client'

export default function EditUserModal({ user, lookups, onSave, onClose }) {
  const [roleIds, setRoleIds] = useState(user.roleIds || [])
  const [phaseId, setPhaseId] = useState(user.PhaseID ? String(user.PhaseID) : '')
  const [isActive, setIsActive] = useState(user.IsActive)
  const [isAvailable, setIsAvailable] = useState(user.isAvailable ?? true)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // A worker has exactly ONE Pending folder and ONE Complete folder, shared
  // across every process type they're enabled for - not a separate folder
  // pair per type. Enabling Polish+GLB for a worker means both stages' files
  // flow through the same two folders; the per-process-type row in
  // WorkerProcessPaths still exists in the database (so SourcePath/DestPath
  // are still tracked per assignment), it just always gets the same pair of
  // paths written to it here instead of the admin re-typing them per type.
  const [sharedPendingPath, setSharedPendingPath] = useState('')
  const [sharedCompletePath, setSharedCompletePath] = useState('')
  const [enabledTypeIds, setEnabledTypeIds] = useState([])
  const [pathsLoading, setPathsLoading] = useState(true)
  const [browserField, setBrowserField] = useState(null) // 'pending' | 'complete'

  const [leave, setLeave] = useState([])
  const [leaveLoading, setLeaveLoading] = useState(true)
  const [leaveStart, setLeaveStart] = useState('')
  const [leaveEnd, setLeaveEnd] = useState('')
  const [leaveError, setLeaveError] = useState('')
  const [leaveSaving, setLeaveSaving] = useState(false)

  function reloadLeave() {
    return api
      .getUserLeave(user.UserID)
      .then(setLeave)
      .catch((err) => setLeaveError(err.message || 'Failed to load leave'))
  }

  useEffect(() => {
    reloadLeave().finally(() => setLeaveLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleAddLeave(e) {
    e.preventDefault()
    if (!leaveStart || !leaveEnd) {
      setLeaveError('Both a start and end date are required.')
      return
    }
    if (leaveEnd < leaveStart) {
      setLeaveError('End date must not be before the start date.')
      return
    }
    setLeaveSaving(true)
    setLeaveError('')
    try {
      await api.addUserLeave(user.UserID, leaveStart, leaveEnd)
      setLeaveStart('')
      setLeaveEnd('')
      await reloadLeave()
    } catch (err) {
      setLeaveError(err.message || 'Failed to add leave')
    } finally {
      setLeaveSaving(false)
    }
  }

  async function handleCancelLeave(leaveId) {
    if (!window.confirm('Cancel this leave period?')) return
    try {
      await api.deleteUserLeave(user.UserID, leaveId)
      await reloadLeave()
    } catch (err) {
      setLeaveError(err.message || 'Failed to cancel leave')
    }
  }

  // Admin and worker roles aren't mutually exclusive - a user can hold both
  // (e.g. an admin who also does Polish work). Process Type Paths only make
  // sense once a non-Admin role is held (that's what makes someone assignable
  // work) - Phase itself is never required, since a worker's access is
  // entirely defined by what's assigned to them, not by phase membership.
  const hasWorkerRole = roleIds.some((id) => lookups.roles.find((r) => r.id === id)?.name !== 'Admin')

  useEffect(() => {
    let cancelled = false
    api
      .getWorkerProcessPaths(user.UserID)
      .then((rows) => {
        if (cancelled) return
        setEnabledTypeIds(rows.filter((r) => r.isActive).map((r) => r.processTypeId))
        // Pre-fill the shared fields from whatever was configured before
        // (any row, even a disabled one) - once saved through this form
        // every enabled type is written with the same pair going forward.
        const withPaths = rows.find((r) => r.pendingPath && r.completePath)
        if (withPaths) {
          setSharedPendingPath(withPaths.pendingPath)
          setSharedCompletePath(withPaths.completePath)
        }
      })
      .catch((err) => setError(err.message || 'Failed to load worker paths'))
      .finally(() => !cancelled && setPathsLoading(false))
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function toggleEnabled(processTypeId) {
    setEnabledTypeIds((prev) =>
      prev.includes(processTypeId) ? prev.filter((id) => id !== processTypeId) : [...prev, processTypeId]
    )
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (roleIds.length === 0) {
      setError('Select at least one role')
      return
    }
    let entries = []
    if (enabledTypeIds.length > 0) {
      if (!sharedPendingPath || !sharedCompletePath) {
        setError('Pick both a Pending and a Complete folder')
        return
      }
      if (sharedPendingPath.trim().toLowerCase() === sharedCompletePath.trim().toLowerCase()) {
        setError('Pending and Complete folders must be different')
        return
      }
      entries = enabledTypeIds.map((processTypeId) => ({
        process_type_id: processTypeId,
        pending_path: sharedPendingPath,
        complete_path: sharedCompletePath,
        is_active: true,
      }))
    }

    setLoading(true)
    try {
      await onSave(user.UserID, {
        role_ids: roleIds,
        phase_id: phaseId ? Number(phaseId) : null,
        is_active: isActive,
        is_available: isAvailable,
      })
      await api.setWorkerProcessPaths(user.UserID, entries)
      onClose()
    } catch (err) {
      setError(err.message || 'Failed to update user')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title={`Edit "${user.Username}"`} onClose={onClose} wide>
      <form onSubmit={handleSubmit} className="modal-body" style={{ padding: 0 }}>
        <RoleCheckboxGroup roles={lookups.roles} value={roleIds} onChange={setRoleIds} />
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
        <label className="checkbox-row">
          <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
          Active
        </label>
        <label className="checkbox-row">
          <input type="checkbox" checked={isAvailable} onChange={(e) => setIsAvailable(e.target.checked)} />
          Available <span className="hint">(unchecking hides them from the Assign/Reject picker by default, without deactivating the account)</span>
        </label>

        <div className="move-section">
          <h3>Leave</h3>
          <p className="hint">Date ranges this worker is on leave - hides them from the Assign/Reject picker by default during that window.</p>
          <div className="settings-form">
            <label>
              Start date
              <input type="date" value={leaveStart} onChange={(e) => setLeaveStart(e.target.value)} />
            </label>
            <label>
              End date
              <input type="date" value={leaveEnd} onChange={(e) => setLeaveEnd(e.target.value)} />
            </label>
            <button type="button" onClick={handleAddLeave} disabled={leaveSaving}>
              {leaveSaving ? 'Adding...' : 'Add Leave'}
            </button>
          </div>
          {leaveError && <div className="error-banner">{leaveError}</div>}
          {leaveLoading ? (
            <div className="loading">Loading...</div>
          ) : leave.length === 0 ? (
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
                      <button type="button" className="secondary" onClick={() => handleCancelLeave(l.id)}>
                        Cancel
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {hasWorkerRole && (
          <div className="move-section">
            <h3>Pending / Complete Folders</h3>
            <p className="hint">
              One Pending folder and one Complete folder for this worker, shared across every stage they're
              enabled for below - not a separate pair per stage.
            </p>
            {pathsLoading ? (
              <div className="loading">Loading...</div>
            ) : (
              <>
                <div className="path-input-row">
                  <input
                    value={sharedPendingPath}
                    onChange={(e) => setSharedPendingPath(e.target.value)}
                    placeholder="Pending folder"
                  />
                  <button type="button" className="secondary" onClick={() => setBrowserField('pending')}>
                    Choose...
                  </button>
                </div>
                <div className="path-input-row">
                  <input
                    value={sharedCompletePath}
                    onChange={(e) => setSharedCompletePath(e.target.value)}
                    placeholder="Complete folder"
                  />
                  <button type="button" className="secondary" onClick={() => setBrowserField('complete')}>
                    Choose...
                  </button>
                </div>

                <p className="hint">Enabled for:</p>
                <div className="worker-type-checkboxes">
                  {lookups.processTypes.map((pt) => (
                    <label key={pt.id} className="checkbox-row worker-path-toggle">
                      <input
                        type="checkbox"
                        checked={enabledTypeIds.includes(pt.id)}
                        onChange={() => toggleEnabled(pt.id)}
                      />
                      {pt.name}
                    </label>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {error && <div className="error-banner">{error}</div>}
        <div className="modal-actions">
          <button type="button" onClick={onClose} className="secondary">
            Cancel
          </button>
          <button type="submit" disabled={loading || pathsLoading}>
            {loading ? 'Saving...' : 'Save'}
          </button>
        </div>
      </form>

      {browserField && (
        <FolderBrowserModal
          startPath={browserField === 'pending' ? sharedPendingPath : sharedCompletePath}
          onClose={() => setBrowserField(null)}
          onSelect={(path) => {
            if (browserField === 'pending') setSharedPendingPath(path)
            else setSharedCompletePath(path)
            setBrowserField(null)
          }}
        />
      )}
    </Modal>
  )
}
