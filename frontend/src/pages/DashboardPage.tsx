import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  GitBranch, MessageSquare, GitPullRequest, Network, Zap, ShieldAlert,
  Wrench, Search, Play, TrendingUp, GitCommit, Plug, BarChart2,
  BookMarked, AlertTriangle, DollarSign, CheckCircle2, Clock, Bot,
} from 'lucide-react'
import { getRepositories, getExecutiveDashboard, listHITLApprovals, listChangeReports, getRouterStats } from '../services/api'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { useAppStore } from '../store'
import { formatDate } from '../lib/utils'

const QUICK_ACTIONS = [
  { label: 'Chat with Code',    icon: MessageSquare, to: '/chat',                desc: 'Ask questions about your codebase',         color: 'bg-indigo-50 text-indigo-600' },
  { label: 'Auto Engineer',     icon: Bot,           to: '/autonomous-engineer', desc: 'Issue → Code → Tests → PR automatically',   color: 'bg-violet-50 text-violet-600' },
  { label: 'Agent Playground',  icon: Play,          to: '/playground',          desc: 'Run any agent interactively',               color: 'bg-purple-50 text-purple-600' },
  { label: 'Security Scan',     icon: ShieldAlert,   to: '/security',            desc: 'Detect vulnerabilities via Claude 3.5',     color: 'bg-red-50 text-red-600' },
  { label: 'PR Review',         icon: GitPullRequest,to: '/pr-review',           desc: 'AI-powered pull request analysis',           color: 'bg-blue-50 text-blue-600' },
  { label: 'Knowledge Graph',   icon: Network,       to: '/knowledge-graph',     desc: 'KG + RAG Fusion query',                     color: 'bg-green-50 text-green-600' },
  { label: 'Change Intel',      icon: GitCommit,     to: '/change-intelligence', desc: 'Push event impact analysis',                color: 'bg-orange-50 text-orange-600' },
  { label: 'Benchmarks',        icon: BarChart2,     to: '/benchmarks',          desc: 'Compare agent versions',                    color: 'bg-yellow-50 text-yellow-600' },
  { label: 'Executive View',    icon: TrendingUp,    to: '/executive',           desc: 'Cost, risk, AI usage for managers',         color: 'bg-teal-50 text-teal-600' },
  { label: 'Slack / Teams',     icon: Plug,          to: '/integrations',        desc: '@copilot commands integration',             color: 'bg-pink-50 text-pink-600' },
]

