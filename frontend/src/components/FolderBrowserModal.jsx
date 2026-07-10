import { useEffect, useState } from 'react'
import Modal from './Modal'
import * as api from '../api/client'

function TreeNode({ entry, depth, selectedPath, onSelect }) {
  const [expanded, setExpanded] = useState(false)
  const [children, setChildren] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function loadChildren() {
    setLoading(true)
    setError('')
    try {
      const data = await api.browseFolders(entry.path)
      setChildren(data.folders)
    } catch (err) {
      setError(err.message || 'Could not open that folder')
    } finally {
      setLoading(false)
    }
  }

  function toggle() {
    if (!expanded && children === null) loadChildren()
    setExpanded(!expanded)
  }

  const isSelected = selectedPath === entry.path

  return (
    <li className="folder-tree-node">
      <div className="folder-tree-row" style={{ paddingLeft: depth * 18 }}>
        <button type="button" className="folder-tree-toggle" onClick={toggle} aria-label="Expand">
          {loading ? '…' : expanded ? '▾' : '▸'}
        </button>
        <span
          className={`folder-tree-label ${isSelected ? 'selected' : ''}`}
          onClick={() => onSelect(entry.path)}
          onDoubleClick={toggle}
        >
          📁 {entry.name}
        </span>
      </div>
      {error && <div className="hint folder-tree-error">{error}</div>}
      {expanded && children && (
        <ul className="folder-tree-children">
          {children.length === 0 ? (
            <li className="hint folder-tree-empty">(no sub-folders)</li>
          ) : (
            children.map((c) => (
              <TreeNode key={c.path} entry={c} depth={depth + 1} selectedPath={selectedPath} onSelect={onSelect} />
            ))
          )}
        </ul>
      )}
    </li>
  )
}

export default function FolderBrowserModal({ startPath, onSelect, onClose }) {
  const [roots, setRoots] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedPath, setSelectedPath] = useState(startPath || '')
  const [addressValue, setAddressValue] = useState(startPath || '')

  useEffect(() => {
    api
      .browseFolders(null)
      .then((data) => setRoots(data.folders))
      .catch((err) => setError(err.message || 'Failed to load drives'))
      .finally(() => setLoading(false))
  }, [])

  async function goToAddress(e) {
    e.preventDefault()
    if (!addressValue.trim()) return
    setError('')
    try {
      const data = await api.browseFolders(addressValue.trim())
      setSelectedPath(data.path)
      setAddressValue(data.path)
    } catch (err) {
      setError(err.message || 'That path could not be found')
    }
  }

  return (
    <Modal title="Select Source Folder" onClose={onClose} wide>
      <form className="folder-address-bar" onSubmit={goToAddress}>
        <input
          value={addressValue}
          onChange={(e) => setAddressValue(e.target.value)}
          placeholder="\\server\share\Polish\Characters"
        />
        <button type="submit" className="secondary">
          Go
        </button>
      </form>
      {error && <div className="error-banner">{error}</div>}
      <div className="folder-tree-wrapper">
        {loading ? (
          <div className="loading">Loading...</div>
        ) : (
          <ul className="folder-tree-root">
            {roots.map((r) => (
              <TreeNode
                key={r.path}
                entry={r}
                depth={0}
                selectedPath={selectedPath}
                onSelect={(p) => {
                  setSelectedPath(p)
                  setAddressValue(p)
                }}
              />
            ))}
          </ul>
        )}
      </div>
      <div className="folder-selected-path">
        <strong>Selected:</strong> {selectedPath || <span className="hint">(none)</span>}
      </div>
      <div className="modal-actions">
        <button onClick={onClose} className="secondary">
          Cancel
        </button>
        <button onClick={() => onSelect(selectedPath)} disabled={!selectedPath}>
          Select Folder
        </button>
      </div>
    </Modal>
  )
}
