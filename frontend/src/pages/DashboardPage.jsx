import { useCallback, useEffect, useState } from 'react'
import Sidebar from '../components/Sidebar'
import FilterBar from '../components/FilterBar'
import FilesGrid from '../components/FilesGrid'
import AssignModal from '../components/AssignModal'
import FailAssignmentModal from '../components/FailAssignmentModal'
import FileHistoryModal from '../components/FileHistoryModal'
import ImportModal from '../components/ImportModal'
import MoveFilesModal from '../components/MoveFilesModal'
import { useAuth } from '../context/AuthContext'
import * as api from '../api/client'

const EMPTY_LOOKUPS = { phases: [], statuses: [], categories: [], subCategories: [], roles: [], processTypes: [] }

export default function DashboardPage() {
  const { isAdmin } = useAuth()
  const [lookups, setLookups] = useState(EMPTY_LOOKUPS)
  const [users, setUsers] = useState([])
  const [files, setFiles] = useState([])
  const [filters, setFilters] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [assignTarget, setAssignTarget] = useState(null) // { file, stage }
  const [failTarget, setFailTarget] = useState(null) // file row
  const [historyFileId, setHistoryFileId] = useState(null)
  const [importOpen, setImportOpen] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState([])
  const [moveOpen, setMoveOpen] = useState(false)

  const loadFiles = useCallback(async (activeFilters) => {
    try {
      const data = await api.getFiles(activeFilters)
      setFiles(data)
    } catch (err) {
      setError(err.message || 'Failed to load files')
    }
  }, [])

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
        await loadFiles({})
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load dashboard')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    init()
    return () => {
      cancelled = true
    }
  }, [isAdmin, loadFiles])

  useEffect(() => {
    if (!loading) loadFiles(filters)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters])

  async function handleAssign(fileId, userId, processTypeId) {
    await api.assignFile(fileId, userId, processTypeId)
    await loadFiles(filters)
  }

  async function handleReset(row, stage) {
    if (!window.confirm(`Reset "${row.FileName}"'s ${stage.processTypeName} stage back to Pending?`)) return
    await api.resetFile(row.FileID, stage.processTypeId)
    await loadFiles(filters)
  }

  async function handleComplete(row) {
    if (!row.myActiveAssignmentId) return
    await api.completeAssignment(row.myActiveAssignmentId)
    await loadFiles(filters)
  }

  async function handleFail(reason) {
    await api.failAssignment(failTarget.myActiveAssignmentId, reason)
    await loadFiles(filters)
  }

  async function handleSetActive(row, isActive) {
    try {
      await api.setFileActive(row.FileID, isActive)
      await loadFiles(filters)
    } catch (err) {
      setError(err.message || 'Failed to update file')
    }
  }

  async function handleDelete(row) {
    if (!window.confirm(`Delete "${row.FileName}"? This removes it and its history permanently.`)) return
    try {
      await api.deleteFile(row.FileID)
      await loadFiles(filters)
    } catch (err) {
      setError(err.message || 'Failed to delete file')
    }
  }

  return (
    <div className="app-shell">
      <Sidebar onImportClick={() => setImportOpen(true)} />
      <main className="main-content">
        <div className="page-header">
          <FilterBar filters={filters} onChange={setFilters} lookups={lookups} users={users} isAdmin={isAdmin} />
          {isAdmin && selectedFiles.length > 0 && (
            <button onClick={() => setMoveOpen(true)}>Move Selected ({selectedFiles.length})</button>
          )}
        </div>
        {error && <div className="error-banner">{error}</div>}
        {loading ? (
          <div className="loading">Loading...</div>
        ) : (
          <FilesGrid
            files={files}
            lookups={lookups}
            users={users}
            onAssign={(row, stage) => setAssignTarget({ file: row, stage })}
            onReset={handleReset}
            onComplete={handleComplete}
            onFail={(row) => setFailTarget(row)}
            onHistory={(row) => setHistoryFileId(row.FileID)}
            onSetActive={handleSetActive}
            onDelete={handleDelete}
            onSelectionChanged={setSelectedFiles}
          />
        )}
      </main>

      {assignTarget && (
        <AssignModal
          file={assignTarget.file}
          stage={assignTarget.stage}
          users={users}
          onAssign={handleAssign}
          onClose={() => setAssignTarget(null)}
        />
      )}

      {failTarget && (
        <FailAssignmentModal file={failTarget} onFail={handleFail} onClose={() => setFailTarget(null)} />
      )}

      {historyFileId && <FileHistoryModal fileId={historyFileId} onClose={() => setHistoryFileId(null)} />}

      {importOpen && (
        <ImportModal lookups={lookups} onClose={() => setImportOpen(false)} onImported={() => loadFiles(filters)} />
      )}

      {moveOpen && (
        <MoveFilesModal
          selectedFiles={selectedFiles}
          lookups={lookups}
          onMoveCategory={api.moveCategory}
          onMovePhase={api.movePhase}
          onDone={() => loadFiles(filters)}
          onClose={() => setMoveOpen(false)}
        />
      )}
    </div>
  )
}
