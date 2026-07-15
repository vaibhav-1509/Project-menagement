import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import * as api from '../api/client'

// Not a browser/OS push notification - just an in-app "here's what's new"
// feed, refreshed by polling rather than a live socket connection (matches
// the rest of this app's plain-REST design, no push infrastructure exists).
const POLL_INTERVAL_MS = 30000

export default function NotificationBell() {
  const { isAdmin } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [lowWorkload, setLowWorkload] = useState([])
  const [staleCount, setStaleCount] = useState(0)
  const containerRef = useRef(null)

  async function load() {
    try {
      const data = await api.getNotifications(30)
      setItems(data.items)
      setUnreadCount(data.unreadCount)
    } catch {
      // Silent by design - a failed background poll shouldn't surface an
      // error banner on every page in the app.
    }
    if (isAdmin) {
      try {
        const board = await api.getAdminWorkboard()
        setLowWorkload(board.lowWorkloadWorkers)
        setStaleCount(board.staleAssignments.length)
      } catch {
        // ignore
      }
    }
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin])

  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  async function handleItemClick(notif) {
    if (!notif.isRead) {
      try {
        await api.markNotificationRead(notif.id)
        setItems((prev) => prev.map((n) => (n.id === notif.id ? { ...n, isRead: true } : n)))
        setUnreadCount((c) => Math.max(0, c - 1))
      } catch {
        // ignore - worst case it just stays unread until the next poll
      }
    }
    setOpen(false)
    // SubmittedForApproval is an admin decision waiting on the Workboard;
    // everything else (FileAssigned) is "go look at your queue".
    navigate(notif.type === 'SubmittedForApproval' ? '/workboard' : '/dashboard')
  }

  async function handleMarkAllRead() {
    try {
      await api.markAllNotificationsRead()
      setItems((prev) => prev.map((n) => ({ ...n, isRead: true })))
      setUnreadCount(0)
    } catch {
      // ignore
    }
  }

  return (
    <div className="notification-bell" ref={containerRef}>
      <button className="notification-bell-toggle" onClick={() => setOpen((o) => !o)} title="Notifications">
        <span aria-hidden="true">🔔</span>
        {unreadCount > 0 && <span className="notification-badge">{unreadCount > 99 ? '99+' : unreadCount}</span>}
      </button>
      {open && (
        <div className="notification-dropdown">
          <div className="notification-dropdown-header">
            <strong>Notifications</strong>
            {unreadCount > 0 && (
              <button type="button" className="link-button" onClick={handleMarkAllRead}>
                Mark all read
              </button>
            )}
          </div>
          <div className="notification-list">
            {items.length === 0 && <p className="hint">Nothing yet.</p>}
            {items.map((n) => (
              <div
                key={n.id}
                className={`notification-item ${n.isRead ? '' : 'notification-item-unread'}`}
                onClick={() => handleItemClick(n)}
              >
                <div>{n.message}</div>
                <span className="hint">{new Date(n.createdAt).toLocaleString()}</span>
              </div>
            ))}
          </div>
          {isAdmin && lowWorkload.length > 0 && (
            <div className="notification-reminders">
              <strong>Workers running low on files</strong>
              {lowWorkload.map((w) => (
                <div
                  key={w.userId}
                  className="notification-item"
                  onClick={() => {
                    setOpen(false)
                    navigate('/workboard')
                  }}
                >
                  {w.username} - {w.pendingCount} pending
                </div>
              ))}
            </div>
          )}
          {isAdmin && staleCount > 0 && (
            <div className="notification-reminders">
              <div
                className="notification-item"
                onClick={() => {
                  setOpen(false)
                  navigate('/workboard')
                }}
              >
                {staleCount} assignment{staleCount === 1 ? ' has' : 's have'} been sitting stale too long
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
