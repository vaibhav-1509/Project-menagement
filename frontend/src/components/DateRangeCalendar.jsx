import { useEffect, useRef, useState } from 'react'

const WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const MONTH_LABELS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
]

function pad(n) {
  return String(n).padStart(2, '0')
}

function toIso(year, month, day) {
  return `${year}-${pad(month + 1)}-${pad(day)}`
}

function daysInMonth(year, month) {
  return new Date(year, month + 1, 0).getDate()
}

function formatShort(iso) {
  if (!iso) return ''
  const d = new Date(`${iso}T00:00:00`)
  return `${d.getDate()} ${MONTH_LABELS[d.getMonth()].slice(0, 3)} ${d.getFullYear()}`
}

function formatTrigger(start, end) {
  if (!start) return 'Select date'
  if (!end || end === start) return formatShort(start)
  return `${formatShort(start)} - ${formatShort(end)}`
}

// JS getDay() is Sun=0..Sat=6 - convert to Mon=0..Sun=6 to match the rest of
// the app's Monday-first week convention (see reports.py's ref.weekday()).
function mondayFirstWeekday(year, month, day) {
  return (new Date(year, month, day).getDay() + 6) % 7
}

/** Single-month calendar with range selection (click a start day, click a
 * second day to complete the range) and drill-up navigation: click the month
 * name for a 12-month grid, click the year for a year grid, so older reports
 * are reachable without paging one month at a time. */
