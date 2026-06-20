import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  AlertTriangle, AlertOctagon, Info, CheckCircle,
  RefreshCw, Shield, Sparkles, ChevronDown, ChevronUp,
  BarChart3, FileCode, Layers
} from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { useAppStore } from '../store'
import api from '../services/api'

const SEVERITY_CONFIG = {
  critical: { icon: AlertOctagon, color: 'text-red-600',    bg: 'bg-red-50 border-red-200',       bar: 'bg-red-500' },
  high:     { icon: AlertTriangle, color: 'text-orange-500', bg: 'bg-orange-50 border-orange-200', bar: 'bg-orange-500' },
  medium:   { icon: AlertTriangle, color: 'text-yellow-500', bg: 'bg-yellow-50 border-yellow-200', bar: 'bg-yellow-500' },
  low:      { icon: Info,          color: 'text-blue-500',   bg: 'bg-blue-50 border-blue-200',     bar: 'bg-blue-400' },
}

const RULE_TYPE_LABELS: Record<string, string> = {
  layer_violation:      '🏗️ Layer Violation',
  god_class:            '👾 God Class',
  circular_dependency:  '🔄 Circular Dependency',
  security_antipattern: '🔒 Security',
  antipattern:          '⚠️ Anti-Pattern',
  code_quality:         '📏 Code Quality',
  tight_coupling:       '🔗 Tight Coupling',
}

function ScoreGauge({ score }: { score: number }) {
  const color = score >= 80 ? 'text-green-600' : score >= 60 ? 'text-yellow-600' : 'text-red-600'
  const bg    = score >= 80 ? 'bg-green-50 border-green-200' : score >= 60 ? 'bg-yellow-50 border-yellow-200' : 'bg-red-50 border-red-200'
  const grade = score >= 90 ? 'A' : score >= 80 ? 'B' : score >= 70 ? 'C' : score >= 60 ? 'D' : 'F'
  return (
    <div className={`border rounded-2xl p-6 flex items-center gap-6 ${bg}`}>
      <div className="text-center">
        <div className={`text-6xl font-black ${color}`}>{score}</div>
        <div className="text-sm text-gray-500 mt-1">/ 100</div>
      </div>
      <div>
        <div className={`text-3xl font-bold px-4 py-2 rounded-xl ${bg} ${color} border`}>{grade}</div>
      </div>
      <div className="flex-1">
        <p className="font-semibold text-gray-800 text-lg">Governance Score</p>
        <p className="text-sm text-gray-500 mt-1">
          {score >= 80 ? '✅ Architecture is well-governed.' :
           score >= 60 ? '⚠️ Some architectural issues need attention.' :
           '🔴 Significant governance violations detected.'}
        </p>
      </div>
    </div>
  )
}

