import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Shield, GitBranch, TestTube, Code2, Package,
  BookOpen, RefreshCw, TrendingUp, TrendingDown,
  Minus, Heart, Lightbulb, History
} from 'lucide-react'
import { Button } from '../components/ui/Button'
import { useAppStore } from '../store'
import api from '../services/api'

const DIMENSION_CONFIG: Record<string, { icon: any; color: string; bg: string }> = {
  security:         { icon: Shield,    color: 'text-red-500',    bg: 'bg-red-50' },
  architecture:     { icon: GitBranch, color: 'text-blue-500',   bg: 'bg-blue-50' },
  test_coverage:    { icon: TestTube,  color: 'text-green-500',  bg: 'bg-green-50' },
  code_quality:     { icon: Code2,     color: 'text-purple-500', bg: 'bg-purple-50' },
  dependency:       { icon: Package,   color: 'text-orange-500', bg: 'bg-orange-50' },
  documentation:    { icon: BookOpen,  color: 'text-yellow-500', bg: 'bg-yellow-50' },
}

function ScoreRing({ score, size = 140 }: { score: number; size?: number }) {
  const radius       = size / 2 - 12
  const circumference = 2 * Math.PI * radius
  const offset       = circumference - (score / 100) * circumference
  const color        = score >= 80 ? '#22c55e' : score >= 60 ? '#f59e0b' : '#ef4444'

  return (
    <svg width={size} height={size} className="rotate-[-90deg]">
      <circle cx={size/2} cy={size/2} r={radius} stroke="#e5e7eb" strokeWidth="10" fill="none" />
      <circle
        cx={size/2} cy={size/2} r={radius}
        stroke={color} strokeWidth="10" fill="none"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        style={{ transition: 'stroke-dashoffset 1s ease' }}
      />
      <text
        x={size/2} y={size/2 + 7}
        textAnchor="middle" fill={color}
        fontSize="22" fontWeight="bold"
        transform={`rotate(90, ${size/2}, ${size/2})`}
      >
        {Math.round(score)}
      </text>
    </svg>
  )
}

function ScoreBar({ score, previous }: { score: number; previous?: number }) {
  const color = score >= 80 ? 'bg-green-500' : score >= 60 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="relative">
      <div className="w-full bg-gray-100 rounded-full h-2.5 mt-2">
        <div
          className={`h-2.5 rounded-full ${color} transition-all duration-700`}
          style={{ width: `${score}%` }}
        />
      </div>
      {previous !== undefined && (
        <div
          className="absolute top-2 w-0.5 h-2.5 bg-gray-400 opacity-50"
          style={{ left: `${previous}%` }}
          title={`Previous: ${previous}`}
        />
      )}
    </div>
  )
}

