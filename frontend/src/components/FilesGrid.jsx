import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { AgGridReact } from 'ag-grid-react'
import { AllCommunityModule, ModuleRegistry, colorSchemeDark, themeQuartz } from 'ag-grid-community'
import { useAuth } from '../context/AuthContext'

ModuleRegistry.registerModules([AllCommunityModule])

// Dark UI everywhere (see index.css) - matches this app's own dark palette
// rather than AG Grid's default dark colors, so the grid doesn't look like a
// different app dropped into the page.
const darkGridTheme = themeQuartz.withPart(colorSchemeDark).withParams({
  backgroundColor: '#1b1a22', // --surface
  foregroundColor: '#d8d6e0', // --text
  borderColor: '#2c2a35', // --border
  chromeBackgroundColor: '#171522', // --sidebar-bg
  accentColor: '#8a72ff', // --accent
})

function lookupName(list, id) {
  if (id == null) return '-'
  const item = list.find((i) => i.id === id)
  return item ? item.name : `#${id}`
}

function statusClass(statusName) {
  if (statusName === 'Complete') return 'active'
  if (statusName === 'Failed') return 'inactive'
  return ''
}

// The next assignable stage for a file: the first non-Complete stage whose
// predecessor is Complete (or has no predecessor) and that isn't already
// mid-flight. Sequential gating means at most one stage is ever assignable.
function findAssignableStage(row) {
  const stages = row.processStages || []
  for (let i = 0; i < stages.length; i++) {
    const stage = stages[i]
    if (stage.statusName === 'Complete') continue
    const previous = stages[i - 1]
    if (previous && previous.statusName !== 'Complete') return null
    if (stage.activeAssignmentId) return null
    return stage
  }
  return null
}

// A stage the admin can reset (undo) - either mid-flight (has an active
// assignment) or already marked Complete (e.g. completed by mistake). Only
// the "frontier" stage is resettable: if a later stage has already started,
// resetting an earlier one out from under it would violate sequential
// gating, so that case is refused here rather than left to create an
// inconsistent pipeline state.
function findResettableStage(row) {
  const stages = row.processStages || []
  for (let i = stages.length - 1; i >= 0; i--) {
    const stage = stages[i]
    const isResettable = stage.activeAssignmentId != null || stage.statusName === 'Complete'
    if (!isResettable) continue
    const laterStageStarted = stages
      .slice(i + 1)
      .some((s) => s.statusName !== 'Pending' || s.assignedToUserId != null)
    if (laterStageStarted) return null
    return stage
  }
  return null
}