function ViolationCard({ v }: { v: any }) {
  const [expanded, setExpanded]  = useState(false)
  const [aiSuggestion, setAiSuggestion] = useState('')

  const fixMutation = useMutation({
    mutationFn: () => api.post(`/governance/${v.repo_id || 'x'}/fix-suggest`, { violation: v }).then(r => r.data),
    onSuccess: (data) => setAiSuggestion(data.suggestion),
  })

  const cfg   = SEVERITY_CONFIG[v.severity as keyof typeof SEVERITY_CONFIG] || SEVERITY_CONFIG.low
  const Icon  = cfg.icon

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden hover:border-gray-300 transition-colors">
      <button
        className="w-full flex items-start gap-3 p-4 text-left hover:bg-gray-50 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <Icon size={16} className={`${cfg.color} mt-0.5 flex-shrink-0`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="font-medium text-sm text-gray-800">{v.rule_name}</span>
            <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${cfg.bg} ${cfg.color}`}>
              {v.severity}
            </span>
            <span className="text-[10px] text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
              {RULE_TYPE_LABELS[v.rule_type] || v.rule_type}
            </span>
          </div>
          <p className="text-sm text-gray-600">{v.description}</p>
          {v.file_path && (
            <p className="text-xs font-mono text-gray-400 mt-1 truncate">
              <FileCode size={10} className="inline mr-1" />{v.file_path}
            </p>
          )}
        </div>
        {expanded ? <ChevronUp size={14} className="text-gray-400 flex-shrink-0 mt-1" /> : <ChevronDown size={14} className="text-gray-400 flex-shrink-0 mt-1" />}
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-gray-100 bg-gray-50">
          <div className="pt-3 space-y-3">
            {v.suggestion && (
              <div className="flex items-start gap-2 text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg p-3">
                <span className="text-green-500 mt-0.5">💡</span>
                <span>{v.suggestion}</span>
              </div>
            )}
            {aiSuggestion && (
              <div className="flex items-start gap-2 text-sm text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-lg p-3">
                <Sparkles size={14} className="text-indigo-500 mt-0.5 flex-shrink-0" />
                <span>{aiSuggestion}</span>
              </div>
            )}
            <Button
              onClick={() => fixMutation.mutate()}
              loading={fixMutation.isPending}
              className="text-xs gap-1 py-1.5 px-3"
            >
              <Sparkles size={11} /> Get AI Fix
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function GovernancePage() {
  const { selectedRepo }              = useAppStore()
  const [severityFilter, setSeverityFilter] = useState('all')
  const [typeFilter, setTypeFilter]   = useState('all')
  const [tab, setTab]                 = useState<'violations' | 'rules'>('violations')

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['governance', selectedRepo?.id],
    queryFn:  () => api.get(`/governance/${selectedRepo?.id}`).then(r => r.data),
    enabled:  !!selectedRepo?.id,
  })

  const { data: rulesData } = useQuery({
    queryKey: ['governance-rules'],
    queryFn:  () => api.get('/governance/rules').then(r => r.data),
  })

  const violations = (data?.violations || []).filter((v: any) =>
    (severityFilter === 'all' || v.severity === severityFilter) &&
    (typeFilter === 'all' || v.rule_type === typeFilter)
  )

  const ruleTypes = [...new Set((data?.violations || []).map((v: any) => v.rule_type))] as string[]

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-orange-100 rounded-xl">
            <Shield size={20} className="text-orange-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Architecture Governance</h1>
            <p className="text-gray-500 text-sm mt-0.5">
              {data ? `${data.files_scanned} files scanned · ${data.rules_applied} rules applied` : 'Detect violations, anti-patterns and architectural risks'}
            </p>
          </div>
        </div>
        <Button onClick={() => refetch()} loading={isLoading} className="gap-2">
          <RefreshCw size={14} /> Scan
        </Button>
      </div>

      {!selectedRepo && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 text-yellow-700 text-sm">
          Select a repository from the sidebar to run governance analysis.
        </div>
      )}

      {isLoading && (
        <div className="text-center py-20 text-gray-400">
          <Shield size={32} className="mx-auto mb-3 animate-pulse" />
          Running governance analysis...
        </div>
      )}

      {data && (
        <>
          {/* Governance Score */}
          <div className="mb-6">
            <ScoreGauge score={data.governance_score} />
          </div>

          {/* Severity Summary */}
          <div className="grid grid-cols-4 gap-3 mb-6">
            {(['critical', 'high', 'medium', 'low'] as const).map(sev => {
              const cfg   = SEVERITY_CONFIG[sev]
              const Icon  = cfg.icon
              const count = data.severity_counts?.[sev] || 0
              return (
                <button
                  key={sev}
                  onClick={() => setSeverityFilter(severityFilter === sev ? 'all' : sev)}
                  className={`border rounded-xl p-4 text-left transition-all ${cfg.bg} ${
                    severityFilter === sev ? 'ring-2 ring-offset-1 ring-gray-500' : ''
                  }`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Icon size={14} className={cfg.color} />
                    <span className="text-xs font-semibold uppercase tracking-wide text-gray-600">{sev}</span>
                  </div>
                  <span className="text-3xl font-black text-gray-900">{count}</span>
                </button>
              )
            })}
          </div>

          {/* Tabs */}
          <div className="flex gap-1 mb-4 bg-gray-100 rounded-xl p-1 w-fit">
            {(['violations', 'rules'] as const).map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  tab === t ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {t === 'violations'
                  ? <><BarChart3 size={13} className="inline mr-1.5" />Violations ({data.total_violations})</>
                  : <><Layers size={13} className="inline mr-1.5" />Rules ({rulesData?.total || 0})</>
                }
              </button>
            ))}
          </div>

          {tab === 'violations' && (
            <>
              {/* Type filter */}
              {ruleTypes.length > 0 && (
                <div className="flex gap-2 mb-4 flex-wrap">
                  <button
                    onClick={() => setTypeFilter('all')}
                    className={`px-3 py-1 rounded-lg text-xs border transition-all ${
                      typeFilter === 'all' ? 'bg-gray-900 text-white border-gray-900' : 'bg-white text-gray-500 border-gray-200'
                    }`}
                  >
                    All types
                  </button>
                  {ruleTypes.map(rt => (
                    <button
                      key={rt}
                      onClick={() => setTypeFilter(typeFilter === rt ? 'all' : rt)}
                      className={`px-3 py-1 rounded-lg text-xs border transition-all ${
                        typeFilter === rt ? 'bg-gray-900 text-white border-gray-900' : 'bg-white text-gray-500 border-gray-200'
                      }`}
                    >
                      {RULE_TYPE_LABELS[rt] || rt} ({data.by_type?.[rt] || 0})
                    </button>
                  ))}
                </div>
              )}

              {/* Violations List */}
              {violations.length === 0 ? (
                <div className="flex items-center gap-3 p-10 text-green-600 bg-green-50 border border-green-200 rounded-xl">
                  <CheckCircle size={20} />
                  <span className="font-medium">No violations found for selected filters. 🎉</span>
                </div>
              ) : (
                <div className="space-y-2">
                  {violations.map((v: any, i: number) => (
                    <ViolationCard key={v.id || i} v={v} />
                  ))}
                </div>
              )}
            </>
          )}

          {tab === 'rules' && rulesData && (
            <div className="space-y-2">
              {rulesData.rules.map((rule: any) => {
                const cfg  = SEVERITY_CONFIG[rule.severity as keyof typeof SEVERITY_CONFIG] || SEVERITY_CONFIG.low
                const Icon = cfg.icon
                return (
                  <div key={rule.id} className="bg-white border border-gray-200 rounded-xl p-4">
                    <div className="flex items-start gap-3">
                      <Icon size={15} className={`${cfg.color} mt-0.5`} />
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-mono text-xs text-gray-400">{rule.id}</span>
                          <span className="font-medium text-sm text-gray-800">{rule.name}</span>
                          <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${cfg.bg} ${cfg.color}`}>
                            {rule.severity}
                          </span>
                        </div>
                        <p className="text-sm text-gray-600">{rule.description}</p>
                        <p className="text-xs text-green-600 mt-1">💡 {rule.suggestion}</p>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}
    </div>
  )
}
