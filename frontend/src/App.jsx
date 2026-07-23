import { Navigate, Route, Routes } from 'react-router-dom'
import { Suspense, lazy } from 'react'
import { useAuth } from './context/AuthContext'

const LoginPage = lazy(() => import('./pages/LoginPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const BrowseFilesPage = lazy(() => import('./pages/BrowseFilesPage'))
const UsersPage = lazy(() => import('./pages/UsersPage'))
const TaxonomyPage = lazy(() => import('./pages/TaxonomyPage'))
const ProcessTypesPage = lazy(() => import('./pages/ProcessTypesPage'))
const AuditTrailPage = lazy(() => import('./pages/AuditTrailPage'))
const CalendarPage = lazy(() => import('./pages/CalendarPage'))
const ReportsPage = lazy(() => import('./pages/ReportsPage'))
const WorkboardPage = lazy(() => import('./pages/WorkboardPage'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))

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

function Loading() {
  return <div className="loading">Loading...</div>
}

export default function App() {
  return (
    <Suspense fallback={<Loading />}>
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
    </Suspense>
  )
}
