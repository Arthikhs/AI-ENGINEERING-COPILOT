import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { GitCommit, AlertTriangle, Layers, Play, ChevronRight, Loader2, Shield, Zap } from 'lucide-react'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { cn } from '../lib/utils'
import { listChangeReports, getChangeReport, manualChangeAnalyze, getRepositories } from '../services/api'

const RISK_COLOR: Record<string, string> = {
  HIGH:     'text-red-700 bg-red-50 border-red-200',
  CRITICAL: 'text-red-800 bg-red-100 border-red-300',
  MEDIUM:   'text-yellow-700 bg-yellow-50 border-yellow-200',
  LOW:      'text-green-700 bg-green-50 border-green-200',
}

const LAYER_COLOR: Record<string, string> = {
  api:                  'bg-blue-100 text-blue-700',
  service:              'bg-indigo-100 text-indigo-700',
  model:                'bg-green-100 text-green-700',
  database_migration:   'bg-red-100 text-red-700',
  config:               'bg-gray-100 text-gray-600',
  infrastructure:       'bg-purple-100 text-purple-700',
  test:                 'bg-orange-100 text-orange-700',
  general:              'bg-slate-100 text-slate-600',
}

export default function ChangeIntelligencePage() {
  const qc = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [repoId, setRepoId] = useState('')
  const [manualFiles, setManualFiles] = useState('')
  const [showManual, setShowManual] = useState(false)

  const { data: repos = [] } = useQuery({
    queryKey: ['repos'],
    queryFn: () => getRepositories().then(r => r.data),
  })

  const { data: listData, isLoading } = useQuery({
    queryKey: ['change-reports', repoId],
    queryFn: () => listChangeReports(repoId || undefined).then(r => r.data),
  })

  const { data: detail } = useQuery({
    queryKey: ['change-report', selectedId],
    queryFn: () => getChangeReport(selectedId!).then(r => r.data),
    enabled: !!selectedId,
  })

  const analyzeM = useMutation({
    mutationFn: () => manualChangeAnalyze(
      repoId,
      manualFiles.split('\n').map(f => f.trim()).filter(Boolean)
    ).then(r => r.data),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['change-reports'] })
      setSelectedId(data.report_id)
      setShowManual(false)
    },
  })

  const reports = listData?.reports ?? []

  return (
    <div className="p-8 max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <GitCommit size={22} className="text-indigo-600" />
          <h1 className="text-2xl font-bold text-gray-900">Repository Change Intelligence</h1>
        </div>
        <Button onClick={() => setShowManual(!showManual)}>
          <Play size={14} className="mr-1" /> Manual Analysis
        </Button>
      </div>

      {/* Manual trigger */}
      {showManual && (
        <Card className="mb-6">
          <CardHeader><h2 className="font-semibold text-gray-800">Manually Trigger Analysis</h2></CardHeader>
          <CardContent>
            <p className="text-xs text-gray-400 mb-3">Simulates a push event. Normally triggered automatically by GitHub webhook.</p>
            <div className="flex gap-3 mb-3">
              <select
                value={repoId}
                onChange={e => setRepoId(e.target.value)}
                className="flex-1 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">Select repository...</option>
                {(repos as any[]).filter((r: any) => r.is_indexed).map((r: any) => (
                  <option key={r.id} value={r.id}>{r.full_name}</option>
                ))}
              </select>
            </div>
            <textarea
              value={manualFiles}
              onChange={e => setManualFiles(e.target.value)}
              placeholder="Enter changed file paths, one per line&#10;e.g.&#10;backend/api/auth.py&#10;backend/models/user.py&#10;frontend/src/pages/LoginPage.tsx"
              rows={5}
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none mb-3"
            />
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowManual(false)}>Cancel</Button>
              <Button
                onClick={() => analyzeM.mutate()}
                disabled={!repoId || !manualFiles.trim()}
                loading={analyzeM.isPending}
              >
                Analyze Impact
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="flex gap-6">
        {/* Left: report list */}
        <div className="w-72 flex-shrink-0">
          <select
            value={repoId}
            onChange={e => setRepoId(e.target.value)}
            className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">All repositories</option>
            {(repos as any[]).map((r: any) => (
              <option key={r.id} value={r.id}>{r.full_name}</option>
            ))}
          </select>

          {isLoading && (
            <div className="flex items-center gap-2 text-gray-400 text-sm py-4">
              <Loader2 size={14} className="animate-spin" /> Loading reports...
            </div>
          )}

          <div className="space-y-2">
            {reports.map((r: any) => (
              <button
                key={r.id}
                onClick={() => setSelectedId(r.id)}
                className={cn(
                  'w-full text-left px-4 py-3 rounded-xl border transition-colors',
                  selectedId === r.id
                    ? 'border-indigo-400 bg-indigo-50'
                    : 'border-gray-200 bg-white hover:border-indigo-200'
                )}
              >
                <div className="flex items-center gap-2 mb-1">
                  <GitCommit size={12} className="text-gray-400" />
                  <span className="text-xs font-mono text-gray-600 truncate">{r.commit_sha?.slice(0, 8)}</span>
                  <span className="text-xs text-gray-400">{r.branch}</span>
                </div>
                <p className="text-xs text-gray-700 truncate mb-1">{r.summary || 'No summary'}</p>
                <div className="flex items-center gap-2 text-xs text-gray-400">
                  <span>{r.files_changed_count} files</span>
                  <span>·</span>
                  <span className={r.risk_count > 0 ? 'text-red-500 font-medium' : ''}>{r.risk_count} risks</span>
                  <span>·</span>
                  <span>{r.affected_services_count} services</span>
                </div>
              </button>
            ))}
            {!isLoading && !reports.length && (
              <div className="text-center py-8 text-gray-400 text-sm border border-dashed border-gray-300 rounded-xl">
                No reports yet. Push to GitHub or use Manual Analysis.
              </div>
            )}
          </div>
        </div>

        {/* Right: report detail */}
        <div className="flex-1 min-w-0 space-y-4">
          {!selectedId && !analyzeM.isPending && (
            <div className="flex items-center justify-center h-48 border border-dashed border-gray-300 rounded-xl text-gray-400 text-sm">
              Select a report to view the impact analysis
            </div>
          )}

          {analyzeM.isPending && (
            <div className="flex items-center gap-3 p-6 bg-white border border-gray-200 rounded-xl">
              <Loader2 className="animate-spin text-indigo-500" size={20} />
              <span className="text-gray-600 text-sm">Running AI change impact analysis...</span>
            </div>
          )}

          {detail && (
            <>
              {/* Header */}
              <Card>
                <CardContent className="py-4">
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="font-mono text-sm font-bold text-indigo-700">{detail.commit_sha?.slice(0, 12)}</span>
                    <Badge variant="info">{detail.branch}</Badge>
                    {detail.pusher && <span className="text-xs text-gray-500">by {detail.pusher}</span>}
                    <span className="text-xs text-gray-400 ml-auto">{new Date(detail.created_at).toLocaleString()}</span>
                  </div>
                  {detail.summary && (
                    <p className="text-sm text-gray-700 mt-2 leading-relaxed">{detail.summary}</p>
                  )}
                </CardContent>
              </Card>

              {/* Files Changed */}
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <GitCommit size={15} className="text-gray-500" />
                    <h2 className="font-semibold text-gray-800">Files Changed ({detail.files_changed?.length ?? 0})</h2>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-1 max-h-48 overflow-y-auto">
                    {detail.files_changed?.map((f: string, i: number) => {
                      const layer = detail.architectural_impact?.layers_affected?.[0] || 'general'
                      const ext = f.split('.').pop() || ''
                      const inferredLayer =
                        f.includes('test') ? 'test' :
                        f.includes('migration') ? 'database_migration' :
                        f.includes('api/') || f.includes('router') ? 'api' :
                        f.includes('model') ? 'model' :
                        f.includes('config') || f.includes('.env') ? 'config' :
                        f.includes('service') ? 'service' :
                        'general'
                      return (
                        <div key={i} className="flex items-center gap-2 text-xs">
                          <span className={cn('px-1.5 py-0.5 rounded text-xs font-medium', LAYER_COLOR[inferredLayer] ?? LAYER_COLOR.general)}>
                            {inferredLayer}
                          </span>
                          <span className="font-mono text-gray-700 truncate">{f}</span>
                        </div>
                      )
                    })}
                  </div>
                </CardContent>
              </Card>

              <div className="grid grid-cols-2 gap-4">
                {/* Architectural Impact */}
                <Card>
                  <CardHeader>
                    <div className="flex items-center gap-2">
                      <Layers size={15} className="text-blue-500" />
                      <h2 className="font-semibold text-gray-800">Architectural Impact</h2>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {detail.architectural_impact?.layers_affected?.map((l: string) => (
                        <span key={l} className={cn('px-2 py-0.5 rounded text-xs font-medium', LAYER_COLOR[l] ?? LAYER_COLOR.general)}>{l}</span>
                      ))}
                    </div>
                    {detail.architectural_impact?.is_breaking_change && (
                      <div className="flex items-center gap-1.5 text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-2">
                        <AlertTriangle size={12} /> Breaking change detected
                      </div>
                    )}
                    {detail.architectural_impact?.interfaces_modified?.length > 0 && (
                      <div>
                        <p className="text-xs text-gray-500 mb-1">Modified interfaces:</p>
                        {detail.architectural_impact.interfaces_modified.map((iface: string, i: number) => (
                          <p key={i} className="text-xs font-mono text-gray-700">{iface}</p>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Affected Services */}
                <Card>
                  <CardHeader>
                    <div className="flex items-center gap-2">
                      <Zap size={15} className="text-purple-500" />
                      <h2 className="font-semibold text-gray-800">Affected Services</h2>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {detail.affected_services?.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5">
                        {detail.affected_services.map((s: string, i: number) => (
                          <span key={i} className="px-2 py-1 bg-purple-50 border border-purple-200 text-purple-700 rounded-lg text-xs font-medium">
                            {s}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-gray-400">No affected services detected.</p>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Risks */}
              {detail.risks?.length > 0 && (
                <Card>
                  <CardHeader>
                    <div className="flex items-center gap-2">
                      <Shield size={15} className="text-red-500" />
                      <h2 className="font-semibold text-gray-800">Risks ({detail.risks.length})</h2>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {detail.risks.map((r: any, i: number) => (
                        <div key={i} className={cn('p-3 rounded-xl border text-xs', RISK_COLOR[r.level] ?? RISK_COLOR.LOW)}>
                          <div className="flex items-center gap-2 mb-1">
                            <AlertTriangle size={12} />
                            <span className="font-bold">{r.level}</span>
                            {r.file && <span className="font-mono opacity-70">{r.file}</span>}
                          </div>
                          <p>{r.description}</p>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Recommendation */}
              {detail.recommendation && (
                <Card>
                  <CardHeader><h2 className="font-semibold text-gray-800">Recommendation</h2></CardHeader>
                  <CardContent>
                    <p className="text-sm text-gray-700 leading-relaxed">{detail.recommendation}</p>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