function DeltaBadge({ delta }: { delta: number | null }) {
  if (delta === null) return null
  if (delta === 0) return (
    <span className="flex items-center gap-0.5 text-xs text-gray-400">
      <Minus size={10} /> 0
    </span>
  )
  return (
    <span className={`flex items-center gap-0.5 text-xs font-medium ${delta > 0 ? 'text-green-600' : 'text-red-500'}`}>
      {delta > 0 ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
      {delta > 0 ? '+' : ''}{delta}
    </span>
  )
}

function MiniTrendBar({ history, field }: { history: any[]; field: string }) {
  if (!history?.length) return null
  const values = history.slice(0, 7).reverse().map(h => parseFloat(h[field] || 0))
  const max = Math.max(...values, 1)

  return (
    <div className="flex items-end gap-0.5 h-6 mt-1">
      {values.map((v, i) => (
        <div
          key={i}
          className={`flex-1 rounded-sm ${v >= 80 ? 'bg-green-400' : v >= 60 ? 'bg-yellow-400' : 'bg-red-400'}`}
          style={{ height: `${(v / max) * 100}%`, minHeight: 2 }}
          title={`${Math.round(v)}`}
        />
      ))}
    </div>
  )
}

export default function HealthScorePage() {
  const { selectedRepo }          = useAppStore()
  const [tab, setTab]             = useState<'overview' | 'history'>('overview')

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['health-score', selectedRepo?.id],
    queryFn:  () => api.get(`/health-score/${selectedRepo?.id}`).then(r => r.data),
    enabled:  !!selectedRepo?.id,
  })

  const { data: historyData } = useQuery({
    queryKey: ['health-score-history', selectedRepo?.id],
    queryFn:  () => api.get(`/health-score/${selectedRepo?.id}/history?limit=10`).then(r => r.data),
    enabled:  !!selectedRepo?.id,
  })

  const history = historyData?.history || []

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-pink-100 rounded-xl">
            <Heart size={20} className="text-pink-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Repository Health Score</h1>
            <p className="text-gray-500 text-sm mt-0.5">6-dimension quality assessment with trend tracking</p>
          </div>
        </div>
        <Button onClick={() => refetch()} loading={isLoading} className="gap-2">
          <RefreshCw size={14} /> Compute
        </Button>
      </div>

      {!selectedRepo && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 text-yellow-700 text-sm">
          Select an indexed repository from the sidebar to compute its health score.
        </div>
      )}

      {isLoading && (
        <div className="text-center py-20 text-gray-400">
          <Heart size={32} className="mx-auto mb-3 animate-pulse text-pink-400" />
          Computing health score across 6 dimensions...
        </div>
      )}

      {data && (
        <>
          {/* Overall Score Card */}
          <div className="bg-white border border-gray-200 rounded-2xl p-8 mb-6">
            <div className="flex items-center gap-8">
              <ScoreRing score={data.overall_score} size={150} />
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-5xl font-black text-gray-900">{data.overall_score}</span>
                  <span className="text-2xl text-gray-400">/ 100</span>
                  <span className={`text-2xl font-bold px-3 py-1 rounded-xl ${
                    data.grade === 'A' ? 'bg-green-100 text-green-700' :
                    data.grade === 'B' ? 'bg-blue-100 text-blue-700' :
                    data.grade === 'C' ? 'bg-yellow-100 text-yellow-700' :
                    'bg-red-100 text-red-700'
                  }`}>{data.grade}</span>
                  {data.delta !== null && <DeltaBadge delta={data.delta} />}
                </div>
                <p className="text-gray-500 mb-4">
                  {data.overall_score >= 80 ? '✅ Healthy repository — great engineering practices!' :
                   data.overall_score >= 60 ? '⚠️ Some areas need attention.' :
                   '🔴 Significant improvements needed across multiple dimensions.'}
                </p>

                {/* Recommendations */}
                {data.recommendations?.length > 0 && (
                  <div className="space-y-1.5">
                    {data.recommendations.map((rec: string, i: number) => (
                      <div key={i} className="flex items-start gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                        <Lightbulb size={13} className="mt-0.5 flex-shrink-0 text-amber-500" />
                        <span>{rec}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 mb-4 bg-gray-100 rounded-xl p-1 w-fit">
            {(['overview', 'history'] as const).map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all capitalize ${
                  tab === t ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {t === 'history' ? <><History size={13} className="inline mr-1.5" />History</> : t}
              </button>
            ))}
          </div>

          {tab === 'overview' && (
            <div className="grid grid-cols-2 gap-4">
              {Object.entries(data.dimensions).map(([key, dim]: [string, any]) => {
                const cfg  = DIMENSION_CONFIG[key] || DIMENSION_CONFIG.security
                const Icon = cfg.icon
                const prevScore = history[1]?.[`${key}_score`]

                return (
                  <div key={key} className="bg-white border border-gray-200 rounded-xl p-5 hover:border-gray-300 transition-colors">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <div className={`p-1.5 rounded-lg ${cfg.bg}`}>
                          <Icon size={13} className={cfg.color} />
                        </div>
                        <span className="font-semibold text-sm text-gray-800 capitalize">
                          {key.replace(/_/g, ' ')}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-400">{dim.weight}</span>
                        <span className="font-bold text-lg text-gray-900">{dim.score}</span>
                      </div>
                    </div>

                    <ScoreBar score={dim.score} previous={prevScore ? parseFloat(prevScore) : undefined} />

                    {/* Mini trend */}
                    {history.length > 1 && (
                      <MiniTrendBar history={history} field={`${key}_score`} />
                    )}

                    {/* Details */}
                    {dim.details && Object.keys(dim.details).filter(k => k !== 'recommendation').length > 0 && (
                      <div className="mt-3 space-y-1">
                        {Object.entries(dim.details)
                          .filter(([k]) => k !== 'recommendation' && k !== 'note')
                          .slice(0, 3)
                          .map(([k, v]) => (
                            <div key={k} className="flex justify-between text-xs text-gray-500">
                              <span className="capitalize">{k.replace(/_/g, ' ')}</span>
                              <span className="font-mono font-medium text-gray-700">{String(v)}</span>
                            </div>
                          ))}
                      </div>
                    )}

                    {/* Per-dimension recommendation */}
                    {dim.recommendation && (
                      <p className="mt-2 text-xs text-green-600 bg-green-50 rounded-lg px-2 py-1">
                        💡 {dim.recommendation}
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {tab === 'history' && (
            <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-100">
                <span className="font-semibold text-gray-700">Score History ({history.length} snapshots)</span>
              </div>
              {history.length === 0 ? (
                <p className="p-6 text-gray-400 text-sm">No history yet. Compute the score multiple times to see trends.</p>
              ) : (
                <div className="divide-y divide-gray-100">
                  {history.map((h: any, i: number) => {
                    const score = parseFloat(h.overall_score || 0)
                    const prev  = history[i + 1] ? parseFloat(history[i + 1].overall_score || 0) : null
                    const delta = prev !== null ? round1(score - prev) : null
                    return (
                      <div key={i} className="flex items-center gap-4 px-5 py-3 hover:bg-gray-50">
                        <div className={`text-2xl font-bold w-12 text-center ${
                          score >= 80 ? 'text-green-600' : score >= 60 ? 'text-yellow-600' : 'text-red-600'
                        }`}>{Math.round(score)}</div>
                        <div className="flex-1">
                          <div className="w-full bg-gray-100 rounded-full h-2">
                            <div
                              className={`h-2 rounded-full ${score >= 80 ? 'bg-green-500' : score >= 60 ? 'bg-yellow-500' : 'bg-red-500'}`}
                              style={{ width: `${score}%` }}
                            />
                          </div>
                        </div>
                        <DeltaBadge delta={delta} />
                        <span className="text-xs text-gray-400 w-36 text-right">
                          {new Date(h.created_at).toLocaleString()}
                        </span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function round1(n: number) { return Math.round(n * 10) / 10 }
