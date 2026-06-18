import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { GitPullRequest, AlertTriangle, AlertCircle, Info, CheckCircle, Loader2 } from 'lucide-react'
import { getRepositories, reviewPR, getPRReviews } from '../services/api'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { getRiskColor, formatDate } from '../lib/utils'
import ReactMarkdown from 'react-markdown'

const severityIcon: Record<string, any> = {
  CRITICAL: <AlertCircle size={14} className="text-red-500" />,
  HIGH: <AlertTriangle size={14} className="text-orange-500" />,
  MEDIUM: <AlertTriangle size={14} className="text-yellow-500" />,
  LOW: <Info size={14} className="text-blue-500" />,
  INFO: <CheckCircle size={14} className="text-gray-400" />,
}

export default function PRReviewPage() {
  const [repoId, setRepoId] = useState('')
  const [prNumber, setPrNumber] = useState('')
  const [reviewResult, setReviewResult] = useState<any>(null)

  const { data: repos = [] } = useQuery({
    queryKey: ['repos'],
    queryFn: () => getRepositories().then((r) => r.data),
  })

  const { data: pastReviews = [], refetch } = useQuery({
    queryKey: ['pr-reviews', repoId],
    queryFn: () => repoId ? getPRReviews(repoId).then((r) => r.data) : Promise.resolve([]),
    enabled: !!repoId,
  })

  const reviewMutation = useMutation({
    mutationFn: () => reviewPR(repoId, parseInt(prNumber)).then((r) => r.data),
    onSuccess: (data) => {
      setReviewResult(data)
      refetch()
    },
  })

  const riskVariant = (level: string) => {
    const m: Record<string, any> = { critical: 'danger', high: 'danger', medium: 'warning', low: 'success' }
    return m[level] ?? 'default'
  }

  return (
    <div className="p-8 max-w-4xl">
      <div className="flex items-center gap-2 mb-6">
        <GitPullRequest size={22} className="text-indigo-600" />
        <h1 className="text-2xl font-bold text-gray-900">PR Review</h1>
      </div>

      {/* Form */}
      <Card className="mb-6">
        <CardHeader><h2 className="font-semibold text-gray-800">Analyze a Pull Request</h2></CardHeader>
        <CardContent>
          <div className="flex gap-3">
            <select
              value={repoId}
              onChange={(e) => setRepoId(e.target.value)}
              className="flex-1 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">Select repository...</option>
              {repos.map((r: any) => (
                <option key={r.id} value={r.id}>{r.full_name}</option>
              ))}
            </select>
            <input
              type="number"
              value={prNumber}
              onChange={(e) => setPrNumber(e.target.value)}
              placeholder="PR number"
              className="w-36 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <Button
              onClick={() => reviewMutation.mutate()}
              disabled={!repoId || !prNumber}
              loading={reviewMutation.isPending}
            >
              Review PR
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Current Review Result */}
      {reviewMutation.isPending && (
        <div className="flex items-center gap-3 p-6 bg-white border border-gray-200 rounded-xl mb-6">
          <Loader2 className="animate-spin text-indigo-500" size={20} />
          <span className="text-gray-600">Analyzing pull request diff with AI...</span>
        </div>
      )}

      {reviewResult && (
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-semibold text-gray-800">PR #{reviewResult.pr_number}: {reviewResult.pr_title}</h2>
              </div>
              <Badge variant={riskVariant(reviewResult.risk_level)}>
                Risk: {reviewResult.risk_level?.toUpperCase()}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            {/* Findings */}
            {reviewResult.findings?.length > 0 && (
              <div className="mb-4">
                <p className="text-sm font-medium text-gray-700 mb-2">Findings ({reviewResult.findings.length})</p>
                <div className="space-y-2">
                  {reviewResult.findings.map((f: any, i: number) => (
                    <div key={i} className="flex items-start gap-2 p-3 bg-gray-50 rounded-lg">
                      {severityIcon[f.severity] ?? severityIcon.INFO}
                      <div className="flex-1">
                        <span className="text-xs font-semibold text-gray-600">[{f.severity}]</span>
                        <span className="text-sm text-gray-700 ml-1">{f.description}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Full Summary */}
            <details className="mt-2">
              <summary className="text-sm text-indigo-600 cursor-pointer font-medium">Full AI Analysis</summary>
              <div className="mt-3 prose prose-sm max-w-none text-gray-700">
                <ReactMarkdown>{reviewResult.summary}</ReactMarkdown>
              </div>
            </details>
          </CardContent>
        </Card>
      )}

      {/* Past reviews */}
      {pastReviews.length > 0 && (
        <>
          <h2 className="text-lg font-semibold text-gray-800 mb-3">Past Reviews</h2>
          <div className="space-y-2">
            {pastReviews.map((r: any) => (
              <Card key={r.id}>
                <CardContent className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <GitPullRequest size={15} className="text-gray-400" />
                    <div>
                      <p className="text-sm font-medium text-gray-800">PR #{r.pr_number}: {r.pr_title}</p>
                      <p className="text-xs text-gray-400">{formatDate(r.created_at)} · {r.findings_count} findings</p>
                    </div>
                  </div>
                  <Badge variant={riskVariant(r.risk_level)}>{r.risk_level?.toUpperCase()}</Badge>
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