export default function FilesGrid({
  files,
  lookups,
  users,
  onAssign,
  onReset,
  onRevoke,
  onReopen,
  onComplete,
  onFail,
  onHistory,
  onSetActive,
  onDelete,
  onSelectionChanged,
  readOnly = false,
}) {
  const { claims, isAdmin } = useAuth()
  const currentUserId = claims ? Number(claims.sub) : null
  const navigate = useNavigate()

  const userById = useMemo(() => {
    const map = {}
    users.forEach((u) => {
      map[u.UserID] = u.Username
    })
    return map
  }, [users])

  const stageColumns = useMemo(
    () =>
      lookups.processTypes.map((pt) => ({
        headerName: pt.name,
        flex: 1,
        valueGetter: (p) => {
          const stage = (p.data.processStages || []).find((s) => s.processTypeId === pt.id)
          if (!stage) return 'Pending'
          const who = stage.assignedToUserId ? userById[stage.assignedToUserId] || `#${stage.assignedToUserId}` : null
          return who ? `${stage.statusName} (${who})` : stage.statusName
        },
        cellRenderer: (p) => {
          const stage = (p.data.processStages || []).find((s) => s.processTypeId === pt.id)
          if (!stage) return <span className="status-pill">Pending</span>
          const who = stage.assignedToUserId ? userById[stage.assignedToUserId] || `#${stage.assignedToUserId}` : null
          return (
            <span className={`status-pill ${statusClass(stage.statusName)}`} title={stage.lastFailureReason || ''}>
              {stage.statusName}
              {who ? ` (${who})` : ''}
              {stage.lastFailureReason ? ' ⚠' : ''}
            </span>
          )
        },
      })),
    [lookups.processTypes, userById]
  )

  const columnDefs = useMemo(
    () => [
      { field: 'FileName', headerName: 'File Name', flex: 2 },
      {
        headerName: 'Active',
        flex: 0.7,
        sortable: false,
        filter: false,
        cellRenderer: (p) => (
          <span className={`status-pill ${p.data.IsActive ? 'active' : 'inactive'}`}>
            {p.data.IsActive ? 'Active' : 'Inactive'}
          </span>
        ),
      },
      { headerName: 'Phase', flex: 1, valueGetter: (p) => lookupName(lookups.phases, p.data.PhaseID) },
      { headerName: 'Category', flex: 1, valueGetter: (p) => lookupName(lookups.categories, p.data.CategoryID) },
      {
        headerName: 'Sub-Category',
        flex: 1,
        valueGetter: (p) => lookupName(lookups.subCategories, p.data.SubCategoryID),
      },
      {
        headerName: 'Location',
        flex: 1.4,
        sortable: false,
        filter: false,
        cellRenderer: (p) => {
          const row = p.data
          const parts = [
            lookupName(lookups.phases, row.PhaseID),
            lookupName(lookups.categories, row.CategoryID),
            lookupName(lookups.subCategories, row.SubCategoryID),
          ]
          return (
            <button
              type="button"
              className="link-button"
              onClick={() => {
                const params = new URLSearchParams()
                if (row.PhaseID != null) params.set('phase_id', row.PhaseID)
                if (row.CategoryID != null) params.set('category_id', row.CategoryID)
                if (row.SubCategoryID != null) params.set('sub_category_id', row.SubCategoryID)
                params.set('file_id', row.FileID)
                navigate(`/browse?${params.toString()}`)
              }}
            >
              {parts.join(' > ')}
            </button>
          )
        },
      },
      ...stageColumns,
      {
        field: 'UpdatedAt',
        headerName: 'Updated',
        flex: 1,
        valueFormatter: (p) => (p.value ? new Date(p.value).toLocaleString() : '-'),
      },
      {
        headerName: 'Actions',
        flex: 2.6,
        sortable: false,
        filter: false,
        cellRenderer: (p) => {
          const row = p.data
          const assignable = findAssignableStage(row)
          const resettableStage = findResettableStage(row)
          const isMine = row.myActiveAssignmentId != null
          const hasAnyActiveAssignment = (row.processStages || []).some((s) => s.activeAssignmentId)
          return (
            <div className="grid-actions">
              {!readOnly && isAdmin && assignable && (
                <button onClick={() => onAssign(row, assignable)}>Assign {assignable.processTypeName}</button>
              )}
              {!readOnly && isAdmin && resettableStage && (
                <button onClick={() => onReset(row, resettableStage)} className="secondary">
                  {resettableStage.statusName === 'Complete' ? 'Undo Complete' : 'Reset'} {resettableStage.processTypeName}
                </button>
              )}
              {!readOnly && isAdmin && resettableStage && (
                <button
                  onClick={() => onRevoke(row, resettableStage)}
                  className="secondary"
                  title="Undo an assignment mistake - removes it from that worker's Calendar/Reports history, unlike Reset"
                >
                  Revoke {resettableStage.processTypeName}
                </button>
              )}
              {!readOnly && resettableStage && resettableStage.statusName === 'Complete' && resettableStage.assignedToUserId === currentUserId && (
                <button
                  onClick={() => onReopen(row, resettableStage)}
                  className="secondary"
                  title="Undo your own Complete - reopens it under you so you can keep working"
                >
                  Reopen {resettableStage.processTypeName}
                </button>
              )}
              {!readOnly && isMine && (
                <>
                  <button onClick={() => onComplete(row)}>Complete</button>
                  <button onClick={() => onFail(row)} className="secondary">
                    Fail
                  </button>
                </>
              )}
              <button onClick={() => onHistory(row)} className="secondary">
                History
              </button>
              {!readOnly && isAdmin && (
                <>
                  <button onClick={() => onSetActive(row, !row.IsActive)} className="secondary">
                    {row.IsActive ? 'Deactivate' : 'Activate'}
                  </button>
                  <button
                    onClick={() => onDelete(row)}
                    className="secondary"
                    disabled={hasAnyActiveAssignment}
                    title={hasAnyActiveAssignment ? 'Has an active assignment - reset it first' : ''}
                  >
                    Delete
                  </button>
                </>
              )}
            </div>
          )
        },
      },
    ],
    [
      lookups,
      stageColumns,
      isAdmin,
      currentUserId,
      navigate,
      readOnly,
      onAssign,
      onReset,
      onRevoke,
      onReopen,
      onComplete,
      onFail,
      onHistory,
      onSetActive,
      onDelete,
    ]
  )

  return (
    <div className="grid-wrapper">
      <AgGridReact
        theme={darkGridTheme}
        rowData={files}
        columnDefs={columnDefs}
        getRowId={(p) => String(p.data.FileID)}
        pagination
        paginationPageSize={20}
        rowSelection={isAdmin ? { mode: 'multiRow' } : undefined}
        onSelectionChanged={isAdmin ? (e) => onSelectionChanged?.(e.api.getSelectedRows()) : undefined}
      />
    </div>
  )
}
