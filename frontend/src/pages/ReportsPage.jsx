import { useEffect, useState } from 'react'
import Sidebar from '../components/Sidebar'
import WeekBarChart from '../components/reports/WeekBarChart'
import MonthBarChart from '../components/reports/MonthBarChart'
import ComparisonPieChart from '../components/reports/ComparisonPieChart'
import TaxonomyCompletionPie from '../components/reports/TaxonomyCompletionPie'
import { useAuth } from '../context/AuthContext'
import * as api from '../api/client'

export default function ReportsPage() {
  const { isAdmin } = useAuth()
  const [referenceDate, setReferenceDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [report, setReport] = useState(null)
  const [progress, setProgress] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [progressLevel, setProgressLevel] = useState('phases') // phases | categories | subCategories
  const [progressNodeId, setProgressNodeId] = useState('')

  const [users, setUsers] = useState([])
  const [selectedUserId, setSelectedUserId] = useState('') // admin-only: '' = whole team

  const [exportRange, setExportRange] = useState('month')
  const [exporting, setExporting] = useState('') // '' | 'excel' | 'pdf'
  const [exportError, setExportError] = useState('')

  useEffect(() => {
    if (isAdmin) api.getUsers().then(setUsers).catch(() => {})
  }, [isAdmin])

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      try {
        // Taxonomy Progress is an org-wide structural view (admin only) - a
        // worker's own report is just their own completions, scoped server-side
        // by the same /completions call everyone uses. When an admin picks a
        // specific worker, that worker's own progress replaces the org-wide
        // metric the same way it would if that worker viewed this page
        // themselves - Taxonomy Progress stays the org-wide view regardless.
        const completionsParams = { reference_date: referenceDate }
        if (isAdmin && selectedUserId) completionsParams.user_id = selectedUserId
        const [reportData, progressData] = await Promise.all([
          api.getCompletionsReport(completionsParams),
          isAdmin ? api.getTaxonomyProgressReport() : Promise.resolve(null),
        ])
        if (cancelled) return
        setReport(reportData)
        setProgress(progressData)
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
  }, [referenceDate, selectedUserId, isAdmin])

  const progressItems = progress ? progress[progressLevel] : []
  const selectedProgressItem = progressItems.find((i) => String(i.id) === String(progressNodeId)) || progressItems[0]

  async function handleExport(kind) {
    setExportError('')
    setExporting(kind)
    try {
      const params = { range: exportRange, reference_date: referenceDate }
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
            Reference date
            <input type="date" value={referenceDate} onChange={(e) => setReferenceDate(e.target.value)} />
          </label>
          <label>
            Export range
            <select value={exportRange} onChange={(e) => setExportRange(e.target.value)}>
              <option value="day">Day</option>
              <option value="week">Week</option>
              <option value="month">Month</option>
              <option value="year">Year</option>
            </select>
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

        {error && <div className="error-banner">{error}</div>}
        {exportError && <div className="error-banner">{exportError}</div>}
        {loading || !report ? (
          <div className="loading">Loading...</div>
        ) : (
          <>
            <div className="reports-stat-row">
              <div className="reports-stat-card">
                <div className="stat-value">{report.totals.today}</div>
                <div className="stat-label">Completed Today</div>
              </div>
              <div className="reports-stat-card">
                <div className="stat-value">{report.totals.thisWeek}</div>
                <div className="stat-label">This Week</div>
              </div>
              <div className="reports-stat-card">
                <div className="stat-value">{report.totals.thisMonth}</div>
                <div className="stat-label">This Month</div>
              </div>
              <div className="reports-stat-card">
                <div className="stat-value">{report.totals.thisYear}</div>
                <div className="stat-label">This Year</div>
              </div>
            </div>

            <div className="reports-grid">
              <div className="reports-panel">
                <h3>This Week</h3>
                <WeekBarChart data={report.week.days} />
              </div>
              <div className="reports-panel">
                <h3>This Month</h3>
                <MonthBarChart data={report.month.days} />
              </div>
              <div className="reports-panel">
                <h3>Weekly Comparison</h3>
                <ComparisonPieChart data={report.weekComparison} />
              </div>
              <div className="reports-panel">
                <h3>Monthly Comparison</h3>
                <ComparisonPieChart data={report.monthComparison} />
              </div>
              <div className="reports-panel">
                <h3>This Year</h3>
                <ComparisonPieChart data={report.year.months} />
              </div>

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
            </div>
          </>
        )}
      </main>
    </div>
  )
}
