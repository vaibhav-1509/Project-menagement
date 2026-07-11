import { useEffect, useState } from 'react'
import Modal from './Modal'
import FolderBrowserModal from './FolderBrowserModal'
import RoleCheckboxGroup from './RoleCheckboxGroup'
import * as api from '../api/client'

export default function EditUserModal({ user, lookups, onSave, onClose }) {
  const [roleIds, setRoleIds] = useState(user.roleIds || [])
  const [phaseId, setPhaseId] = useState(user.PhaseID ? String(user.PhaseID) : '')
  const [isActive, setIsActive] = useState(user.IsActive)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const [pathsByType, setPathsByType] = useState({})
  const [pathsLoading, setPathsLoading] = useState(true)
  const [browserTarget, setBrowserTarget] = useState(null) // { processTypeId, field: 'pending' | 'complete' }

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
        const byType = {}
        rows.forEach((r) => {
          byType[r.processTypeId] = { enabled: r.isActive, pendingPath: r.pendingPath, completePath: r.completePath }
        })
        setPathsByType(byType)
      })
      .catch((err) => setError(err.message || 'Failed to load worker paths'))
      .finally(() => !cancelled && setPathsLoading(false))
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function updatePath(processTypeId, field, value) {
    setPathsByType({
      ...pathsByType,
      [processTypeId]: { enabled: true, pendingPath: '', completePath: '', ...pathsByType[processTypeId], [field]: value },
    })
  }

  function toggleEnabled(processTypeId) {
    const current = pathsByType[processTypeId] || { pendingPath: '', completePath: '' }
    setPathsByType({ ...pathsByType, [processTypeId]: { ...current, enabled: !current.enabled } })
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (roleIds.length === 0) {
      setError('Select at least one role')
      return
    }
    const entries = []
    for (const pt of lookups.processTypes) {
      const entry = pathsByType[pt.id]
      if (!entry?.enabled) continue
      if (!entry.pendingPath || !entry.completePath) {
        setError(`Pick both a Pending and a Complete folder for ${pt.name}`)
        return
      }
      entries.push({
        process_type_id: pt.id,
        pending_path: entry.pendingPath,
        complete_path: entry.completePath,
        is_active: true,
      })
    }

    setLoading(true)
    try {
      await onSave(user.UserID, {
        role_ids: roleIds,
        phase_id: phaseId ? Number(phaseId) : null,
        is_active: isActive,
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

        {hasWorkerRole && (
          <div className="move-section">
            <h3>Process Type Paths</h3>
            <p className="hint">
              Enable the stages this worker can be assigned, with a Pending and Complete folder for each. Both
              are required before they can be assigned any work of that type.
            </p>
            {pathsLoading ? (
              <div className="loading">Loading...</div>
            ) : (
              lookups.processTypes.map((pt) => {
                const entry = pathsByType[pt.id] || { enabled: false, pendingPath: '', completePath: '' }
                return (
                  <div key={pt.id} className="worker-path-row">
                    <label className="checkbox-row worker-path-toggle">
                      <input type="checkbox" checked={!!entry.enabled} onChange={() => toggleEnabled(pt.id)} />
                      {pt.name}
                    </label>
                    {entry.enabled && (
                      <div className="worker-path-fields">
                        <div className="path-input-row">
                          <input
                            value={entry.pendingPath}
                            onChange={(e) => updatePath(pt.id, 'pendingPath', e.target.value)}
                            placeholder="Pending folder"
                          />
                          <button
                            type="button"
                            className="secondary"
                            onClick={() => setBrowserTarget({ processTypeId: pt.id, field: 'pendingPath' })}
                          >
                            Choose...
                          </button>
                        </div>
                        <div className="path-input-row">
                          <input
                            value={entry.completePath}
                            onChange={(e) => updatePath(pt.id, 'completePath', e.target.value)}
                            placeholder="Complete folder"
                          />
                          <button
                            type="button"
                            className="secondary"
                            onClick={() => setBrowserTarget({ processTypeId: pt.id, field: 'completePath' })}
                          >
                            Choose...
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )
              })
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

      {browserTarget && (
        <FolderBrowserModal
          startPath={pathsByType[browserTarget.processTypeId]?.[browserTarget.field] || ''}
          onClose={() => setBrowserTarget(null)}
          onSelect={(path) => {
            updatePath(browserTarget.processTypeId, browserTarget.field, path)
            setBrowserTarget(null)
          }}
        />
      )}
    </Modal>
  )
}
