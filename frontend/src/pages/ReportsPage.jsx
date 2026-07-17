import { useEffect, useState } from 'react'
import Sidebar from '../components/Sidebar'
import DateRangeCalendar from '../components/DateRangeCalendar'
import MonthBarChart from '../components/reports/MonthBarChart'
import ComparisonPieChart from '../components/reports/ComparisonPieChart'
import TaxonomyCompletionPie from '../components/reports/TaxonomyCompletionPie'
import WorkedFilesTable from '../components/reports/WorkedFilesTable'
import ExportReportModal from '../components/reports/ExportReportModal'
import { useAuth } from '../context/AuthContext'
import * as api from '../api/client'

function isoDate(d) {
  return d.toISOString().slice(0, 10)
}

// Monday-Sunday of the week containing `d` - matches the app's Monday-first
// week convention used elsewhere (e.g. reports.py's ref.weekday()).
function currentWeekRange() {
  const now = new Date()
  const monday = new Date(now)
  monday.setDate(now.getDate() - ((now.getDay() + 6) % 7))
  const sunday = new Date(monday)
  sunday.setDate(monday.getDate() + 6)
  return { start: isoDate(monday), end: isoDate(sunday) }
}

export default function ReportsPage() {
  const { isAdmin } = useAuth()
  const [range, setRange] = useState(currentWeekRange)
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

  const [exportModalOpen, setExportModalOpen] = useState(false)

  useEffect(() => {
    if (isAdmin) api.getUsers().then(setUsers).catch(() => {})
  }, [isAdmin])

  useEffect(() => {
    let cancelled = false
    async function load() {
      if (!range.start || !range.end || range.end < range.start) return
      setLoading(true)
      setError('')
      try {
        // Taxonomy Progress is an org-wide structural view (admin only) - a
        // worker's own report is just their own completions, scoped server-side
        // by the same /completions call everyone uses. When an admin picks a
        // specific worker, that worker's own progress replaces the org-wide
        // metric the same way it would if that worker viewed this page
        // themselves - Taxonomy Progress stays the org-wide view regardless.
        const rangeParams = { start_date: range.start, end_date: range.end }
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
  }, [range.start, range.end, selectedUserId, isAdmin])

  const progressItems = progress ? progress[progressLevel] : []
  const selectedProgressItem = progressItems.find((i) => String(i.id) === String(progressNodeId)) || progressItems[0]

  async function handleExport(kind, start, end) {
    const params = { start_date: start, end_date: end }
    if (isAdmin && selectedUserId) params.user_id = selectedUserId
    if (kind === 'excel') await api.exportReportExcel(params)
    else await api.exportReportPdf(params)
  }

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content">
        <div className="page-header reports-page-header">
          <div className="reports-header-row">
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
          </div>

          <div className="reports-header-row">
            <DateRangeCalendar value={range} onChange={(start, end) => end && setRange({ start, end })} />
            <button className="secondary reports-export-btn" onClick={() => setExportModalOpen(true)}>
              Export
            </button>
          </div>
        </div>

        {range.end < range.start && <div className="error-banner">End date must not be before start date.</div>}
        {error && <div className="error-banner">{error}</div>}
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
                <h3>
                  Completions - {report.startDate} to {report.endDate}
                </h3>
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
                  <h3>
                    Repairs - {repairs.startDate} to {repairs.endDate}
                  </h3>
                  <MonthBarChart data={repairs.series} />
                </div>
              )}

              <div className="reports-panel reports-panel-2col">
                <h3>Worked Files</h3>
                {!detail ? <div className="loading">Loading...</div> : <WorkedFilesTable rows={detail.rows} />}
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

      {exportModalOpen && (
        <ExportReportModal
          initialStart={range.start}
          initialEnd={range.end}
          onExport={handleExport}
          onClose={() => setExportModalOpen(false)}
        />
      )}
    </div>
  )
}
