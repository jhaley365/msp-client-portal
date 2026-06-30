import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`

  // Admins can view data as any customer via this header.
  const viewAs = localStorage.getItem('viewAsCustomerId')
  if (viewAs) config.headers['X-View-As-Customer'] = viewAs

  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      localStorage.removeItem('viewAsCustomerId')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api
