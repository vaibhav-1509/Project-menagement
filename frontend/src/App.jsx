import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import BrowseFilesPage from './pages/BrowseFilesPage'
import UsersPage from './pages/UsersPage'
import TaxonomyPage from './pages/TaxonomyPage'
import ProcessTypesPage from './pages/ProcessTypesPage'
import AuditTrailPage from './pages/AuditTrailPage'
import CalendarPage from './pages/CalendarPage'
import ReportsPage from './pages/ReportsPage'
import WorkboardPage from './pages/WorkboardPage'
import ProfilePage from './pages/ProfilePage'

function ProtectedRoute({ children }) {
  const { token } = useAuth()
  if (!token) return <Navigate to="/login" replace />
  return children
}

function AdminRoute({ children }) {
  const { isAdmin, rolesLoaded } = useAuth()
  if (!rolesLoaded) return null
  if (!isAdmin) return <Navigate to="/dashboard" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/browse"
        element={
          <ProtectedRoute>
            <BrowseFilesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/users"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <UsersPage />
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/taxonomy"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <TaxonomyPage />
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/process-types"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <ProcessTypesPage />
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/reports"
        element={
          <ProtectedRoute>
            <ReportsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/calendar"
        element={
          <ProtectedRoute>
            <CalendarPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/audit-trail"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <AuditTrailPage />
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/workboard"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <WorkboardPage />
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/profile"
        element={
          <ProtectedRoute>
            <ProfilePage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
