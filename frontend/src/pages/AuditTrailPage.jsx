import { useEffect, useState } from 'react'
import Sidebar from '../components/Sidebar'
import * as api from '../api/client'

const PAGE_SIZE = 25

function formatValue(raw) {
  if (raw == null) return '-'
  try {
    const parsed = JSON.parse(raw)
    if (parsed && typeof parsed === 'object') {
      return Object.entries(parsed)
        .map(([k, v]) => `${k}: ${v}`)
        .join(', ')
    }
    return String(parsed)
  } catch {
    return raw
  }
}

export default function AuditTrailPage() {
  const [users, setUsers] = useState([])
  const [entries, setEntries] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [userId, setUserId] = useState('')
  const [action, setAction] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  async function load() {
    setLoading(true)
    setError('')
    try {
      const data = await api.getAuditTrail({
        user_id: userId || null,
        action: action || null,
        date_from: dateFrom || null,
        date_to: dateTo || null,
        page,
        page_size: PAGE_SIZE,
      })
      setEntries(data.items)
      setTotal(data.total)
    } catch (err) {
      setError(err.message || 'Failed to load audit trail')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    api.getUsers().then(setUsers).catch(() => {})
  }, [])

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page])

  function applyFilters(e) {
    e.preventDefault()
    setPage(1)
    load()
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h1>Audit Trail</h1>
        </div>

        <form className="filter-bar" onSubmit={applyFilters}>
          <select value={userId} onChange={(e) => setUserId(e.target.value)}>
            <option value="">All Users</option>
            {users.map((u) => (
              <option key={u.UserID} value={u.UserID}>
                {u.Username}
              </option>
            ))}
          </select>
          <input value={action} onChange={(e) => setAction(e.target.value)} placeholder="Action (e.g. Reset)" />
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          <button type="submit">Apply Filters</button>
        </form>

        {error && <div className="error-banner">{error}</div>}
        {loading ? (
          <div className="loading">Loading...</div>
        ) : (
          <>
            <table className="users-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>File</th>
                  <th>Action</th>
                  <th>Performed By</th>
                  <th>Old Value</th>
                  <th>New Value</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => (
                  <tr key={e.auditTrailId}>
                    <td>{new Date(e.timestamp).toLocaleString()}</td>
                    <td>{e.fileName}</td>
                    <td>{e.action}</td>
                    <td>{e.performedByUsername}</td>
                    <td>{formatValue(e.oldValue)}</td>
                    <td>{formatValue(e.newValue)}</td>
                  </tr>
                ))}
                {entries.length === 0 && (
                  <tr>
                    <td colSpan={6} className="hint">
                      No audit trail entries match these filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>

            <div className="grid-actions">
              <button className="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                Previous
              </button>
              <span className="hint">
                Page {page} of {totalPages} ({total} total)
              </span>
              <button className="secondary" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
                Next
              </button>
            </div>
          </>
        )}
      </main>
    </div>
  )
}
