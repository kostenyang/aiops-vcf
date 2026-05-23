import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
})

export const alertsApi = {
  correlate: (alerts: unknown[]) => api.post('/api/alerts/correlate', { alerts }),
}
export const changesApi = {
  scoreRisk: (change: unknown) => api.post('/api/changes/risk', change),
}
export const reportsApi = {
  generate: (envData: unknown) => api.post('/api/reports/generate', envData),
}
export const troubleshootApi = {
  diagnose: (symptom: string, context: unknown) =>
    api.post('/api/troubleshoot/diagnose', { symptom, context }),
}
export const capacityApi = {
  plan: (metrics: unknown) => api.post('/api/capacity/plan', { metrics }),
}

export default api
