import { useState } from 'react'
import { alertsApi } from '../services/api'

interface Incident {
  id: string
  title: string
  severity: string
  alert_ids: string[]
  root_cause_hypothesis: string
  next_steps: string[]
}

const SEVERITY_COLOR: Record<string, string> = {
  critical: 'bg-red-500',
  high:     'bg-orange-500',
  medium:   'bg-yellow-500',
  low:      'bg-blue-500',
}

const PLACEHOLDER = JSON.stringify([
  { id: 'ALT-001', name: 'vSAN disk degraded', severity: 'critical', host: 'esxi-01', time: '2026-05-23T10:00:00Z' },
  { id: 'ALT-002', name: 'CPU usage > 90%',    severity: 'high',     host: 'esxi-01', time: '2026-05-23T10:01:00Z' },
  { id: 'ALT-003', name: 'NFS datastore latency high', severity: 'medium', host: 'esxi-02', time: '2026-05-23T10:02:00Z' },
], null, 2)

export default function Alerts() {
  const [input, setInput]       = useState(PLACEHOLDER)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState<string | null>(null)
  const [incidents, setIncidents] = useState<Incident[] | null>(null)

  async function handleSubmit() {
    setError(null)
    setLoading(true)
    try {
      const alerts = JSON.parse(input)
      const { data } = await alertsApi.correlate(alerts)
      setIncidents(data.incidents)
    } catch (e: any) {
      setError(e.response?.data?.detail ?? e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-8 max-w-4xl">
      <h1 className="text-2xl font-semibold text-white mb-1">Alert Correlation</h1>
      <p className="text-gray-400 mb-6">貼上告警 JSON，AI 自動分群並推測根因。</p>

      <div className="mb-4">
        <label className="block text-xs text-gray-500 uppercase tracking-wide mb-1">Alerts (JSON array)</label>
        <textarea
          className="w-full h-44 bg-gray-900 border border-gray-700 rounded-lg p-3 text-sm text-gray-200 font-mono focus:outline-none focus:border-blue-500 resize-none"
          value={input}
          onChange={e => setInput(e.target.value)}
        />
      </div>

      <button
        onClick={handleSubmit}
        disabled={loading}
        className="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
      >
        {loading ? 'Analyzing…' : 'Correlate Alerts'}
      </button>

      {error && (
        <div className="mt-4 p-3 bg-red-900/40 border border-red-700 rounded-lg text-red-300 text-sm">{error}</div>
      )}

      {incidents && (
        <div className="mt-6 space-y-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">{incidents.length} Incident{incidents.length !== 1 ? 's' : ''} identified</p>
          {incidents.map(inc => (
            <div key={inc.id} className="bg-gray-900 border border-gray-700 rounded-xl p-5">
              <div className="flex items-center gap-3 mb-3">
                <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase text-white ${SEVERITY_COLOR[inc.severity] ?? 'bg-gray-600'}`}>
                  {inc.severity}
                </span>
                <span className="text-white font-medium">{inc.title}</span>
                <span className="ml-auto text-gray-600 text-xs font-mono">{inc.id}</span>
              </div>
              <p className="text-gray-300 text-sm mb-3">
                <span className="text-gray-500">Root Cause: </span>{inc.root_cause_hypothesis}
              </p>
              {inc.alert_ids?.length > 0 && (
                <p className="text-gray-500 text-xs mb-3">
                  Related alerts: {inc.alert_ids.join(', ')}
                </p>
              )}
              {inc.next_steps?.length > 0 && (
                <div>
                  <p className="text-gray-500 text-xs uppercase tracking-wide mb-2">Next Steps</p>
                  <ol className="space-y-1">
                    {inc.next_steps.map((step, i) => (
                      <li key={i} className="text-gray-300 text-sm flex gap-2">
                        <span className="text-blue-400 font-mono">{i + 1}.</span>{step}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
