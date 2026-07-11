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
  const [warning, setWarning] = useState('')
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
    setWarning('')
    const result = await api.assignFile(fileId, userId, processTypeId)
    if (result?.warning) setWarning(result.warning)
    await loadFiles(filters)
  }

  async function handleReset(row, stage) {
    const verb = stage.statusName === 'Complete' ? 'Undo the completed' : 'Reset the'
    if (!window.confirm(`${verb} "${row.FileName}"'s ${stage.processTypeName} stage back to Pending?`)) return
    await api.resetFile(row.FileID, stage.processTypeId)
    await loadFiles(filters)
  }

  async function handleRevoke(row, stage) {
    if (
      !window.confirm(
        `Revoke "${row.FileName}"'s ${stage.processTypeName} assignment? Use this only if the assignment itself was a mistake - it removes it from ${stage.assignedToUserId ? 'the assigned worker\'s' : "that worker's"} Calendar/Reports history entirely, unlike Reset.`
      )
    )
      return
    setWarning('')
    try {
      await api.revokeFile(row.FileID, stage.processTypeId)
      await loadFiles(filters)
    } catch (err) {
      setError(err.message || 'Failed to revoke assignment')
    }
  }

  async function handleReopen(row, stage) {
    if (!window.confirm(`Reopen "${row.FileName}"'s ${stage.processTypeName} stage so you can keep working on it?`)) return
    setWarning('')
    try {
      const result = await api.reopenFile(row.FileID, stage.processTypeId)
      if (result?.warning) setWarning(result.warning)
      await loadFiles(filters)
    } catch (err) {
      setError(err.message || 'Failed to reopen stage')
    }
  }

  async function handleComplete(row) {
    if (!row.myActiveAssignmentId) return
    setWarning('')
    const result = await api.completeAssignment(row.myActiveAssignmentId)
    if (result?.warning) setWarning(result.warning)
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
        {warning && <div className="warning-banner">{warning}</div>}
        {loading ? (
          <div className="loading">Loading...</div>
        ) : (
          <FilesGrid
            files={files}
            lookups={lookups}
            users={users}
            onAssign={(row, stage) => setAssignTarget({ file: row, stage })}
            onReset={handleReset}
            onRevoke={handleRevoke}
            onReopen={handleReopen}
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
