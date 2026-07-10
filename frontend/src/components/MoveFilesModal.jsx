import { useState } from 'react'
import Modal from './Modal'

export default function MoveFilesModal({ selectedFiles, lookups, onMoveCategory, onMovePhase, onClose, onDone }) {
  const [categoryId, setCategoryId] = useState('')
  const [subCategoryId, setSubCategoryId] = useState('')
  const [phaseId, setPhaseId] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(false)

  const fileIds = selectedFiles.map((f) => f.FileID)
  const selectedPhaseIds = [...new Set(selectedFiles.map((f) => f.PhaseID))]
  const singlePhaseId = selectedPhaseIds.length === 1 ? selectedPhaseIds[0] : null
  const categoryOptions = lookups.categories.filter((c) => !singlePhaseId || c.phaseId === singlePhaseId)
  const subCategoryOptions = lookups.subCategories.filter(
    (sc) => !categoryId || sc.categoryId === Number(categoryId)
  )

  async function handleMoveCategory() {
    setError('')
    setNotice('')
    setLoading(true)
    try {
      const res = await onMoveCategory(fileIds, categoryId ? Number(categoryId) : null, subCategoryId ? Number(subCategoryId) : null)
      setNotice(`Moved ${res.updated} file(s) to the new category.`)
      onDone()
    } catch (err) {
      setError(err.message || 'Failed to move category')
    } finally {
      setLoading(false)
    }
  }

  async function handleMovePhase() {
    if (!phaseId) {
      setError('Select a phase')
      return
    }
    setError('')
    setNotice('')
    setLoading(true)
    try {
      const res = await onMovePhase(fileIds, Number(phaseId))
      let message = `Moved ${res.updated} file(s) to the new phase.`
      if (res.skipped.length > 0) {
        message += ` Skipped ${res.skipped.length}: ${res.skipped.map((s) => s.reason).join('; ')}`
      }
      setNotice(message)
      onDone()
    } catch (err) {
      setError(err.message || 'Failed to move phase')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title={`Move ${selectedFiles.length} file(s)`} onClose={onClose}>
      <p className="hint">
        {selectedFiles
          .slice(0, 5)
          .map((f) => f.FileName)
          .join(', ')}
        {selectedFiles.length > 5 ? ` and ${selectedFiles.length - 5} more` : ''}
      </p>

      <div className="move-section">
        <h3>Move to Category / Sub-Category</h3>
        {singlePhaseId ? (
          <>
            <label>
              Category
              <select
                value={categoryId}
                onChange={(e) => {
                  setCategoryId(e.target.value)
                  setSubCategoryId('')
                }}
              >
                <option value="">Uncategorized</option>
                {categoryOptions.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Sub-Category
              <select value={subCategoryId} onChange={(e) => setSubCategoryId(e.target.value)} disabled={!categoryId}>
                <option value="">None</option>
                {subCategoryOptions.map((sc) => (
                  <option key={sc.id} value={sc.id}>
                    {sc.name}
                  </option>
                ))}
              </select>
            </label>
            <button onClick={handleMoveCategory} disabled={loading}>
              Move Category
            </button>
          </>
        ) : (
          <p className="hint">
            Selected files span multiple phases, and categories are scoped to a phase - select files from a
            single phase to move category.
          </p>
        )}
      </div>

      <div className="move-section">
        <h3>Move to Phase</h3>
        <p className="hint">Files with an active assignment are skipped - reset them first.</p>
        <label>
          Phase
          <select value={phaseId} onChange={(e) => setPhaseId(e.target.value)}>
            <option value="">Select a phase...</option>
            {lookups.phases.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <button onClick={handleMovePhase} disabled={loading || !phaseId}>
          Move Phase
        </button>
      </div>

      {notice && <div className="notice-banner">{notice}</div>}
      {error && <div className="error-banner">{error}</div>}
      <div className="modal-actions">
        <button onClick={onClose}>Done</button>
      </div>
    </Modal>
  )
}
