import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Network, Loader2, AlertTriangle, Layers, GitBranch } from 'lucide-react'
import { getRepositories, analyzeArchitecture, getLatestArchitectureReport } from '../services/api'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'

export default function ArchitecturePage() {
  const [repoId, setRepoId] = useState('')
  const [report, setReport] = useState<any>(null)

  const { data: repos = [] } = useQuery({
    queryKey: ['repos'],
    queryFn: () => getRepositories().then((r) => r.data),
  })

  const { data: latestReport, refetch: refetchLatest } = useQuery({
    queryKey: ['arch-report', repoId],
    queryFn: () => repoId ? getLatestArchitectureReport(repoId).then((r) => r.data) : null,
    enabled: !!repoId,
  })

  const analyzeMutation = useMutation({
    mutationFn: () => analyzeArchitecture(repoId).then((r) => r.data),
    onSuccess: (data) => {
      setReport(data)
      refetchLatest()
    },
  })

  const displayReport = report ?? latestReport

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-center gap-2 mb-6">
        <Network size={22} className="text-indigo-600" />
        <h1 className="text-2xl font-bold text-gray-900">Architecture Analyzer</h1>
      </div>

      {/* Controls */}
      <Card className="mb-6">
        <CardContent className="flex gap-3 pt-4">
          <select
            value={repoId}
            onChange={(e) => { setRepoId(e.target.value); setReport(null) }}
            className="flex-1 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">Select an indexed repository...</option>
            {repos.filter((r: any) => r.is_indexed).map((r: any) => (
              <option key={r.id} value={r.id}>{r.full_name}</option>
            ))}
          </select>
          <Button
            onClick={() => analyzeMutation.mutate()}
            disabled={!repoId}
            loading={analyzeMutation.isPending}
          >
            Analyze Architecture
          </Button>
        </CardContent>
      </Card>

      {analyzeMutation.isPending && (
        <div className="flex items-center gap-3 p-6 bg-white border border-gray-200 rounded-xl mb-6">
          <Loader2 className="animate-spin text-indigo-500" size={20} />
          <span className="text-gray-600">Analyzing repository architecture with AI...</span>
        </div>
      )}

      {displayReport && (
        <div className="space-y-4">
          {/* Summary */}
          <Card>
            <CardHeader><h2 className="font-semibold text-gray-800">Summary</h2></CardHeader>
            <CardContent>
              <p className="text-gray-700 text-sm mb-4">{displayReport.summary}</p>
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-indigo-50 rounded-xl p-4 text-center">
                  <p className="text-2xl font-bold text-indigo-700">{displayReport.service_count}</p>
                  <p className="text-xs text-indigo-500 mt-1">Services</p>
                </div>
                <div className="bg-green-50 rounded-xl p-4 text-center">
                  <p className="text-2xl font-bold text-green-700">{displayReport.api_count}</p>
                  <p className="text-xs text-green-500 mt-1">API Endpoints</p>
                </div>
                <div className={`rounded-xl p-4 text-center ${displayReport.circular_dependencies?.length > 0 ? 'bg-red-50' : 'bg-gray-50'}`}>
                  <p className={`text-2xl font-bold ${displayReport.circular_dependencies?.length > 0 ? 'text-red-700' : 'text-gray-700'}`}>
                    {displayReport.circular_dependencies?.length ?? 0}
                  </p>
                  <p className={`text-xs mt-1 ${displayReport.circular_dependencies?.length > 0 ? 'text-red-500' : 'text-gray-500'}`}>
                    Circular Deps
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Services */}
          {displayReport.services?.length > 0 && (
            <Card>
              <CardHeader>
                <h2 className="font-semibold text-gray-800 flex items-center gap-2">
                  <GitBranch size={15} /> Services / Modules
                </h2>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {displayReport.services.map((s: string) => (
                    <Badge key={s} variant="info">{s}</Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Dependency Graph */}
          {Object.keys(displayReport.dependency_graph ?? {}).length > 0 && (
            <Card>
              <CardHeader>
                <h2 className="font-semibold text-gray-800 flex items-center gap-2">
                  <Network size={15} /> Dependency Graph
                </h2>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {Object.entries(displayReport.dependency_graph).map(([svc, deps]: [string, any]) => (
                    <div key={svc} className="flex items-center gap-2 text-sm">
                      <span className="font-medium text-gray-700 w-40 truncate">{svc}</span>
                      <span className="text-gray-400">→</span>
                      <div className="flex flex-wrap gap-1">
                        {(Array.isArray(deps) ? deps : []).map((dep: string) => (
                          <Badge key={dep} variant="default">{dep}</Badge>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Circular Dependencies */}
          {displayReport.circular_dependencies?.length > 0 && (
            <Card>
              <CardHeader>
                <h2 className="font-semibold text-gray-800 flex items-center gap-2 text-red-700">
                  <AlertTriangle size={15} /> Circular Dependencies
                </h2>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {displayReport.circular_dependencies.map((cycle: string[], i: number) => (
                    <div key={i} className="flex items-center gap-1 text-sm text-red-700 bg-red-50 px-3 py-2 rounded-lg">
                      {cycle.map((c, j) => (
                        <span key={j}>
                          {c}{j < cycle.length - 1 && <span className="text-red-400 mx-1">→</span>}
                        </span>
                      ))}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Layers */}
          {Object.keys(displayReport.layers ?? {}).length > 0 && (
            <Card>
              <CardHeader>
                <h2 className="font-semibold text-gray-800 flex items-center gap-2">
                  <Layers size={15} /> Architectural Layers
                </h2>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {Object.entries(displayReport.layers).map(([layer, items]: [string, any]) => (
                    <div key={layer}>
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">{layer}</p>
                      <div className="flex flex-wrap gap-1.5">
                        {(Array.isArray(items) ? items : []).map((item: string) => (
                          <Badge key={item} variant="default">{item}</Badge>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
