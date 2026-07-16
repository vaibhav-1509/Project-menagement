import { useEffect, useState } from 'react'
import Sidebar from '../components/Sidebar'
import MonthBarChart from '../components/reports/MonthBarChart'
import ComparisonPieChart from '../components/reports/ComparisonPieChart'
import TaxonomyCompletionPie from '../components/reports/TaxonomyCompletionPie'
import WorkedFilesTable from '../components/reports/WorkedFilesTable'
import { useAuth } from '../context/AuthContext'
import * as api from '../api/client'

function isoDaysAgo(days) {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString().slice(0, 10)
}

export default function ReportsPage() {
  const { isAdmin } = useAuth()
  const [startDate, setStartDate] = useState(() => isoDaysAgo(29))
  const [endDate, setEndDate] = useState(() => isoDaysAgo(0))
  const [report, setReport] = useState(null)
  const [repairs, setRepairs] = useState(null)
  const [progress, setProgress] = useState(null)
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [progressLevel, setProgressLevel] = useState('phases') // phases | categories | subCategories
  const [progressNodeId, setProgressNodeId] = useState('')

  const [users, setUsers] = useState([])
  const [selectedUserId, setSelectedUserId] = useState('') // admin-only: '' = whole team

  const [exporting, setExporting] = useState('') // '' | 'excel' | 'pdf'
  const [exportError, setExportError] = useState('')

  useEffect(() => {
    if (isAdmin) api.getUsers().then(setUsers).catch(() => {})
  }, [isAdmin])

  useEffect(() => {
    let cancelled = false
    async function load() {
      if (endDate < startDate) return
      setLoading(true)
      setError('')
      try {
        // Taxonomy Progress is an org-wide structural view (admin only) - a
        // worker's own report is just their own completions, scoped server-side
        // by the same /completions call everyone uses. When an admin picks a
        // specific worker, that worker's own progress replaces the org-wide
        // metric the same way it would if that worker viewed this page
        // themselves - Taxonomy Progress stays the org-wide view regardless.
        const rangeParams = { start_date: startDate, end_date: endDate }
        if (isAdmin && selectedUserId) rangeParams.user_id = selectedUserId
        const [reportData, repairsData, progressData, detailData] = await Promise.all([
          api.getCompletionsReport(rangeParams),
          api.getRepairsReport(rangeParams),
          isAdmin ? api.getTaxonomyProgressReport() : Promise.resolve(null),
          api.getReportsDetail(rangeParams),
        ])
        if (cancelled) return
        setReport(reportData)
        setRepairs(repairsData)
        setProgress(progressData)
        setDetail(detailData)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load reports')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [startDate, endDate, selectedUserId, isAdmin])

  const progressItems = progress ? progress[progressLevel] : []
  const selectedProgressItem = progressItems.find((i) => String(i.id) === String(progressNodeId)) || progressItems[0]

  async function handleExport(kind) {
    setExportError('')
    setExporting(kind)
    try {
      const params = { start_date: startDate, end_date: endDate }
      if (isAdmin && selectedUserId) params.user_id = selectedUserId
      if (kind === 'excel') await api.exportReportExcel(params)
      else await api.exportReportPdf(params)
    } catch (err) {
      setExportError(err.message || `Failed to export ${kind}`)
    } finally {
      setExporting('')
    }
  }

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h1>
            {isAdmin
              ? selectedUserId
                ? `${users.find((u) => String(u.UserID) === String(selectedUserId))?.Username || ''}'s Reports`
                : 'Reports'
              : 'My Reports'}
          </h1>
          {!isAdmin && <p className="hint">Your own completions and activity - not the whole team's.</p>}
          {isAdmin && (
            <label>
              Worker
              <select value={selectedUserId} onChange={(e) => setSelectedUserId(e.target.value)}>
                <option value="">Whole team</option>
                {users.map((u) => (
                  <option key={u.UserID} value={u.UserID}>
                    {u.Username}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="reports-date-picker">
            Start date
            <input type="date" value={startDate} max={endDate} onChange={(e) => setStartDate(e.target.value)} />
          </label>
          <label className="reports-date-picker">
            End date
            <input type="date" value={endDate} min={startDate} onChange={(e) => setEndDate(e.target.value)} />
          </label>
          <div className="reports-export-actions">
            <button
              className="secondary"
              disabled={exporting !== ''}
              onClick={() => handleExport('excel')}
              title="Excel: file name, process type, assigned/completion timestamps for the selected range and user"
            >
              {exporting === 'excel' ? 'Exporting...' : 'Export Excel'}
            </button>
            <button
              className="secondary"
              disabled={exporting !== ''}
              onClick={() => handleExport('pdf')}
              title="PDF: full report including charts for the selected range and user"
            >
              {exporting === 'pdf' ? 'Exporting...' : 'Export PDF'}
            </button>
          </div>
        </div>

        {endDate < startDate && <div className="error-banner">End date must not be before start date.</div>}
        {error && <div className="error-banner">{error}</div>}
        {exportError && <div className="error-banner">{exportError}</div>}
        {loading || !report ? (
          <div className="loading">Loading...</div>
        ) : (
          <>
            <div className="reports-stat-row">
              <div className="reports-stat-card">
                <div className="stat-value">{report.totalInRange}</div>
                <div className="stat-label">Completed in Range</div>
              </div>
              {repairs && (
                <div className="reports-stat-card">
                  <div className="stat-value">{repairs.totalInRange}</div>
                  <div className="stat-label">Repairs in Range</div>
                </div>
              )}
            </div>

            <div className="reports-grid">
              <div className="reports-panel reports-panel-wide">
                <h3>Completions - {report.startDate} to {report.endDate}</h3>
                <MonthBarChart data={report.series} />
              </div>
              <div className="reports-panel">
                <h3>vs. Previous Period</h3>
                <ComparisonPieChart data={report.comparison} />
              </div>
              <div className="reports-panel">
                <h3>By Process Type</h3>
                <ComparisonPieChart data={report.processTypeBreakdown} />
              </div>
              {repairs && (
                <div className="reports-panel reports-panel-wide">
                  <h3>Repairs - {repairs.startDate} to {repairs.endDate}</h3>
                  <MonthBarChart data={repairs.series} />
                </div>
              )}

              {progress && (
                <div className="reports-panel reports-panel-wide">
                  <h3>Taxonomy Progress</h3>
                  <div className="filter-bar">
                    <select
                      value={progressLevel}
                      onChange={(e) => {
                        setProgressLevel(e.target.value)
                        setProgressNodeId('')
                      }}
                    >
                      <option value="phases">Phases</option>
                      <option value="categories">Categories</option>
                      <option value="subCategories">Sub-Categories</option>
                    </select>
                    <select value={progressNodeId} onChange={(e) => setProgressNodeId(e.target.value)}>
                      {progressItems.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <TaxonomyCompletionPie item={selectedProgressItem} />
                </div>
              )}

              {detail && (
                <div className="reports-panel reports-panel-wide">
                  <h3>Worked Files - {startDate} to {endDate}</h3>
                  <WorkedFilesTable rows={detail.rows} />
                </div>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  )
}
