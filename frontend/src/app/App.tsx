import { Navigate, Route, Routes } from 'react-router-dom'
import LoginPage from './LoginPage'
import DashboardPage from './DashboardPage'
import AwsPage from './AwsPage'
import TicketsPage from './TicketsPage'
import SecurityPage from './SecurityPage'
import DnsPage from './DnsPage'
import O365Page from './O365Page'
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
        <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
          <Route index element={<DashboardPage />} />
          <Route path="aws" element={<AwsPage />} />
          <Route path="tickets" element={<TicketsPage />} />
          <Route path="security" element={<SecurityPage />} />
          <Route path="dns" element={<DnsPage />} />
          <Route path="o365" element={<O365Page />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}
