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

// New graph query endpoints
export const getEntity = (id) => api.get(`/api/entity/${id}`)
export const getNeighborhood = (id, depth = 2, relTypes = '') =>
  api.get(`/api/neighborhood/${id}`, { params: { depth, rel_types: relTypes } })
export const getPaths = (fromId, toId, maxHops = 6) =>
  api.get('/api/paths', { params: { from_id: fromId, to_id: toId, max_hops: maxHops } })
export const getShared = (a, b) =>
  api.get('/api/shared', { params: { a, b } })
export const getCommunity = (seedId) =>
  api.get(`/api/community/${seedId}`)

// Action endpoints
export const freezeAccount = (accountId, reason, evidenceIds, dryRun = true) =>
  api.post('/api/actions/freeze', { account_id: accountId, reason, evidence_ids: evidenceIds, dry_run: dryRun })
export const openCase = (alertIds, reason, evidenceIds) =>
  api.post('/api/actions/open_case', { alert_ids: alertIds, reason, evidence_ids: evidenceIds })
export const escalateCase = (caseId, reason, evidenceIds) =>
  api.post('/api/actions/escalate', { case_id: caseId, reason, evidence_ids: evidenceIds })

export default api
