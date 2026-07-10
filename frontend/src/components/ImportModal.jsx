import { useRef, useState } from 'react'
import Modal from './Modal'
import FolderBrowserModal from './FolderBrowserModal'
import ComboSelect from './ComboSelect'
import * as api from '../api/client'

export default function ImportModal({ lookups, onClose, onImported }) {
  const [mode, setMode] = useState('full') // 'full' | 'manual'
  const [file, setFile] = useState(null)
  const [dragActive, setDragActive] = useState(false)
  const fileInputRef = useRef(null)
  const [phaseName, setPhaseName] = useState('')
  const [categoryName, setCategoryName] = useState('')
  const [subCategoryName, setSubCategoryName] = useState('')
  const [sourceRootPath, setSourceRootPath] = useState('')
  const [browserOpen, setBrowserOpen] = useState(false)
  const [preview, setPreview] = useState(null)
  const [resolutions, setResolutions] = useState({})
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const selectedPhase = lookups.phases.find((p) => p.name === phaseName)
  const categoryOptions = lookups.categories.filter((c) => !selectedPhase || c.phaseId === selectedPhase.id)
  const matchedCategory = categoryOptions.find((c) => c.name === categoryName)
  const subCategoryOptions = lookups.subCategories.filter(
    (sc) => !matchedCategory || sc.categoryId === matchedCategory.id
  )

  function manualContext() {
    if (mode !== 'manual') return null
    return {
      phaseName,
      categoryName: categoryName || null,
      subCategoryName: subCategoryName || null,
      sourceRootPath,
    }
  }

  function pickFile(candidate) {
    if (!candidate) return
    if (!candidate.name.toLowerCase().endsWith('.csv')) {
      setError('Please choose a .csv file')
      return
    }
    setError('')
    setFile(candidate)
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragActive(false)
    pickFile(e.dataTransfer.files?.[0])
  }

  async function handlePreview() {
    if (!file) return
    if (mode === 'manual' && (!phaseName || !sourceRootPath)) {
      setError('Phase and source folder path are required')
      return
    }
    setLoading(true)
    setError('')
    try {
      const data = await api.previewImport(file, manualContext())
      setPreview(data)
      const defaults = {}
      data.conflicts.forEach((c) => {
        defaults[`${c.row.file_name}::${c.row.phase_name}`] = 'skip'
      })
      setResolutions(defaults)
    } catch (err) {
      setError(err.message || 'Preview failed')
    } finally {
      setLoading(false)
    }
  }

  async function handleCommit() {
    if (!preview) return
    setLoading(true)
    setError('')
    try {
      const rows = [...preview.new_rows, ...preview.conflicts.map((c) => c.row)]
      const resolutionEntries = preview.conflicts.map((c) => ({
        file_name: c.row.file_name,
        phase_name: c.row.phase_name,
        resolution: resolutions[`${c.row.file_name}::${c.row.phase_name}`] || 'skip',
      }))
      const res = await api.commitImport({ rows, resolutions: resolutionEntries }, file?.name)
      setResult(res)
      onImported()
    } catch (err) {
      setError(err.message || 'Import failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title="Import CSV" onClose={onClose}>
      {!preview && (
        <>
          <div className="mode-tabs">
            <button
              type="button"
              className={mode === 'full' ? 'active' : 'secondary'}
              onClick={() => setMode('full')}
            >
              Full CSV
            </button>
            <button
              type="button"
              className={mode === 'manual' ? 'active' : 'secondary'}
              onClick={() => setMode('manual')}
            >
              Manual (pick Phase/Category first)
            </button>
          </div>

          {mode === 'full' ? (
            <p className="hint">
              CSV columns: file_name, phase_name, category_name, sub_category_name, source_path
            </p>
          ) : (
            <>
              <p className="hint">
                CSV: just file_name, one per row (header optional). Every row in this batch gets the
                Phase/Category/Sub-Category and source folder picked below.
              </p>
              <label>
                Phase
                <select
                  value={phaseName}
                  onChange={(e) => {
                    setPhaseName(e.target.value)
                    setCategoryName('')
                    setSubCategoryName('')
                  }}
                  required
                >
                  <option value="">Select a phase...</option>
                  {lookups.phases.map((p) => (
                    <option key={p.id} value={p.name}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Category
                <ComboSelect
                  value={categoryName}
                  onChange={(name) => {
                    setCategoryName(name)
                    setSubCategoryName('')
                  }}
                  options={categoryOptions}
                  placeholder="Type a new category name"
                  emptyLabel="Select a category..."
                />
              </label>
              <label>
                Sub-Category
                <ComboSelect
                  value={subCategoryName}
                  onChange={setSubCategoryName}
                  options={subCategoryOptions}
                  placeholder="Type a new sub-category name"
                  emptyLabel="Select a sub-category..."
                />
              </label>
              <label>
                Source folder path
                <div className="path-input-row">
                  <input
                    value={sourceRootPath}
                    onChange={(e) => setSourceRootPath(e.target.value)}
                    placeholder="\\server\share\Polish\Characters\Hero"
                    required
                  />
                  <button type="button" className="secondary" onClick={() => setBrowserOpen(true)}>
                    Browse...
                  </button>
                </div>
              </label>
            </>
          )}

          {browserOpen && (
            <FolderBrowserModal
              startPath={sourceRootPath}
              onClose={() => setBrowserOpen(false)}
              onSelect={(path) => {
                setSourceRootPath(path)
                setBrowserOpen(false)
              }}
            />
          )}

          <div
            className={`csv-dropzone ${dragActive ? 'active' : ''}`}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault()
              setDragActive(true)
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleDrop}
          >
            {file ? (
              <span>
                {file.name}{' '}
                <button
                  type="button"
                  className="secondary"
                  onClick={(e) => {
                    e.stopPropagation()
                    setFile(null)
                  }}
                >
                  Remove
                </button>
              </span>
            ) : (
              <span>Drag &amp; drop a CSV file here, or click to choose</span>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              style={{ display: 'none' }}
              onChange={(e) => pickFile(e.target.files?.[0])}
            />
          </div>
          {error && <div className="error-banner">{error}</div>}
          <div className="modal-actions">
            <button onClick={onClose} className="secondary">
              Cancel
            </button>
            <button onClick={handlePreview} disabled={!file || loading}>
              {loading ? 'Reading...' : 'Preview'}
            </button>
          </div>
        </>
      )}

      {preview && !result && (
        <>
          <p>
            {preview.new_rows.length} new file(s), {preview.conflicts.length} conflict(s).
          </p>
          {preview.conflicts.length > 0 && (
            <table className="import-conflict-table">
              <thead>
                <tr>
                  <th>File</th>
                  <th>Phase</th>
                  <th>Existing</th>
                  <th>Resolution</th>
                </tr>
              </thead>
              <tbody>
                {preview.conflicts.map((c) => {
                  const key = `${c.row.file_name}::${c.row.phase_name}`
                  return (
                    <tr key={key}>
                      <td>{c.row.file_name}</td>
                      <td>{c.row.phase_name}</td>
                      <td>v{c.existing_version_number}</td>
                      <td>
                        <select
                          value={resolutions[key]}
                          onChange={(e) => setResolutions({ ...resolutions, [key]: e.target.value })}
                        >
                          <option value="skip">Skip</option>
                          <option value="overwrite">Overwrite</option>
                          <option value="new_version">New Version</option>
                        </select>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
          {error && <div className="error-banner">{error}</div>}
          <div className="modal-actions">
            <button onClick={onClose} className="secondary">
              Cancel
            </button>
            <button onClick={handleCommit} disabled={loading}>
              {loading ? 'Importing...' : 'Confirm Import'}
            </button>
          </div>
        </>
      )}

      {result && (
        <>
          <p>
            Created {result.created}, updated {result.updated}, skipped {result.skipped}.
          </p>
          {result.errors.length > 0 && (
            <ul className="import-errors">
              {result.errors.map((e, i) => (
                <li key={i}>
                  {e.file_name} ({e.phase_name}): {e.error}
                </li>
              ))}
            </ul>
          )}
          <div className="modal-actions">
            <button onClick={onClose}>Done</button>
          </div>
        </>
      )}
    </Modal>
  )
}
