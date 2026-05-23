import { useState } from 'react'
import { reportsApi } from '../services/api'

const PLACEHOLDER = JSON.stringify({
  customer: 'ACME Corp',
  period: '2026-05',
  vcf_version: '5.2.1',
  cluster_count: 3,
  host_count: 12,
  vm_count: 340,
  alerts_this_month: 47,
  critical_alerts: 2,
  cpu_utilization_avg: 68,
  memory_utilization_avg: 72,
  vsan_capacity_used_pct: 61,
}, null, 2)

export default function Reports() {
  const [input, setInput]   = useState(PLACEHOLDER)
  const [loading, setLoading] = useState(false)
  const [error, setError]   = useState<string | null>(null)
  const [report, setReport] = useState<string | null>(null)

  async function handleSubmit() {
    setError(null)
    setLoading(true)
    try {
      const envData = JSON.parse(input)
      const { data } = await reportsApi.generate(envData)
      setReport(data.report)
    } catch (e: any) {
      setError(e.response?.data?.detail ?? e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-8 max-w-4xl">
      <h1 className="text-2xl font-semibold text-white mb-1">Health Report</h1>
      <p className="text-gray-400 mb-6">輸入環境資料，AI 自動生成繁體中文月度健康報告。</p>

      <div className="mb-4">
        <label className="block text-xs text-gray-500 uppercase tracking-wide mb-1">Environment Data (JSON)</label>
        <textarea
          className="w-full h-52 bg-gray-900 border border-gray-700 rounded-lg p-3 text-sm text-gray-200 font-mono focus:outline-none focus:border-blue-500 resize-none"
          value={input}
          onChange={e => setInput(e.target.value)}
        />
      </div>

      <button
        onClick={handleSubmit}
        disabled={loading}
        className="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
      >
        {loading ? 'Generating Report…' : 'Generate Health Report'}
      </button>

      {error && (
        <div className="mt-4 p-3 bg-red-900/40 border border-red-700 rounded-lg text-red-300 text-sm">{error}</div>
      )}

      {report && (
        <div className="mt-6 bg-gray-900 border border-gray-700 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <p className="text-xs text-gray-500 uppercase tracking-wide">Generated Report</p>
            <button
              onClick={() => navigator.clipboard.writeText(report)}
              className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              Copy
            </button>
          </div>
          <pre className="text-gray-200 text-sm whitespace-pre-wrap font-sans leading-relaxed">{report}</pre>
        </div>
      )}
    </div>
  )
}
