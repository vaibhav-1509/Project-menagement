import { useEffect, useState } from 'react'
import Sidebar from '../components/Sidebar'
import * as api from '../api/client'

const EMPTY_TAXONOMY = { phases: [], categories: [], subCategories: [] }

export default function TaxonomyPage() {
  const [taxonomy, setTaxonomy] = useState(EMPTY_TAXONOMY)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [newPhaseName, setNewPhaseName] = useState('')
  const [newCategoryNameByPhase, setNewCategoryNameByPhase] = useState({})
  const [newSubCategoryNameByCategory, setNewSubCategoryNameByCategory] = useState({})

  const [editingKey, setEditingKey] = useState(null)
  const [editingValue, setEditingValue] = useState('')

  async function load() {
    setLoading(true)
    try {
      setTaxonomy(await api.getTaxonomyAdmin())
    } catch (err) {
      setError(err.message || 'Failed to load taxonomy')
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

  async function handleAddPhase(e) {
    e.preventDefault()
    await run(async () => {
      await api.createPhase(newPhaseName)
      setNewPhaseName('')
    })
  }

  async function handleAddCategory(e, phaseId) {
    e.preventDefault()
    const name = newCategoryNameByPhase[phaseId] || ''
    await run(async () => {
      await api.createCategory(phaseId, name)
      setNewCategoryNameByPhase({ ...newCategoryNameByPhase, [phaseId]: '' })
    })
  }

  async function handleAddSubCategory(e, categoryId) {
    e.preventDefault()
    const name = newSubCategoryNameByCategory[categoryId] || ''
    await run(async () => {
      await api.createSubCategory(categoryId, name)
      setNewSubCategoryNameByCategory({ ...newSubCategoryNameByCategory, [categoryId]: '' })
    })
  }

  function StatusPill({ isActive }) {
    return <span className={`status-pill ${isActive ? 'active' : 'inactive'}`}>{isActive ? 'Active' : 'Inactive'}</span>
  }

  function startEditing(key, currentName) {
    setEditingKey(key)
    setEditingValue(currentName)
  }

  function cancelEditing() {
    setEditingKey(null)
    setEditingValue('')
  }

  async function saveEditing(renameFn) {
    const name = editingValue.trim()
    if (!name) return
    await run(() => renameFn(name))
    setEditingKey(null)
    setEditingValue('')
  }

  function EditableName({ nodeKey, name, onRename, tag: Tag = 'span' }) {
    if (editingKey === nodeKey) {
      return (
        <span className="taxonomy-name-edit">
          <input
            autoFocus
            value={editingValue}
            onChange={(e) => setEditingValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                saveEditing(onRename)
              } else if (e.key === 'Escape') {
                cancelEditing()
              }
            }}
          />
          <button type="button" onClick={() => saveEditing(onRename)}>
            Save
          </button>
          <button type="button" className="secondary" onClick={cancelEditing}>
            Cancel
          </button>
        </span>
      )
    }
    return (
      <>
        <Tag>{name}</Tag>
        <button type="button" className="secondary taxonomy-edit-btn" onClick={() => startEditing(nodeKey, name)}>
          Edit
        </button>
      </>
    )
  }

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h1>Phases, Categories &amp; Sub-Categories</h1>
        </div>
        <p className="hint">
          Every phase defines its own category list, and every category defines its own sub-category list -
          Phase &gt; Category &gt; Sub-Category. Deactivate to hide something from new selections without
          losing history; delete is only allowed once nothing references it.
        </p>
        {error && <div className="error-banner">{error}</div>}
        {loading ? (
          <div className="loading">Loading...</div>
        ) : (
          <div className="taxonomy-tree">
            {taxonomy.phases.map((phase) => {
              const categories = taxonomy.categories.filter((c) => c.phaseId === phase.id)
              const canDeletePhase = phase.fileCount === 0 && phase.userCount === 0 && categories.length === 0

              return (
                <div key={phase.id} className="taxonomy-node taxonomy-phase">
                  <div className="taxonomy-node-header">
                    <EditableName
                      nodeKey={`phase-${phase.id}`}
                      name={phase.name}
                      tag="strong"
                      onRename={(name) => api.renamePhase(phase.id, name)}
                    />
                    <StatusPill isActive={phase.isActive} />
                    <span className="hint">
                      {phase.fileCount} file(s) &middot; {phase.userCount} user(s)
                    </span>
                    <div className="taxonomy-node-actions">
                      <button
                        className="secondary"
                        onClick={() => run(() => api.setPhaseActive(phase.id, !phase.isActive))}
                      >
                        {phase.isActive ? 'Deactivate' : 'Activate'}
                      </button>
                      <button
                        className="secondary"
                        disabled={!canDeletePhase}
                        title={canDeletePhase ? '' : 'Still referenced by files, users, or categories'}
                        onClick={() => {
                          if (window.confirm(`Delete phase "${phase.name}"?`)) run(() => api.deletePhase(phase.id))
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  </div>

                  <div className="taxonomy-children">
                    {categories.map((category) => {
                      const subCategories = taxonomy.subCategories.filter((sc) => sc.categoryId === category.id)
                      const canDeleteCategory = category.fileCount === 0

                      return (
                        <div key={category.id} className="taxonomy-node taxonomy-category">
                          <div className="taxonomy-node-header">
                            <EditableName
                              nodeKey={`category-${category.id}`}
                              name={category.name}
                              onRename={(name) => api.renameCategory(category.id, name)}
                            />
                            <StatusPill isActive={category.isActive} />
                            <span className="hint">{category.fileCount} file(s)</span>
                            <div className="taxonomy-node-actions">
                              <button
                                className="secondary"
                                onClick={() => run(() => api.setCategoryActive(category.id, !category.isActive))}
                              >
                                {category.isActive ? 'Deactivate' : 'Activate'}
                              </button>
                              <button
                                className="secondary"
                                disabled={!canDeleteCategory}
                                title={canDeleteCategory ? '' : 'Still referenced by files'}
                                onClick={() => {
                                  if (window.confirm(`Delete category "${category.name}"?`))
                                    run(() => api.deleteCategory(category.id))
                                }}
                              >
                                Delete
                              </button>
                            </div>
                          </div>

                          <div className="taxonomy-children">
                            {subCategories.map((sc) => {
                              const canDeleteSub = sc.fileCount === 0
                              return (
                                <div key={sc.id} className="taxonomy-node taxonomy-subcategory">
                                  <div className="taxonomy-node-header">
                                    <EditableName
                                      nodeKey={`subcategory-${sc.id}`}
                                      name={sc.name}
                                      onRename={(name) => api.renameSubCategory(sc.id, name)}
                                    />
                                    <StatusPill isActive={sc.isActive} />
                                    <span className="hint">{sc.fileCount} file(s)</span>
                                    <div className="taxonomy-node-actions">
                                      <button
                                        className="secondary"
                                        onClick={() => run(() => api.setSubCategoryActive(sc.id, !sc.isActive))}
                                      >
                                        {sc.isActive ? 'Deactivate' : 'Activate'}
                                      </button>
                                      <button
                                        className="secondary"
                                        disabled={!canDeleteSub}
                                        title={canDeleteSub ? '' : 'Still referenced by files'}
                                        onClick={() => {
                                          if (window.confirm(`Delete sub-category "${sc.name}"?`))
                                            run(() => api.deleteSubCategory(sc.id))
                                        }}
                                      >
                                        Delete
                                      </button>
                                    </div>
                                  </div>
                                </div>
                              )
                            })}
                            <form onSubmit={(e) => handleAddSubCategory(e, category.id)} className="taxonomy-form">
                              <input
                                value={newSubCategoryNameByCategory[category.id] || ''}
                                onChange={(e) =>
                                  setNewSubCategoryNameByCategory({
                                    ...newSubCategoryNameByCategory,
                                    [category.id]: e.target.value,
                                  })
                                }
                                placeholder={`New sub-category in ${category.name}`}
                                required
                              />
                              <button type="submit">+ Add Sub-Category</button>
                            </form>
                          </div>
                        </div>
                      )
                    })}
                    <form onSubmit={(e) => handleAddCategory(e, phase.id)} className="taxonomy-form">
                      <input
                        value={newCategoryNameByPhase[phase.id] || ''}
                        onChange={(e) =>
                          setNewCategoryNameByPhase({ ...newCategoryNameByPhase, [phase.id]: e.target.value })
                        }
                        placeholder={`New category in ${phase.name}`}
                        required
                      />
                      <button type="submit">+ Add Category</button>
                    </form>
                  </div>
                </div>
              )
            })}

            {taxonomy.phases.length === 0 && (
              <p className="hint">No phases yet - add one below to get started.</p>
            )}

            <form onSubmit={handleAddPhase} className="taxonomy-form taxonomy-form-top">
              <input
                value={newPhaseName}
                onChange={(e) => setNewPhaseName(e.target.value)}
                placeholder="New phase name"
                required
              />
              <button type="submit">+ Add Phase</button>
            </form>
          </div>
        )}
      </main>
    </div>
  )
}
