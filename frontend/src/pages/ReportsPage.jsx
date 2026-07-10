import { useEffect, useState } from 'react'
import Sidebar from '../components/Sidebar'
import WeekBarChart from '../components/reports/WeekBarChart'
import MonthBarChart from '../components/reports/MonthBarChart'
import ComparisonPieChart from '../components/reports/ComparisonPieChart'
import TaxonomyCompletionPie from '../components/reports/TaxonomyCompletionPie'
import * as api from '../api/client'

export default function ReportsPage() {
  const [referenceDate, setReferenceDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [report, setReport] = useState(null)
  const [progress, setProgress] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [progressLevel, setProgressLevel] = useState('phases') // phases | categories | subCategories
  const [progressNodeId, setProgressNodeId] = useState('')

  async function load() {
    setLoading(true)
    setError('')
    try {
      const [reportData, progressData] = await Promise.all([
        api.getCompletionsReport({ reference_date: referenceDate }),
        api.getTaxonomyProgressReport(),
      ])
      setReport(reportData)
      setProgress(progressData)
    } catch (err) {
      setError(err.message || 'Failed to load reports')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [referenceDate])

  const progressItems = progress ? progress[progressLevel] : []
  const selectedProgressItem = progressItems.find((i) => String(i.id) === String(progressNodeId)) || progressItems[0]

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h1>Reports</h1>
          <label className="reports-date-picker">
            Reference date
            <input type="date" value={referenceDate} onChange={(e) => setReferenceDate(e.target.value)} />
          </label>
        </div>

        {error && <div className="error-banner">{error}</div>}
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
