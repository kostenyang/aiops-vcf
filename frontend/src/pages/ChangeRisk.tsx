import { useState, FormEvent } from 'react'
import { changesApi } from '../services/api'

interface RiskResult {
  risk_score: number
  risk_level: string
  go_no_go: string
  blockers: string[]
  checklist: string[]
  recommendation: string
}

const RISK_COLOR: Record<string, string> = {
  low:      'text-green-400',
  medium:   'text-yellow-400',
  high:     'text-orange-400',
  critical: 'text-red-400',
}
const GONOGO_COLOR: Record<string, string> = {
  'go':          'bg-green-600',
  'no-go':       'bg-red-600',
  'conditional': 'bg-yellow-600',
}

const FIELD = 'w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500'

export default function ChangeRisk() {
  const [form, setForm] = useState({
    title: '', type: 'upgrade', target: '',
    vcf_version: '', maintenance_window: '', rollback_plan: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState<string | null>(null)
  const [result, setResult]   = useState<RiskResult | null>(null)

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }))

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const { data } = await changesApi.scoreRisk(form)
      setResult(data)
    } catch (e: any) {
      setError(e.response?.data?.detail ?? e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-8 max-w-3xl">
      <h1 className="text-2xl font-semibold text-white mb-1">Change Risk Assessment</h1>
      <p className="text-gray-400 mb-6">評估 VCF 升級或變更的風險，取得 GO / NO-GO 建議。</p>

      <form onSubmit={handleSubmit} className="bg-gray-900 border border-gray-700 rounded-xl p-5 mb-6 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Change Title *</label>
            <input className={FIELD} value={form.title} onChange={set('title')}
              placeholder="Upgrade VCF to 5.3" required />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Change Type</label>
            <select className={FIELD} value={form.type} onChange={set('type')}>
              <option value="upgrade">Upgrade</option>
              <option value="patch">Patch</option>
              <option value="config">Config Change</option>
              <option value="migration">Migration</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Target *</label>
            <input className={FIELD} value={form.target} onChange={set('target')}
              placeholder="VCF 5.2 → 5.3" required />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Current VCF Version</label>
            <input className={FIELD} value={form.vcf_version} onChange={set('vcf_version')}
              placeholder="5.2.1" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Maintenance Window</label>
            <input className={FIELD} value={form.maintenance_window} onChange={set('maintenance_window')}
              placeholder="2026-05-25 02:00–04:00 UTC" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Rollback Plan</label>
            <input className={FIELD} value={form.rollback_plan} onChange={set('rollback_plan')}
              placeholder="Snapshot + restore previous bundle" />
          </div>
        </div>
        <button type="submit" disabled={loading}
          className="w-full py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors">
          {loading ? 'Assessing Risk…' : 'Assess Change Risk'}
        </button>
      </form>

      {error && (
        <div className="p-3 bg-red-900/40 border border-red-700 rounded-lg text-red-300 text-sm">{error}</div>
      )}

      {result && (
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 space-y-5">
          <div className="flex items-center gap-8">
            <div>
              <p className="text-xs text-gray-500 mb-1">Risk Score</p>
              <p className={`text-5xl font-bold ${RISK_COLOR[result.risk_level] ?? 'text-gray-400'}`}>
                {result.risk_score}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Risk Level</p>
              <p className={`text-xl font-semibold capitalize ${RISK_COLOR[result.risk_level] ?? 'text-gray-400'}`}>
                {result.risk_level}
              </p>
            </div>
            <div className="ml-auto">
              <span className={`px-5 py-2 rounded-full text-white font-bold uppercase text-sm ${GONOGO_COLOR[result.go_no_go] ?? 'bg-gray-600'}`}>
                {result.go_no_go}
              </span>
            </div>
          </div>

          {result.blockers?.length > 0 && (
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Blockers</p>
              <ul className="space-y-1">
                {result.blockers.map((b, i) => (
                  <li key={i} className="text-red-400 text-sm flex gap-2"><span>⚠</span>{b}</li>
                ))}
              </ul>
            </div>
          )}

          {result.checklist?.length > 0 && (
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Pre-Change Checklist</p>
              <ul className="space-y-1">
                {result.checklist.map((item, i) => (
                  <li key={i} className="text-gray-300 text-sm flex gap-2">
                    <span className="text-green-400">☐</span>{item}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Recommendation</p>
            <p className="text-gray-200 text-sm leading-relaxed">{result.recommendation}</p>
          </div>
        </div>
      )}
    </div>
  )
}
