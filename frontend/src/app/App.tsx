import { Navigate, Route, Routes } from 'react-router-dom'
import LoginPage from './LoginPage'
import MagicLinkVerifyPage from './MagicLinkVerifyPage'
import DashboardPage from './DashboardPage'
import AwsPage from './AwsPage'
import TicketsPage from './TicketsPage'
import SecurityPage from './SecurityPage'
import DnsPage from './DnsPage'
import O365Page from './O365Page'
import AppsPage from './AppsPage'
import MonitoringPage from './MonitoringPage'
import AdminUsersPage from './AdminUsersPage'
import AdminAuditPage from './AdminAuditPage'
import Layout from '../components/Layout'
import { AuthProvider, useAuthContext } from './AuthContext'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuthContext()
  return user ? <>{children}</> : <Navigate to="/login" replace />
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuthContext()
  if (!user) return <Navigate to="/login" replace />
  if (!user.is_admin) return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/auth/verify" element={<MagicLinkVerifyPage />} />
        <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
          <Route index element={<DashboardPage />} />
          <Route path="aws" element={<AwsPage />} />
          <Route path="tickets" element={<TicketsPage />} />
          <Route path="security" element={<SecurityPage />} />
          <Route path="dns" element={<DnsPage />} />
          <Route path="o365" element={<O365Page />} />
          <Route path="apps" element={<AppsPage />} />
          <Route path="monitoring" element={<MonitoringPage />} />
          <Route path="admin/users" element={<AdminRoute><AdminUsersPage /></AdminRoute>} />
          <Route path="admin/audit" element={<AdminRoute><AdminAuditPage /></AdminRoute>} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}
