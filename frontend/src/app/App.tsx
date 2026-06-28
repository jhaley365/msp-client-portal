import { Navigate, Route, Routes } from 'react-router-dom'
import LoginPage from './LoginPage'
import DashboardPage from './DashboardPage'
import InstancesPage from './InstancesPage'
import VolumesPage from './VolumesPage'
import SnapshotsPage from './SnapshotsPage'
import Layout from '../components/Layout'
import { AuthProvider, useAuthContext } from './AuthContext'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuthContext()
  return user ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <PrivateRoute>
              <Layout />
            </PrivateRoute>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="instances" element={<InstancesPage />} />
          <Route path="volumes" element={<VolumesPage />} />
          <Route path="snapshots" element={<SnapshotsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}