export default function DateRangeCalendar({ value, onChange, alwaysExpanded = false }) {
  const today = new Date()
  const initialDate = value?.start ? new Date(`${value.start}T00:00:00`) : today

  const [viewYear, setViewYear] = useState(initialDate.getFullYear())
  const [viewMonth, setViewMonth] = useState(initialDate.getMonth())
  const [viewMode, setViewMode] = useState('days') // 'days' | 'months' | 'years'
  const [yearsPageStart, setYearsPageStart] = useState(initialDate.getFullYear() - 5)

  // Selection lives in local state, not derived straight from `value` - the
  // parent only ever receives a *complete* range worth reacting to (it skips
  // reloading data on a lone start-date click), so if we read start/end
  // straight from props, clicking a first day would never visibly select
  // anything (the parent hasn't changed value yet) and the very next click
  // would misread the stale old range as "already complete" and restart
  // instead of finishing it. Owning the selection locally, and syncing back
  // in only when the parent's value genuinely changes (e.g. an Export popup
  // preset button), avoids that dead end.
  const [start, setStart] = useState(value?.start || null)
  const [end, setEnd] = useState(value?.end || null)

  // Collapsed by default - shows a compact trigger button with the current
  // selection, expands into the full calendar (like a dropdown menu) on click.
  const [expanded, setExpanded] = useState(false)
  const rootRef = useRef(null)

  useEffect(() => {
    setStart(value?.start || null)
    setEnd(value?.end || null)
  }, [value?.start, value?.end])

  useEffect(() => {
    if (!expanded) return
    function onOutsideClick(e) {
      if (rootRef.current && !rootRef.current.contains(e.target)) setExpanded(false)
    }
    document.addEventListener('mousedown', onOutsideClick)
    return () => document.removeEventListener('mousedown', onOutsideClick)
  }, [expanded])

  // Follow the selected start date's month when it changes from outside
  // (e.g. an Export popup preset button), so the visible month always makes
  // sense relative to what's selected.
  useEffect(() => {
    if (!start) return
    const d = new Date(`${start}T00:00:00`)
    setViewYear(d.getFullYear())
    setViewMonth(d.getMonth())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [start])

  function selectDay(iso) {
    let newStart, newEnd
    if (!start || end) {
      newStart = iso
      newEnd = null
    } else if (iso < start) {
      newStart = iso
      newEnd = start
    } else {
      newStart = start
      newEnd = iso
    }
    setStart(newStart)
    setEnd(newEnd)
    onChange(newStart, newEnd)
    if (newEnd && !alwaysExpanded) setExpanded(false)
  }

  function goPrev() {
    if (viewMode === 'days') {
      if (viewMonth === 0) {
        setViewMonth(11)
        setViewYear((y) => y - 1)
      } else {
        setViewMonth((m) => m - 1)
      }
    } else if (viewMode === 'months') {
      setViewYear((y) => y - 1)
    } else {
      setYearsPageStart((y) => y - 12)
    }
  }

  function goNext() {
    if (viewMode === 'days') {
      if (viewMonth === 11) {
        setViewMonth(0)
        setViewYear((y) => y + 1)
      } else {
        setViewMonth((m) => m + 1)
      }
    } else if (viewMode === 'months') {
      setViewYear((y) => y + 1)
    } else {
      setYearsPageStart((y) => y + 12)
    }
  }

  const todayIso = toIso(today.getFullYear(), today.getMonth(), today.getDate())

  function renderDays() {
    const total = daysInMonth(viewYear, viewMonth)
    const leadingBlanks = mondayFirstWeekday(viewYear, viewMonth, 1)
    const cells = Array(leadingBlanks).fill(null)
    for (let d = 1; d <= total; d++) cells.push(d)

    return (
      <>
        <div className="cal-weekdays">
          {WEEKDAY_LABELS.map((w) => (
            <div key={w} className="cal-weekday">
              {w}
            </div>
          ))}
        </div>
        <div className="cal-days">
          {cells.map((d, i) => {
            if (d === null) return <div key={`blank-${i}`} className="cal-day cal-day-blank" />
            const iso = toIso(viewYear, viewMonth, d)
            const classes = ['cal-day']
            if (iso === start || iso === end) classes.push('cal-day-selected')
            if (start && end && iso > start && iso < end) classes.push('cal-day-in-range')
            if (iso === todayIso) classes.push('cal-day-today')
            return (
              <button type="button" key={iso} className={classes.join(' ')} onClick={() => selectDay(iso)}>
                {d}
              </button>
            )
          })}
        </div>
      </>
    )
  }

  function renderMonths() {
    return (
      <div className="cal-months">
        {MONTH_LABELS.map((m, i) => (
          <button
            type="button"
            key={m}
            className={`cal-month ${i === viewMonth ? 'cal-month-selected' : ''}`}
            onClick={() => {
              setViewMonth(i)
              setViewMode('days')
            }}
          >
            {m.slice(0, 3)}
          </button>
        ))}
      </div>
    )
  }

  function renderYears() {
    const years = Array.from({ length: 12 }, (_, i) => yearsPageStart + i)
    return (
      <div className="cal-years">
        {years.map((y) => (
          <button
            type="button"
            key={y}
            className={`cal-year ${y === viewYear ? 'cal-year-selected' : ''}`}
            onClick={() => {
              setViewYear(y)
              setViewMode('months')
            }}
          >
            {y}
          </button>
        ))}
      </div>
    )
  }

  const calendarBody = (
    <>
      <div className="cal-header">
        <button type="button" className="cal-nav" onClick={goPrev} aria-label="Previous">
          ‹
        </button>
        {viewMode === 'years' ? (
          <span className="cal-header-label">
            {yearsPageStart} - {yearsPageStart + 11}
          </span>
        ) : (
          <span className="cal-header-label">
            <button type="button" className="cal-header-btn" onClick={() => setViewMode('months')}>
              {MONTH_LABELS[viewMonth]}
            </button>
            <button type="button" className="cal-header-btn" onClick={() => setViewMode('years')}>
              {viewYear}
            </button>
          </span>
        )}
        <button type="button" className="cal-nav" onClick={goNext} aria-label="Next">
          ›
        </button>
      </div>
      {viewMode === 'days' && renderDays()}
      {viewMode === 'months' && renderMonths()}
      {viewMode === 'years' && renderYears()}
      <div className="cal-range-summary">
        {start ? (end ? `${start} to ${end}` : `${start} - pick an end date`) : 'Pick a start date'}
      </div>
    </>
  )

  if (alwaysExpanded) {
    return <div className="date-range-calendar date-range-calendar-inline">{calendarBody}</div>
  }

  return (
    <div className="date-range-picker" ref={rootRef}>
      <button type="button" className="date-range-trigger" onClick={() => setExpanded((v) => !v)}>
        <span className="date-range-trigger-icon">📅</span>
        {formatTrigger(start, end)}
      </button>

      {expanded && <div className="date-range-calendar">{calendarBody}</div>}
    </div>
  )
}
