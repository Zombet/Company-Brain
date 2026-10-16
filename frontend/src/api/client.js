import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 120000,
})

export const investigateQuery = (query, sessionId) =>
  api.post('/api/investigate', { query, session_id: sessionId })

export const getAccount = (id) => api.get(`/api/accounts/${id}`)
export const getNeighbors = (id) => api.get(`/api/accounts/${id}/neighbors`)
export const getHistory = (id) => api.get(`/api/accounts/${id}/history`)
export const getConnected = (txnId) => api.get(`/api/transactions/${txnId}/connected`)
export const flagAccount = (id, reason) => api.post('/api/accounts/flag', { account_id: id, reason })
export const getPath = (from, to) => api.get('/api/path', { params: { from_account: from, to_account: to } })
export const getOverview = () => api.get('/api/graph/overview')

export default api
