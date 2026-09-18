import { useEffect, useState } from 'react'
import api from '../lib/api'

interface User {
  customer_id: string
  name: string
  email: string
  is_admin: boolean
}

interface CustomerOption {
  customer_id: string
  name: string
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(() => {
    const stored = localStorage.getItem('user')
    return stored ? JSON.parse(stored) : null
  })

  const [viewAsCustomerId, setViewAsCustomerIdState] = useState<string>(() => {
    return localStorage.getItem('viewAsCustomerId') || ''
  })

  const [customers, setCustomers] = useState<CustomerOption[]>([])

  useEffect(() => {
    if (user?.is_admin) {
      api.get('/admin/customers').then((r) => setCustomers(r.data)).catch(() => {})
    }
  }, [user?.is_admin])

  const activeCustomerName =
    user?.is_admin && viewAsCustomerId
      ? customers.find((c) => c.customer_id === viewAsCustomerId)?.name || viewAsCustomerId
      : user?.name || user?.email || ''

  const setViewAsCustomerId = (id: string) => {
    if (id) {
      localStorage.setItem('viewAsCustomerId', id)
    } else {
      localStorage.removeItem('viewAsCustomerId')
    }
    setViewAsCustomerIdState(id)
  }

  const login = async (email: string, password: string): Promise<void> => {
    const { data } = await api.post('/auth/login', { email, password })
    localStorage.setItem('token', data.access_token)
    const u: User = {
      customer_id: data.customer_id,
      name: data.name,
      email,
      is_admin: data.is_admin ?? false,
    }
    localStorage.setItem('user', JSON.stringify(u))
    setUser(u)
  }

  const logout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    localStorage.removeItem('viewAsCustomerId')
    setUser(null)
    setViewAsCustomerIdState('')
  }

  return { user, login, logout, viewAsCustomerId, setViewAsCustomerId, customers, activeCustomerName }
}
