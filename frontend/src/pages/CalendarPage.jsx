import { useEffect, useState } from 'react'
import Sidebar from '../components/Sidebar'
import Modal from '../components/Modal'
import * as api from '../api/client'

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]
const WEEKDAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

function pad2(n) {
  return String(n).padStart(2, '0')
}

export default function CalendarPage() {
  const today = new Date()
  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth() + 1) // 1-12
  const [days, setDays] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [selectedDate, setSelectedDate] = useState(null)
  const [dayEvents, setDayEvents] = useState(null)
  const [dayLoading, setDayLoading] = useState(false)

  async function load() {
    setLoading(true)
    setError('')
    try {
      const data = await api.getCalendarMonth(year, month)
      setDays(data.days)
    } catch (err) {
      setError(err.message || 'Failed to load calendar')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [year, month])

  function goToPrevMonth() {
    if (month === 1) {
      setMonth(12)
      setYear(year - 1)
    } else {
      setMonth(month - 1)
    }
  }

  function goToNextMonth() {
    if (month === 12) {
      setMonth(1)
      setYear(year + 1)
    } else {
      setMonth(month + 1)
    }
  }

  function goToToday() {
    setYear(today.getFullYear())
    setMonth(today.getMonth() + 1)
  }

  async function openDay(dateIso) {
    setSelectedDate(dateIso)
    setDayLoading(true)
    try {
      const data = await api.getCalendarDay(dateIso)
      setDayEvents(data.events)
    } catch (err) {
      setError(err.message || 'Failed to load day detail')
    } finally {
      setDayLoading(false)
    }
  }

  const firstWeekday = new Date(year, month - 1, 1).getDay()
  const leadingBlanks = Array.from({ length: firstWeekday })

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h1>Calendar</h1>
        </div>

        <div className="calendar-controls">
          <button className="secondary" onClick={goToPrevMonth}>
            &lt;
          </button>
          <strong>
            {MONTH_NAMES[month - 1]} {year}
          </strong>
          <button className="secondary" onClick={goToNextMonth}>
            &gt;
          </button>
          <button className="secondary" onClick={goToToday}>
            Today
          </button>
        </div>

        {error && <div className="error-banner">{error}</div>}
        {loading ? (
          <div className="loading">Loading...</div>
        ) : (
          <div className="calendar-grid">
            {WEEKDAY_LABELS.map((label) => (
              <div key={label} className="calendar-weekday-label">
                {label}
              </div>
            ))}
            {leadingBlanks.map((_, i) => (
              <div key={`blank-${i}`} className="calendar-day calendar-day-blank" />
            ))}
            {days.map((day) => {
              const total = day.assignedCount + day.completedCount + day.failedCount
              const dayNum = Number(day.date.slice(-2))
              const isToday =
                year === today.getFullYear() && month === today.getMonth() + 1 && dayNum === today.getDate()
              return (
                <div
                  key={day.date}
                  className={`calendar-day ${isToday ? 'calendar-day-today' : ''}`}
                  onClick={() => openDay(day.date)}
                >
                  <div className="calendar-day-number">{dayNum}</div>
                  {total > 0 && (
                    <div className="calendar-day-badges">
                      {day.assignedCount > 0 && <span className="status-pill">{day.assignedCount} assigned</span>}
                      {day.completedCount > 0 && (
                        <span className="status-pill active">{day.completedCount} completed</span>
                      )}
                      {day.failedCount > 0 && <span className="status-pill inactive">{day.failedCount} failed</span>}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </main>

      {selectedDate && (
        <Modal title={`Activity on ${selectedDate}`} onClose={() => setSelectedDate(null)}>
          {dayLoading ? (
            <div className="loading">Loading...</div>
          ) : (
            <div className="taxonomy-tree">
              {(dayEvents || []).length === 0 && <p className="hint">No activity on this day.</p>}
              {(dayEvents || []).map((e, i) => (
                <div key={i} className="taxonomy-node">
                  <div className="taxonomy-node-header">
                    <strong>{e.fileName}</strong>
                    <span className="hint">{e.processTypeName}</span>
                    <span className="status-pill">{e.event}</span>
                    <span className="hint">{e.assignedToUsername}</span>
                    <span className="hint">{new Date(e.eventTs).toLocaleTimeString()}</span>
                  </div>
                  {e.failureReason && <p className="hint">Reason: {e.failureReason}</p>}
                </div>
              ))}
            </div>
          )}
        </Modal>
      )}
    </div>
  )
}
