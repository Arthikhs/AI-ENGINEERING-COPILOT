import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  Bot, GitBranch, GitPullRequest, CheckCircle2, XCircle,
  Loader2, ChevronRight, ExternalLink, Play, RefreshCw,
  FileCode, TestTube, Shield, ClipboardList, Cpu, Search
} from 'lucide-react'
import {
  getRepositories, runAutonomousEngineer,
  getAutonomousJob, listAutonomousJobs
} from '../services/api'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'

const PIPELINE_STEPS = [
  { key: 'fetch',     label: 'Fetch Issue',       icon: ClipboardList },
  { key: 'analyze',   label: 'Analyze Reqs',      icon: Search },
  { key: 'plan',      label: 'Create Plan',        icon: Cpu },
  { key: 'code',      label: 'Generate Code',      icon: FileCode },
  { key: 'tests',     label: 'Generate Tests',     icon: TestTube },
  { key: 'execute',   label: 'Execute Tests',      icon: Play },
  { key: 'review',    label: 'Code Review',        icon: Shield },
  { key: 'pr',        label: 'Create PR',          icon: GitPullRequest },
]

const STATUS_CONFIG: Record<string, { color: string; icon: any; label: string }> = {
  queued:    { color: 'bg-gray-100 text-gray-600',   icon: Loader2,      label: 'Queued' },
  running:   { color: 'bg-blue-100 text-blue-700',   icon: Loader2,      label: 'Running' },
  completed: { color: 'bg-green-100 text-green-700', icon: CheckCircle2, label: 'Completed' },
  failed:    { color: 'bg-red-100 text-red-700',     icon: XCircle,      label: 'Failed' },
}

function getActiveStep(stepLog: string[]): number {
  if (!stepLog?.length) return 0
  const last = stepLog[stepLog.length - 1]
  if (last.includes('Step 1')) return 0
  if (last.includes('Step 2')) return 1
  if (last.includes('Step 3')) return 2
  if (last.includes('Step 4')) return 3
  if (last.includes('Step 5')) return 4
  if (last.includes('Step 6')) return 5
  if (last.includes('Step 7')) return 6
  if (last.includes('PR opened')) return 7
  return stepLog.length > 0 ? 7 : 0
}

function JobStatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.queued
  const Icon = cfg.icon
  const spinning = status === 'running' || status === 'queued'
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${cfg.color}`}>
      <Icon size={11} className={spinning ? 'animate-spin' : ''} />
      {cfg.label}
    </span>
  )
}

export default function AutonomousEngineerPage() {
  const [repoId, setRepoId]           = useState('')
  const [issueNumber, setIssueNumber] = useState('')
  const [activeJobId, setActiveJobId] = useState<string | null>(null)

  const { data: repos = [] } = useQuery({
    queryKey: ['repos'],
    queryFn: () => getRepositories().then(r => r.data),
  })

  const triggerMutation = useMutation({
    mutationFn: () => runAutonomousEngineer(repoId, parseInt(issueNumber)).then(r => r.data),
    onSuccess: (data) => setActiveJobId(data.job_id),
  })

  const { data: activeJob } = useQuery({
    queryKey: ['autonomous-job', activeJobId],
    queryFn: () => activeJobId ? getAutonomousJob(activeJobId).then(r => r.data) : null,
    enabled: !!activeJobId,
    refetchInterval: (data: any) =>
      data?.status === 'running' || data?.status === 'queued' ? 2000 : false,
  })

  const { data: jobHistory = [], refetch: refetchHistory } = useQuery({
    queryKey: ['autonomous-jobs', repoId],
    queryFn: () => listAutonomousJobs(repoId || undefined).then(r => r.data.jobs),
  })

  useEffect(() => {
    if (activeJob?.status === 'completed' || activeJob?.status === 'failed') {
      refetchHistory()
    }
  }, [activeJob?.status])

  const isPolling   = activeJob?.status === 'running' || activeJob?.status === 'queued'
  const activeStep  = activeJob ? getActiveStep(activeJob.step_log || []) : -1
  const indexedRepos = repos.filter((r: any) => r.is_indexed)

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 bg-indigo-100 rounded-xl">
          <Bot size={22} className="text-indigo-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Autonomous Engineer</h1>
          <p className="text-sm text-gray-500">GitHub Issue → Requirements → Plan → Code → Tests → Review → PR</p>
        </div>
      </div>

      {/* Pipeline Visualization */}
      <div className="flex items-center gap-1 mb-6 p-4 bg-gray-50 rounded-xl overflow-x-auto">
        {PIPELINE_STEPS.map((step, i) => {
          const Icon = step.icon
          const isDone    = activeJob && i < activeStep
          const isCurrent = activeJob && i === activeStep && isPolling
          return (
            <span key={step.key} className="flex items-center gap-1 flex-shrink-0">
              <span className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                isDone    ? 'bg-green-50 border-green-300 text-green-700' :
                isCurrent ? 'bg-indigo-600 border-indigo-600 text-white' :
                            'bg-white border-gray-200 text-gray-500'
              }`}>
                {isDone
                  ? <CheckCircle2 size={11} />
                  : isCurrent
                    ? <Loader2 size={11} className="animate-spin" />
                    : <Icon size={11} />
                }
                {step.label}
              </span>
              {i < PIPELINE_STEPS.length - 1 && (
                <ChevronRight size={12} className="text-gray-300 flex-shrink-0" />
              )}
            </span>
          )
        })}
      </div>

      {/* Trigger Form */}
      <Card className="mb-6">
        <CardHeader><h2 className="font-semibold text-gray-800">Run Autonomous Engineer</h2></CardHeader>
        <CardContent>
          <div className="flex gap-3">
            <select
              value={repoId}
              onChange={e => setRepoId(e.target.value)}
              className="flex-1 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">Select repository...</option>
              {indexedRepos.map((r: any) => (
                <option key={r.id} value={r.id}>{r.full_name}</option>
              ))}
            </select>
            <input
              type="number"
              value={issueNumber}
              onChange={e => setIssueNumber(e.target.value)}
              placeholder="Issue #"
              className="w-28 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <Button
              onClick={() => triggerMutation.mutate()}
              disabled={!repoId || !issueNumber || triggerMutation.isPending}
              loading={triggerMutation.isPending}
              className="gap-2"
            >
              <Play size={14} /> Run Agent
            </Button>
          </div>
          <p className="text-xs text-gray-400 mt-2">
            💡 Label any GitHub issue with <code className="bg-gray-100 px-1 rounded">ai-engineer</code> to auto-trigger via webhook
          </p>
        </CardContent>
      </Card>

      {/* Active Job */}
      {activeJob && (
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {isPolling
                  ? <Loader2 size={16} className="animate-spin text-indigo-500" />
                  : activeJob.status === 'completed'
                    ? <CheckCircle2 size={16} className="text-green-500" />
                    : <XCircle size={16} className="text-red-500" />
                }
                <h2 className="font-semibold text-gray-800">
                  Issue #{activeJob.issue_number}
                  {activeJob.issue_title && `: ${activeJob.issue_title}`}
                </h2>
              </div>
              <JobStatusBadge status={activeJob.status} />
            </div>
          </CardHeader>
          <CardContent>
            {/* Step Log */}
            <div className="bg-gray-950 rounded-xl p-4 mb-4 max-h-60 overflow-y-auto">
              {(activeJob.step_log || []).map((step: string, i: number) => (
                <div key={i} className="flex items-start gap-2 text-sm text-gray-300 mb-1">
                  <span className="text-gray-600 text-xs mt-0.5 font-mono">{String(i + 1).padStart(2, '0')}</span>
                  <span>{step}</span>
                </div>
              ))}
              {isPolling && (
                <div className="flex items-center gap-2 text-sm text-indigo-400 mt-1">
                  <Loader2 size={12} className="animate-spin" />
                  <span>Processing...</span>
                </div>
              )}
            </div>

            {/* Results Grid */}
            {activeJob.status === 'completed' && (
              <div className="grid grid-cols-3 gap-3 mb-4">
                <div className="bg-green-50 border border-green-200 rounded-xl p-3">
                  <p className="text-xs text-green-600 font-medium mb-1">Test Results</p>
                  <p className="text-sm font-bold text-green-800">
                    {activeJob.test_results?.passed ? '✅ Passed' :
                     activeJob.test_results?.skipped ? '⚠️ Skipped' : '❌ Failed'}
                  </p>
                </div>
                <div className="bg-blue-50 border border-blue-200 rounded-xl p-3">
                  <p className="text-xs text-blue-600 font-medium mb-1">Code Review</p>
                  <p className="text-sm font-bold text-blue-800">
                    {activeJob.review_result?.approved ? '✅ Approved' :
                     `⚠️ ${activeJob.review_result?.issues?.length || 0} issues`}
                  </p>
                </div>
                <div className="bg-purple-50 border border-purple-200 rounded-xl p-3">
                  <p className="text-xs text-purple-600 font-medium mb-1">Files Changed</p>
                  <p className="text-sm font-bold text-purple-800">
                    {activeJob.files_changed?.length || 0} file(s)
                  </p>
                </div>
              </div>
            )}

            {/* PR Link */}
            {activeJob.status === 'completed' && activeJob.pr_url && (
              <a
                href={activeJob.pr_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors"
              >
                <GitPullRequest size={14} />
                View PR #{activeJob.pr_number}
                <ExternalLink size={12} />
              </a>
            )}

            {/* Branch */}
            {activeJob.branch_name && (
              <div className="mt-3 flex items-center gap-2 text-xs text-gray-500">
                <GitBranch size={12} />
                <code className="bg-gray-100 px-1.5 py-0.5 rounded">{activeJob.branch_name}</code>
              </div>
            )}

            {/* Error */}
            {activeJob.status === 'failed' && activeJob.error && (
              <p className="mt-3 text-sm text-red-600 bg-red-50 p-3 rounded-lg">{activeJob.error}</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Job History */}
      {jobHistory.length > 0 && (
        <>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold text-gray-800">Job History</h2>
            <button onClick={() => refetchHistory()} className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1">
              <RefreshCw size={11} /> Refresh
            </button>
          </div>
          <div className="space-y-2">
            {jobHistory.map((job: any) => (
              <Card
                key={job.job_id}
                className="cursor-pointer hover:border-indigo-200 transition-colors"
                onClick={() => setActiveJobId(job.job_id)}
              >
                <CardContent className="flex items-center justify-between py-3">
                  <div className="flex items-center gap-3">
                    <JobStatusBadge status={job.status} />
                    <div>
                      <p className="text-sm font-medium text-gray-800">
                        Issue #{job.issue_number}
                        {job.issue_title && `: ${job.issue_title}`}
                      </p>
                      <p className="text-xs text-gray-400">
                        {job.repo_full_name}
                        {job.files_changed?.length > 0 && ` · ${job.files_changed.length} files`}
                      </p>
                    </div>
                  </div>
                  {job.pr_url && (
                    <a
                      href={job.pr_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={e => e.stopPropagation()}
                      className="flex items-center gap-1 text-xs text-indigo-600 hover:underline"
                    >
                      <GitPullRequest size={12} /> PR #{job.pr_number}
                    </a>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
