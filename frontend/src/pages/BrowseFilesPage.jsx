import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import Sidebar from '../components/Sidebar'
import FilesGrid from '../components/FilesGrid'
import SearchBox from '../components/SearchBox'
import FileHistoryModal from '../components/FileHistoryModal'
import { useAuth } from '../context/AuthContext'
import * as api from '../api/client'

const EMPTY_LOOKUPS = { phases: [], statuses: [], categories: [], subCategories: [], roles: [], processTypes: [] }

export default function BrowseFilesPage() {
  const { isAdmin } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const [lookups, setLookups] = useState(EMPTY_LOOKUPS)
  const [users, setUsers] = useState([])
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [phaseId, setPhaseId] = useState(searchParams.get('phase_id') || null)
  const [categoryId, setCategoryId] = useState(searchParams.get('category_id') || null)
  const [subCategoryId, setSubCategoryId] = useState(searchParams.get('sub_category_id') || null)
  const [search, setSearch] = useState('')
  const [historyFileId, setHistoryFileId] = useState(null)

  const filters = {
    phase_id: phaseId,
    category_id: categoryId,
    sub_category_id: subCategoryId,
    search: search || null,
  }

  async function loadFiles() {
    try {
      setFiles(await api.getFiles(filters))
    } catch (err) {
      setError(err.message || 'Failed to load files')
    }
  }

  useEffect(() => {
    let cancelled = false
    async function init() {
      setLoading(true)
      try {
        const [lookupsData, usersData] = await Promise.all([
          api.getLookups(),
          isAdmin ? api.getUsers() : Promise.resolve([]),
        ])
        if (cancelled) return
        setLookups(lookupsData)
        setUsers(usersData)
        await loadFiles()
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load browse page')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    init()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin])

  useEffect(() => {
    if (!loading) loadFiles()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phaseId, categoryId, subCategoryId, search])

  function selectPhase(id) {
    setPhaseId(id)
    setCategoryId(null)
    setSubCategoryId(null)
    setSearchParams(id ? { phase_id: id } : {})
  }

  function selectCategory(phaseIdForCat, id) {
    setPhaseId(phaseIdForCat)
    setCategoryId(id)
    setSubCategoryId(null)
    setSearchParams({ phase_id: phaseIdForCat, category_id: id })
  }

  function selectSubCategory(phaseIdForSub, categoryIdForSub, id) {
    setPhaseId(phaseIdForSub)
    setCategoryId(categoryIdForSub)
    setSubCategoryId(id)
    setSearchParams({ phase_id: phaseIdForSub, category_id: categoryIdForSub, sub_category_id: id })
  }

  function clearSelection() {
    setPhaseId(null)
    setCategoryId(null)
    setSubCategoryId(null)
    setSearchParams({})
  }

  const categoriesForPhase = (pid) => lookups.categories.filter((c) => String(c.phaseId) === String(pid))
  const subCategoriesForCategory = (cid) => lookups.subCategories.filter((sc) => String(sc.categoryId) === String(cid))

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h1>Browse Files</h1>
        </div>
        {error && <div className="error-banner">{error}</div>}
        <div className="browse-layout">
          <div className="browse-tree taxonomy-tree">
            <div
              className={`taxonomy-node-header browse-tree-root ${!phaseId ? 'selected' : ''}`}
              onClick={clearSelection}
            >
              All Files
            </div>
            {lookups.phases.map((phase) => (
              <div key={phase.id} className="taxonomy-node taxonomy-phase">
                <div
                  className={`taxonomy-node-header ${String(phaseId) === String(phase.id) && !categoryId ? 'selected' : ''}`}
                  onClick={() => selectPhase(phase.id)}
                >
                  <strong>{phase.name}</strong>
                </div>
                {String(phaseId) === String(phase.id) && (
                  <div className="taxonomy-children">
                    {categoriesForPhase(phase.id).map((category) => (
                      <div key={category.id} className="taxonomy-node taxonomy-category">
                        <div
                          className={`taxonomy-node-header ${
                            String(categoryId) === String(category.id) && !subCategoryId ? 'selected' : ''
                          }`}
                          onClick={() => selectCategory(phase.id, category.id)}
                        >
                          {category.name}
                        </div>
                        {String(categoryId) === String(category.id) && (
                          <div className="taxonomy-children">
                            {subCategoriesForCategory(category.id).map((sc) => (
                              <div
                                key={sc.id}
                                className={`taxonomy-node-header ${
                                  String(subCategoryId) === String(sc.id) ? 'selected' : ''
                                }`}
                                onClick={() => selectSubCategory(phase.id, category.id, sc.id)}
                              >
                                {sc.name}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="browse-results">
            <SearchBox value={search} onChange={setSearch} />
            {loading ? (
              <div className="loading">Loading...</div>
            ) : (
              <FilesGrid
                files={files}
                lookups={lookups}
                users={users}
                onHistory={(row) => setHistoryFileId(row.FileID)}
                readOnly
              />
            )}
          </div>
        </div>
      </main>

      {historyFileId && <FileHistoryModal fileId={historyFileId} onClose={() => setHistoryFileId(null)} />}
    </div>
  )
}
