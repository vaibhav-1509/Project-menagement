import { useEffect, useState } from 'react'
import Sidebar from '../components/Sidebar'
import * as api from '../api/client'

export default function ProcessTypesPage() {
  const [processTypes, setProcessTypes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [newName, setNewName] = useState('')

  const [editingId, setEditingId] = useState(null)
  const [editingValue, setEditingValue] = useState('')

  async function load() {
    setLoading(true)
    try {
      setProcessTypes(await api.getProcessTypes())
    } catch (err) {
      setError(err.message || 'Failed to load process types')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function run(action) {
    setError('')
    try {
      await action()
      await load()
    } catch (err) {
      setError(err.message || 'Action failed')
    }
  }

  async function handleAdd(e) {
    e.preventDefault()
    await run(async () => {
      await api.createProcessType(newName)
      setNewName('')
    })
  }

  function move(index, direction) {
    const target = index + direction
    if (target < 0 || target >= processTypes.length) return
    const reordered = [...processTypes]
    ;[reordered[index], reordered[target]] = [reordered[target], reordered[index]]
    run(() => api.reorderProcessTypes(reordered.map((pt) => pt.id)))
  }

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h1>Process Types</h1>
        </div>
        <p className="hint">
          The ordered pipeline every file moves through (Polish, GLB, Render by default). A file's next stage
          can't be assigned until the previous one is Complete. Use the arrows to reorder.
        </p>
        {error && <div className="error-banner">{error}</div>}
        {loading ? (
          <div className="loading">Loading...</div>
        ) : (
          <div className="taxonomy-tree">
            {processTypes.map((pt, index) => (
              <div key={pt.id} className="taxonomy-node taxonomy-phase">
                <div className="taxonomy-node-header">
                  <div className="process-type-order">
                    <button
                      type="button"
                      className="secondary"
                      disabled={index === 0}
                      onClick={() => move(index, -1)}
                      title="Move up"
                    >
                      &uarr;
                    </button>
                    <button
                      type="button"
                      className="secondary"
                      disabled={index === processTypes.length - 1}
                      onClick={() => move(index, 1)}
                      title="Move down"
                    >
                      &darr;
                    </button>
                  </div>

                  {editingId === pt.id ? (
                    <span className="taxonomy-name-edit">
                      <input
                        autoFocus
                        value={editingValue}
                        onChange={(e) => setEditingValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault()
                            run(() => api.renameProcessType(pt.id, editingValue.trim())).then(() => {
                              setEditingId(null)
                              setEditingValue('')
                            })
                          } else if (e.key === 'Escape') {
                            setEditingId(null)
                          }
                        }}
                      />
                      <button
                        type="button"
                        onClick={() =>
                          run(() => api.renameProcessType(pt.id, editingValue.trim())).then(() => {
                            setEditingId(null)
                            setEditingValue('')
                          })
                        }
                      >
                        Save
                      </button>
                      <button type="button" className="secondary" onClick={() => setEditingId(null)}>
                        Cancel
                      </button>
                    </span>
                  ) : (
                    <>
                      <strong>{pt.name}</strong>
                      <button
                        type="button"
                        className="secondary taxonomy-edit-btn"
                        onClick={() => {
                          setEditingId(pt.id)
                          setEditingValue(pt.name)
                        }}
                      >
                        Edit
                      </button>
                    </>
                  )}

                  <span className={`status-pill ${pt.isActive ? 'active' : 'inactive'}`}>
                    {pt.isActive ? 'Active' : 'Inactive'}
                  </span>
                  <span className="hint">{pt.workerCount} worker(s) enabled</span>

                  <div className="taxonomy-node-actions">
                    <button
                      className="secondary"
                      onClick={() => run(() => api.setProcessTypeActive(pt.id, !pt.isActive))}
                    >
                      {pt.isActive ? 'Deactivate' : 'Activate'}
                    </button>
                    <button
                      className="secondary"
                      disabled={pt.workerCount > 0}
                      title={pt.workerCount > 0 ? 'Still referenced by worker folder configurations' : ''}
                      onClick={() => {
                        if (window.confirm(`Delete process type "${pt.name}"?`)) run(() => api.deleteProcessType(pt.id))
                      }}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}

            <form onSubmit={handleAdd} className="taxonomy-form taxonomy-form-top">
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="New process type name"
                required
              />
              <button type="submit">+ Add Process Type</button>
            </form>
          </div>
        )}
      </main>
    </div>
  )
}
