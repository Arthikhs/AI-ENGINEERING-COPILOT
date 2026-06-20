import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, AlertOctagon, Info, CheckCircle, RefreshCw, Shield } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { useAppStore } from '../store'
import api from '../services/api'

const SEVERITY_CONFIG = {
  critical: { icon: AlertOctagon, color: 'text-red-600', bg: 'bg-red-50 border-red-200', badge: 'destructive' as const },
  high: { icon: AlertTriangle, color: 'text-orange-500', bg: 'bg-orange-50 border-orange-200', badge: 'warning' as const },
  medium: { icon: AlertTriangle, color: 'text-yellow-500', bg: 'bg-yellow-50 border-yellow-200', badge: 'warning' as const },
  low: { icon: Info, color: 'text-blue-500', bg: 'bg-blue-50 border-blue-200', badge: 'info' as const },
}

export default function GovernancePage() {
  const { selectedRepo } = useAppStore()
  const [severityFilter, setSeverityFilter] = useState<string>('all')

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['governance', selectedRepo?.id],
    queryFn: () => api.get(`/enterprise/governance/${selectedRepo?.id}`).then(r => r.data),
    enabled: !!selectedRepo?.id,
  })

  const violations = (data?.violations || []).filter((v: any) =>
    severityFilter === 'all' || v.severity === severityFilter
  )

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Architecture Governance</h1>
          <p className="text-gray-500 text-sm mt-1">Detect violations, anti-patterns, and architectural risks</p>
        </div>
        <Button onClick={() => refetch()} loading={isLoading} className="gap-2">
          <RefreshCw size={14} /> Scan
        </Button>
      </div>

      {!selectedRepo && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 text-yellow-700 text-sm">
          Select a repository to run governance analysis.
        </div>
      )}

      {isLoading && <div className="text-center py-20 text-gray-400">Running governance analysis...</div>}

      {data && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            {(['critical', 'high', 'medium', 'low'] as const).map(sev => {
              const cfg = SEVERITY_CONFIG[sev]
              const Icon = cfg.icon
              const count = data.severity_counts?.[sev] || 0
              return (
                <button
                  key={sev}
                  onClick={() => setSeverityFilter(severityFilter === sev ? 'all' : sev)}
                  className={`border rounded-xl p-4 text-left transition-all ${cfg.bg} ${severityFilter === sev ? 'ring-2 ring-offset-1 ring-gray-400' : ''}`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Icon size={16} className={cfg.color} />
                    <span className="text-sm font-medium capitalize text-gray-700">{sev}</span>
                  </div>
                  <span className="text-2xl font-bold text-gray-900">{count}</span>
                </button>
              )
            })}
          </div>

          {/* Violations List */}
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
              <span className="font-semibold text-gray-700">
                Violations ({violations.length})
              </span>
              <span className="text-xs text-gray-400">{data.rules_applied} rules applied</span>
            </div>

            {violations.length === 0 ? (
              <div className="flex items-center gap-3 p-8 text-green-600">
                <CheckCircle size={20} />
                <span className="font-medium">No violations found for selected severity.</span>
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {violations.map((v: any, i: number) => {
                  const cfg = SEVERITY_CONFIG[v.severity as keyof typeof SEVERITY_CONFIG] || SEVERITY_CONFIG.low
                  const Icon = cfg.icon
                  return (
                    <div key={i} className="p-4 hover:bg-gray-50 transition-colors">
                      <div className="flex items-start gap-3">
                        <Icon size={16} className={`${cfg.color} mt-0.5 flex-shrink-0`} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium text-sm text-gray-800">{v.rule_name}</span>
                            <Badge variant={cfg.badge} className="text-[10px]">{v.severity}</Badge>
                            <Badge variant="info" className="text-[10px]">{v.rule_type}</Badge>
                          </div>
                          <p className="text-sm text-gray-600 mb-1">{v.description}</p>
                          {v.file_path && (
                            <p className="text-xs font-mono text-gray-400 truncate">{v.file_path}</p>
                          )}
                          {v.suggestion && (
                            <p className="text-xs text-green-600 mt-1">💡 {v.suggestion}</p>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