function StatCard({ icon: Icon, label, value, sub, color, onClick }: any) {
  return (
    <Card className={onClick ? 'cursor-pointer hover:shadow-md transition-shadow' : ''} onClick={onClick}>
      <CardContent className="flex items-center gap-4 py-4">
        <div className={`p-2.5 rounded-xl ${color}`}>
          <Icon size={20} />
        </div>
        <div>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          <p className="text-xs text-gray-500">{label}</p>
          {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
        </div>
      </CardContent>
    </Card>
  )
}

export default function DashboardPage() {
  const { user } = useAppStore()
  const navigate = useNavigate()

  const { data: repos = [] } = useQuery({
    queryKey: ['repos'],
    queryFn: () => getRepositories().then(r => r.data),
  })

  const { data: exec } = useQuery({
    queryKey: ['executive', 7],
    queryFn: () => getExecutiveDashboard(7).then(r => r.data),
  })

  const { data: hitlData } = useQuery({
    queryKey: ['hitl-approvals'],
    queryFn: () => listHITLApprovals().then(r => r.data),
  })

  const { data: changeData } = useQuery({
    queryKey: ['change-reports'],
    queryFn: () => listChangeReports().then(r => r.data),
  })

  const { data: routerStats } = useQuery({
    queryKey: ['router-stats'],
    queryFn: () => getRouterStats().then(r => r.data),
  })

  const indexedRepos = (repos as any[]).filter((r: any) => r.is_indexed)
  const pendingApprovals = (hitlData?.approvals ?? []).filter((a: any) => a.status === 'pending')
  const recentReports = (changeData?.reports ?? []).slice(0, 3)
  const totalRuns = exec?.ai_usage?.total_runs ?? 0
  const totalCost = exec?.cost_summary?.total_cost_usd ?? 0

  // Top model from router stats
  const topModel = (routerStats?.stats ?? []).reduce((best: any, cur: any) =>
    !best || cur.calls > best.calls ? cur : best, null)

  return (
    <div className="p-8 max-w-7xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">
          Welcome back, {user?.username} 👋
        </h1>
        <p className="text-gray-500 mt-1">AI Engineering Copilot — command centre</p>
      </div>

      {/* Top stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard icon={GitBranch}    label="Repositories"   value={repos.length}           sub={`${indexedRepos.length} indexed`}                  color="bg-indigo-50 text-indigo-600" onClick={() => navigate('/repositories')} />
        <StatCard icon={Bot}          label="AI Runs (7d)"   value={totalRuns}              sub={`$${totalCost} spent`}                             color="bg-purple-50 text-purple-600" onClick={() => navigate('/executive')} />
        <StatCard icon={AlertTriangle}label="HITL Pending"   value={pendingApprovals.length} sub="security approvals waiting"                       color={pendingApprovals.length > 0 ? 'bg-red-50 text-red-600' : 'bg-green-50 text-green-600'} onClick={() => navigate('/security')} />
        <StatCard icon={GitCommit}    label="Change Reports" value={changeData?.reports?.length ?? 0} sub="push event analyses"                color="bg-orange-50 text-orange-600" onClick={() => navigate('/change-intelligence')} />
      </div>

      <div className="grid grid-cols-3 gap-6 mb-8">
        {/* Quick Actions */}
        <div className="col-span-2">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Quick Actions</h2>
          <div className="grid grid-cols-3 gap-3">
            {QUICK_ACTIONS.map(({ label, icon: Icon, to, desc, color }) => (
              <Card key={to} onClick={() => navigate(to)} className="cursor-pointer hover:shadow-md transition-shadow">
                <CardContent className="py-4">
                  <div className={`w-8 h-8 rounded-lg ${color} flex items-center justify-center mb-2`}>
                    <Icon size={16} />
                  </div>
                  <p className="font-semibold text-gray-800 text-sm">{label}</p>
                  <p className="text-xs text-gray-400 mt-0.5 leading-relaxed">{desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Right column: alerts + model router */}
        <div className="space-y-4">
          {/* HITL Alerts */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <ShieldAlert size={15} className="text-red-500" />
                <h2 className="font-semibold text-gray-800 text-sm">Security Approvals</h2>
                {pendingApprovals.length > 0 && (
                  <span className="ml-auto bg-red-100 text-red-700 text-xs font-bold px-2 py-0.5 rounded-full">
                    {pendingApprovals.length}
                  </span>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {pendingApprovals.length === 0 ? (
                <div className="flex items-center gap-2 text-green-600 text-xs">
                  <CheckCircle2 size={14} /> No pending approvals
                </div>
              ) : (
                <div className="space-y-2">
                  {pendingApprovals.slice(0, 3).map((a: any) => (
                    <div key={a.id} className="flex items-center justify-between p-2 bg-red-50 rounded-lg border border-red-100">
                      <div>
                        <span className="text-xs font-bold text-red-700 uppercase">{a.overall_risk}</span>
                        <p className="text-xs text-gray-500 truncate max-w-[150px]">{a.summary?.slice(0, 50)}</p>
                      </div>
                      <button
                        onClick={() => navigate('/security')}
                        className="text-xs text-indigo-600 hover:underline"
                      >
                        Review
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Model Router Stats */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Zap size={15} className="text-indigo-500" />
                <h2 className="font-semibold text-gray-800 text-sm">Model Router</h2>
              </div>
            </CardHeader>
            <CardContent>
              {topModel ? (
                <div className="space-y-2">
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>Top model</span>
                    <span className="font-mono font-bold text-indigo-700">{topModel.model}</span>
                  </div>
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>Total calls</span>
                    <span className="font-bold text-gray-700">{topModel.calls}</span>
                  </div>
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>Avg latency</span>
                    <span className="font-bold text-gray-700">{topModel.avg_latency_ms}ms</span>
                  </div>
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>Total cost</span>
                    <span className="font-bold text-green-600">${topModel.total_cost_usd}</span>
                  </div>
                  <button onClick={() => navigate('/playground')} className="text-xs text-indigo-600 hover:underline mt-1">
                    Open Playground →
                  </button>
                </div>
              ) : (
                <p className="text-xs text-gray-400">No router invocations yet. Try the Agent Playground.</p>
              )}
            </CardContent>
          </Card>

          {/* AI Cost (7d) */}
          {exec?.cost_summary?.trend?.length > 0 && (
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <DollarSign size={15} className="text-green-500" />
                  <h2 className="font-semibold text-gray-800 text-sm">Cost (7d)</h2>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-1">
                  {exec.cost_summary.trend.slice(-5).map((row: any) => (
                    <div key={row.date} className="flex items-center gap-2">
                      <span className="text-xs text-gray-400 w-20">{row.date.slice(5)}</span>
                      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full bg-green-400 rounded-full"
                          style={{ width: `${Math.min((row.cost_usd / 0.05) * 100, 100)}%` }} />
                      </div>
                      <span className="text-xs font-mono text-gray-600">${row.cost_usd}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Recent Change Reports */}
      {recentReports.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">Recent Change Intelligence</h2>
            <button onClick={() => navigate('/change-intelligence')} className="text-xs text-indigo-600 hover:underline">View all →</button>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {recentReports.map((r: any) => (
              <Card key={r.id} onClick={() => navigate('/change-intelligence')} className="cursor-pointer hover:shadow-md transition-shadow">
                <CardContent className="py-3">
                  <div className="flex items-center gap-2 mb-1">
                    <GitCommit size={12} className="text-gray-400" />
                    <span className="text-xs font-mono text-gray-600">{r.commit_sha?.slice(0, 8)}</span>
                    <Badge variant="info" className="ml-auto text-[10px]">{r.branch}</Badge>
                  </div>
                  <p className="text-xs text-gray-700 truncate">{r.summary || 'No summary'}</p>
                  <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                    <span>{r.files_changed_count} files</span>
                    <span className={r.risk_count > 0 ? 'text-red-500 font-medium' : ''}>{r.risk_count} risks</span>
                    <span>{r.affected_services_count} services</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Repositories */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">Repositories</h2>
          <button onClick={() => navigate('/repositories')} className="text-xs text-indigo-600 hover:underline">Manage →</button>
        </div>
        <div className="space-y-2">
          {(repos as any[]).slice(0, 5).map((repo: any) => (
            <Card key={repo.id} onClick={() => navigate('/chat')} className="cursor-pointer hover:shadow-md transition-shadow">
              <CardContent className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3">
                  <GitBranch size={15} className="text-gray-400" />
                  <div>
                    <p className="font-medium text-gray-800 text-sm">{repo.full_name}</p>
                    <p className="text-xs text-gray-400">
                      {repo.total_files} files · {repo.total_chunks} chunks
                      {repo.last_synced_at && ` · synced ${formatDate(repo.last_synced_at)}`}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {repo.language && <Badge variant="info">{repo.language}</Badge>}
                  <Badge variant={repo.is_indexed ? 'success' : 'warning'}>
                    {repo.is_indexed ? 'Indexed' : 'Not indexed'}
                  </Badge>
                </div>
              </CardContent>
            </Card>
          ))}
          {repos.length === 0 && (
            <Card>
              <CardContent className="text-center py-10 text-gray-400">
                <GitBranch size={32} className="mx-auto mb-3 opacity-30" />
                <p className="font-medium">No repositories connected</p>
                <p className="text-sm mt-1">
                  <button onClick={() => navigate('/repositories')} className="text-indigo-600 underline">
                    Connect your first repository
                  </button>
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
