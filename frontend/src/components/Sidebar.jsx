import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import ChangePasswordModal from './ChangePasswordModal'
import NotificationBell from './NotificationBell'

export default function Sidebar({ onImportClick }) {
  const { username, myRoleNames, isAdmin, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [changePasswordOpen, setChangePasswordOpen] = useState(false)

  function handleImportClick() {
    // Import only makes sense in the file grid's context. If we're not on the
    // dashboard (no onImportClick handler passed in), navigate there first.
    if (onImportClick) onImportClick()
    else navigate('/dashboard')
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-brand-row">
        <div className="sidebar-brand">Project Management Tool</div>
        <NotificationBell />
      </div>
      <nav>
        <button
          className={`nav-item nav-item-button ${location.pathname === '/dashboard' ? 'active' : ''}`}
          onClick={() => navigate('/dashboard')}
        >
          Dashboard
        </button>
        <button
          className={`nav-item nav-item-button ${location.pathname === '/browse' ? 'active' : ''}`}
          onClick={() => navigate('/browse')}
        >
          Browse
        </button>
        {isAdmin && (
          <button className="nav-item nav-item-button" onClick={handleImportClick}>
            Import CSV
          </button>
        )}
        <button
          className={`nav-item nav-item-button ${location.pathname === '/reports' ? 'active' : ''}`}
          onClick={() => navigate('/reports')}
        >
          Reports
        </button>
        <button
          className={`nav-item nav-item-button ${location.pathname === '/calendar' ? 'active' : ''}`}
          onClick={() => navigate('/calendar')}
        >
          Calendar
        </button>
        {isAdmin && (
          <button
            className={`nav-item nav-item-button ${location.pathname === '/workboard' ? 'active' : ''}`}
            onClick={() => navigate('/workboard')}
          >
            Workboard
          </button>
        )}
        {isAdmin && (
          <button
            className={`nav-item nav-item-button ${location.pathname === '/audit-trail' ? 'active' : ''}`}
            onClick={() => navigate('/audit-trail')}
          >
            Audit Trail
          </button>
        )}
        {isAdmin && (
          <button
            className={`nav-item nav-item-button ${location.pathname === '/users' ? 'active' : ''}`}
            onClick={() => navigate('/users')}
          >
            User Management
          </button>
        )}
        {isAdmin && (
          <button
            className={`nav-item nav-item-button ${location.pathname === '/taxonomy' ? 'active' : ''}`}
            onClick={() => navigate('/taxonomy')}
          >
            Categories
          </button>
        )}
        {isAdmin && (
          <button
            className={`nav-item nav-item-button ${location.pathname === '/process-types' ? 'active' : ''}`}
            onClick={() => navigate('/process-types')}
          >
            Process Types
          </button>
        )}
      </nav>
      <div className="sidebar-footer">
        <div className="user-info">
          <div className="username">{username}</div>
          <div className="role-pill-group">
            {myRoleNames.map((r) => (
              <span key={r} className="role-badge">
                {r}
              </span>
            ))}
          </div>
        </div>
        <button className="logout-button" onClick={() => setChangePasswordOpen(true)}>
          Change Password
        </button>
        <button className="logout-button" onClick={logout}>
          Log out
        </button>
      </div>

      {changePasswordOpen && <ChangePasswordModal onClose={() => setChangePasswordOpen(false)} />}
    </aside>
  )
}
