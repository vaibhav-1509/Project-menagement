import { useCallback, useMemo } from 'react'
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
  if (statusName === 'Failed' || statusName === 'Repair') return 'inactive'
  if (statusName === 'Submitted') return 'warning'
  return ''
}

const PRIORITY_VALUES = ['Low', 'Normal', 'High', 'Urgent']

function priorityClass(priority) {
  if (priority === 'Urgent') return 'inactive'
  if (priority === 'High') return 'warning'
  if (priority === 'Low') return 'priority-low'
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
  onApprove,
  onReject,
  onHistory,
  onSetActive,
  onDelete,
  onPriorityChange,
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
        colId: `stage_${pt.id}`,
        minWidth: 80,
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
      { field: 'FileName', headerName: 'File Name', colId: 'FileName', minWidth: 70 },
      {
        headerName: 'Active',
        colId: 'Active',
        minWidth: 60,
        sortable: false,
        filter: false,
        cellRenderer: (p) => (
          <span className={`status-pill ${p.data.IsActive ? 'file-active' : 'file-inactive'}`}>
            {p.data.IsActive ? 'Active' : 'Inactive'}
          </span>
        ),
      },
      {
        headerName: 'Category',
        flex: 1,
        minWidth: 110,
        wrapText: true,
        autoHeight: true,
        valueGetter: (p) => lookupName(lookups.categories, p.data.CategoryID),
      },
      {
        headerName: 'Sub-Category',
        flex: 1,
        minWidth: 110,
        wrapText: true,
        autoHeight: true,
        valueGetter: (p) => lookupName(lookups.subCategories, p.data.SubCategoryID),
      },
      {
        field: 'Priority',
        headerName: 'Priority',
        colId: 'Priority',
        minWidth: 60,
        editable: !readOnly && isAdmin,
        cellEditor: 'agSelectCellEditor',
        cellEditorParams: { values: PRIORITY_VALUES },
        onCellValueChanged: (p) => onPriorityChange?.(p.data.FileID, p.newValue),
        cellRenderer: (p) => <span className={`status-pill ${priorityClass(p.value)}`}>{p.value}</span>,
      },
      {
        headerName: 'Phase',
        flex: 1,
        minWidth: 100,
        sortable: false,
        filter: false,
        cellRenderer: (p) => {
          const row = p.data
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
              {lookupName(lookups.phases, row.PhaseID)}
            </button>
          )
        },
      },
      ...stageColumns,
      {
        field: 'UpdatedAt',
        headerName: 'Updated',
        flex: 1,
        minWidth: 150,
        valueFormatter: (p) => (p.value ? new Date(p.value).toLocaleString() : '-'),
      },
      {
        headerName: 'Actions',
        minWidth: 260,
        flex: 2.6,
        sortable: false,
        filter: false,
        cellRenderer: (p) => {
          const row = p.data
          const assignable = findAssignableStage(row)
          const resettableStage = findResettableStage(row)
          const isSubmitted = resettableStage && resettableStage.statusName === 'Submitted'
          const isMine = row.myActiveAssignmentId != null
          const hasAnyActiveAssignment = (row.processStages || []).some((s) => s.activeAssignmentId)
          return (
            <div className="grid-actions">
              {!readOnly && isAdmin && assignable && (
                <button onClick={() => onAssign(row, assignable)}>Assign {assignable.processTypeName}</button>
              )}
              {!readOnly && isAdmin && isSubmitted && (
                <button
                  onClick={() => onApprove(row, resettableStage)}
                  title="Unlocks the next stage - the file already sits in this worker's Complete folder"
                >
                  Approve {resettableStage.processTypeName}
                </button>
              )}
              {!readOnly && isAdmin && isSubmitted && (
                <button
                  onClick={() => onReject(row, resettableStage)}
                  className="secondary"
                  title="Send back for rework, with a reason - to the same worker or a different eligible one"
                >
                  Reject {resettableStage.processTypeName}
                </button>
              )}
              {!readOnly && isAdmin && resettableStage && !isSubmitted && (
                <button onClick={() => onReset(row, resettableStage)} className="secondary">
                  {resettableStage.statusName === 'Complete' ? 'Undo Complete' : 'Reset'} {resettableStage.processTypeName}
                </button>
              )}
              {!readOnly && isAdmin && resettableStage && !isSubmitted && (
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
      onApprove,
      onReject,
      onHistory,
      onSetActive,
      onDelete,
      onPriorityChange,
    ]
  )

  // File Name, Active, Priority, and each per-process-type stage column show
  // short badge/name text - they shrink to fit their content instead of
  // stretching, so the remaining flexible columns (Category, Sub-Category,
  // Phase, Updated, Actions) get the space and the grid scrolls horizontally
  // once their minWidths no longer all fit.
  const squeezeColIds = useMemo(
    () => ['FileName', 'Active', 'Priority', ...stageColumns.map((c) => c.colId)],
    [stageColumns]
  )

  const autoSizeSqueezeColumns = useCallback(
    (params) => {
      params.api.autoSizeColumns(squeezeColIds)
    },
    [squeezeColIds]
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
        onFirstDataRendered={autoSizeSqueezeColumns}
        onPaginationChanged={autoSizeSqueezeColumns}
      />
    </div>
  )
}
