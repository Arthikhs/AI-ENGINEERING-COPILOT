import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Shield, GitBranch, TestTube, Code2, Package, BookOpen, RefreshCw } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { useAppStore } from '../store'
import api from '../services/api'

const DIMENSION_ICONS: Record<string, any> = {
  security: Shield,
  architecture: GitBranch,
  test_coverage: TestTube,
  code_quality: Code2,
  dependency_health: Package,
  documentation: BookOpen,
}

const DIMENSION_COLORS: Record<string, string> = {
  security: 'text-red-500',
  architecture: 'text-blue-500',
  test_coverage: 'text-green-500',
  code_quality: 'text-purple-500',
  dependency_health: 'text-orange-500',
  documentation: 'text-yellow-500',
}

function ScoreRing({ score, size = 120 }: { score: number; size?: number }) {
  const radius = size / 2 - 10
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (score / 100) * circumference
  const color = score >= 80 ? '#22c55e' : score >= 60 ? '#f59e0b' : '#ef4444'

  return (
    <svg width={size} height={size} className="rotate-[-90deg]">
      <circle cx={size / 2} cy={size / 2} r={radius} stroke="#e5e7eb" strokeWidth="8" fill="none" />
      <circle
        cx={size / 2} cy={size / 2} r={radius}
        stroke={color} strokeWidth="8" fill="none"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        style={{ transition: 'stroke-dashoffset 0.8s ease' }}
      />
      <text
        x={size / 2} y={size / 2 + 6}
        textAnchor="middle" fill={color}
        fontSize="20" fontWeight="bold"
        transform={`rotate(90, ${size / 2}, ${size / 2})`}
      >
        {Math.round(score)}
      </text>
    </svg>
  )
}

function ScoreBar({ score }: { score: number }) {
  const color = score >= 80 ? 'bg-green-500' : score >= 60 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="w-full bg-gray-100 rounded-full h-2 mt-2">
      <div className={`h-2 rounded-full ${color} transition-all duration-700`} style={{ width: `${score}%` }} />
    </div>
  )
}

export default function HealthScorePage() {
  const { selectedRepo } = useAppStore()
  const [repoId, setRepoId] = useState(selectedRepo?.id || '')

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['health-score', repoId],
    queryFn: () => api.get(`/enterprise/health-score/${repoId}`).then(r => r.data),
    enabled: !!repoId,
  })

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Repository Health Score</h1>
          <p className="text-gray-500 text-sm mt-1">Comprehensive quality assessment across 6 dimensions</p>
        </div>
        <Button onClick={() => refetch()} loading={isLoading} className="gap-2">
          <RefreshCw size={14} /> Refresh
        </Button>
      </div>

      {!repoId && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 text-yellow-700 text-sm">
          Select a repository from the sidebar to view its health score.
        </div>
      )}

      {isLoading && <div className="text-center py-20 text-gray-400">Computing health score...</div>}

      {data && (
        <>
          {/* Overall Score */}
          <div className="bg-white border border-gray-200 rounded-2xl p-8 mb-6 flex items-center gap-8">
            <ScoreRing score={data.overall_score} size={140} />
            <div>
              <p className="text-sm text-gray-500 mb-1">Overall Health Score</p>
              <div className="flex items-baseline gap-3">
                <span className="text-5xl font-bold text-gray-900">{data.overall_score}</span>
                <span className="text-2xl font-semibold text-gray-400">/ 100</span>
                <span className={`text-2xl font-bold px-3 py-1 rounded-lg ${
                  data.grade === 'A' ? 'bg-green-100 text-green-700' :
                  data.grade === 'B' ? 'bg-blue-100 text-blue-700' :
                  data.grade === 'C' ? 'bg-yellow-100 text-yellow-700' :
                  'bg-red-100 text-red-700'
                }`}>{data.grade}</span>
              </div>
              <p className="text-gray-500 text-sm mt-2">
                {data.overall_score >= 80 ? '✅ Healthy repository — keep it up!' :
                 data.overall_score >= 60 ? '⚠️ Some areas need attention.' :
                 '🔴 Significant improvements needed.'}
              </p>
            </div>
          </div>

          {/* Dimension Scores */}
          <div className="grid grid-cols-2 gap-4">
            {Object.entries(data.dimensions).map(([key, dim]: [string, any]) => {
              const Icon = DIMENSION_ICONS[key] || Code2
              const colorClass = DIMENSION_COLORS[key] || 'text-gray-500'
              return (
                <div key={key} className="bg-white border border-gray-200 rounded-xl p-5">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Icon size={16} className={colorClass} />
                      <span className="font-medium text-gray-700 capitalize">
                        {key.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-400">{dim.weight}</span>
                      <span className="font-bold text-gray-900">{dim.score}</span>
                    </div>
                  </div>
                  <ScoreBar score={dim.score} />
                  {dim.details && Object.keys(dim.details).length > 0 && (
                    <div className="mt-3 text-xs text-gray-500 space-y-1">
                      {Object.entries(dim.details).map(([k, v]) => (
                        <div key={k} className="flex justify-between">
                          <span className="capitalize">{k.replace(/_/g, ' ')}</span>
                          <span className="font-mono">{String(v)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
