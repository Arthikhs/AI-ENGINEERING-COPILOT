import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Shield, AlertCircle, AlertTriangle, Info, CheckCircle, Loader2 } from 'lucide-react'
import { getRepositories, runSecurityReview } from '../services/api'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { getRiskColor } from '../lib/utils'
import ReactMarkdown from 'react-markdown'

const SEV_ICON: Record<string, any> = {
  CRITICAL: <AlertCircle size={14} className="text-red-600" />,
  HIGH:     <AlertTriangle size={14} className="text-orange-500" />,
  MEDIUM:   <AlertTriangle size={14} className="text-yellow-500" />,
  LOW:      <Info size={14} className="text-blue-500" />,
  INFO:     <CheckCircle size={14} className="text-gray-400" />,
}

const SEV_COLOR: Record<string, string> = {
  CRITICAL: 'border-l-red-500 bg-red-50',
  HIGH:     'border-l-orange-400 bg-orange-50',
  MEDIUM:   'border-l-yellow-400 bg-yellow-50',
  LOW:      'border-l-blue-400 bg-blue-50',
  INFO:     'border-l-gray-300 bg-gray-50',
}

export default function SecurityPage() {
  const [repoId, setRepoId] = useState('')
  const [result, setResult] = useState<any>(null)

  const { data: repos = [] } = useQuery({
    queryKey: ['repos'],
    queryFn: () => getRepositories().then(r => r.data),
  })

  const reviewMutation = useMutation({
    mutationFn: () => runSecurityReview(repoId).then(r => r.data),
    onSuccess: data => setResult(data),
  })

  const riskVariant = (r: string) => ({ critical: 'danger', high: 'danger', medium: 'warning', low: 'success' } as any)[r] ?? 'default'

  return (
    <div className="p-8 max-w-4xl">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 bg-red-100 rounded-xl"><Shield size={22} className="text-red-600" /></div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Security Review Agent</h1>
          <p className="text-sm text-gray-500">SQL Injection · XSS · SSRF · Hardcoded Secrets · Auth Flaws</p>
        </div>
      </div>

      <Card className="mb-6">
        <CardContent className="pt-4 flex gap-3">
          <select
            value={repoId}
            onChange={e => setRepoId(e.target.value)}
            className="flex-1 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">Select indexed repository...</option>
            {repos.filter((r: any) => r.is_indexed).map((r: any) => (
              <option key={r.id} value={r.id}>{r.full_name}</option>
            ))}
          </select>
          <Button onClick={() => reviewMutation.mutate()} disabled={!repoId} loading={reviewMutation.isPending}>
            <Shield size={14} /> Run Security Review
          </Button>
        </CardContent>
      </Card>

      {reviewMutation.isPending && (
        <div className="flex items-center gap-3 p-6 bg-white border border-gray-200 rounded-xl mb-4">
          <Loader2 className="animate-spin text-red-500" size={20} />
          <span className="text-gray-600">Scanning for vulnerabilities across codebase...</span>
        </div>
      )}

      {result && (
        <>
          {/* Summary bar */}
          <div className="flex items-center justify-between p-4 bg-white border border-gray-200 rounded-xl mb-4">
            <div className="flex items-center gap-4">
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wide">Overall Risk</p>
                <Badge variant={riskVariant(result.overall_risk)} className="mt-1 text-sm px-3 py-1">
                  {result.overall_risk?.toUpperCase()}
                </Badge>
              </div>
              <div className="w-px h-10 bg-gray-200" />
              <div className="text-center">
                <p className="text-2xl font-bold text-gray-900">{result.findings?.length ?? 0}</p>
                <p className="text-xs text-gray-500">Findings</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-gray-900">{result.files_analyzed ?? 0}</p>
                <p className="text-xs text-gray-500">Files Scanned</p>
              </div>
            </div>
          </div>

          {/* Summary */}
          {result.summary && (
            <Card className="mb-4">
              <CardHeader><h2 className="font-semibold text-gray-800">Executive Summary</h2></CardHeader>
              <CardContent><p className="text-sm text-gray-700">{result.summary}</p></CardContent>
            </Card>
          )}

          {/* Findings */}
          {result.findings?.length > 0 && (
            <Card>
              <CardHeader>
                <h2 className="font-semibold text-gray-800">Findings ({result.findings.length})</h2>
              </CardHeader>
              <CardContent className="space-y-3">
                {result.findings.map((f: any, i: number) => (
                  <div key={i} className={`border-l-4 px-4 py-3 rounded-r-xl ${SEV_COLOR[f.severity] ?? SEV_COLOR.INFO}`}>
                    <div className="flex items-center gap-2 mb-1">
                      {SEV_ICON[f.severity] ?? SEV_ICON.INFO}
                      <span className="text-xs font-bold text-gray-600">[{f.severity}]</span>
                      <span className="text-sm font-semibold text-gray-800">{f.category}</span>
                    </div>
                    {f.file && <p className="text-xs text-gray-500 mb-1">📁 {f.file}{f.line ? ` · line ${f.line}` : ''}</p>}
                    {f.explanation && <p className="text-sm text-gray-700 mb-2">{f.explanation}</p>}
                    {f.code && (
                      <pre className="text-xs bg-gray-900 text-red-300 px-3 py-2 rounded-lg overflow-x-auto mb-2">
                        {f.code}
                      </pre>
                    )}
                    {f.fix && (
                      <div className="mt-2">
                        <p className="text-xs font-semibold text-green-700 mb-1">✅ Fix:</p>
                        <p className="text-xs text-green-800">{f.fix}</p>
                      </div>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
