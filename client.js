import axios from 'axios'

const client = axios.create({ baseURL: '/api/v1' })

// Attach the access token to every request automatically.
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// On a 401, the token is invalid/expired -- clear it and send the user back to login rather
// than showing a confusing error inside whatever screen they were on.
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default client
