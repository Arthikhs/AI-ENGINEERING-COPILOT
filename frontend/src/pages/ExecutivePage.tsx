import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart2, Shield, GitPullRequest, Database, DollarSign, Zap, TrendingUp, AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { getExecutiveDashboard } from '../services/api'

function StatCard({ icon: Icon, label, value, sub, color }: any) {
  return (
    <Card>
      <CardContent className="py-5">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${color}`}>
            <Icon size={18} className="text-white" />
          </div>
          <div>
            <p className="text-xs text-gray-500">{label}</p>
            <p className="text-2xl font-bold text-gray-900">{value}</p>
            {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function RiskBar({ label, value, total, color }: { label: string; value: number; total: number; color: string }) {
  const pct = total > 0 ? (value / total) * 100 : 0
  return (
    <div className="flex items-center gap-3">
      <span className="w-20 text-xs text-gray-500 text-right">{label}</span>
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-6 text-xs font-bold text-gray-700">{value}</span>
    </div>
  )
}

export default function ExecutivePage() {
  const [days, setDays] = useState(30)
  const { data, isLoading } = useQuery({
    queryKey: ['executive', days],
    queryFn: () => getExecutiveDashboard(days).then(r => r.data),
  })

  if (isLoading) {
    return (
      <div className="p-8 flex items-center gap-3 text-gray-400">
        <Loader2 size={20} className="animate-spin" /> Loading executive dashboard...
      </div>
    )
  }

  const d = data
  const prTotal = Object.values(d?.pr_trends?.by_risk_level ?? {}).reduce((s: any, v: any) => s + v, 0) as number
  const topTask = Object.entries(d?.ai_usage?.by_task_type ?? {}).sort((a, b) => (b[1] as number) - (a[1] as number))[0] as [string, number] | undefined
  const topModel = Object.entries(d?.ai_usage?.model_distribution ?? {}).sort((a, b) => (b[1] as number) - (a[1] as number))[0] as [string, number] | undefined

  return (
    <div className="p-8 max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <TrendingUp size={22} className="text-indigo-600" />
          <h1 className="text-2xl font-bold text-gray-900">Executive Dashboard</h1>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500">Period:</span>
          {[7, 30, 90].map(n => (
            <button key={n} onClick={() => setDays(n)}
              className={`px-3 py-1 rounded-lg text-xs font-medium border transition-colors ${days === n ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-gray-600 border-gray-200 hover:border-indigo-300'}`}>
              {n}d
            </button>
          ))}
        </div>
      </div>

      {/* Top stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard icon={Database} label="Repositories" value={d?.repository_health?.total ?? 0}
          sub={`${d?.repository_health?.indexed ?? 0} indexed`} color="bg-blue-500" />
        <StatCard icon={Shield} label="Security Alerts" value={d?.security_risks?.critical_or_high ?? 0}
          sub={`${d?.security_risks?.pending_approvals ?? 0} pending approval`} color="bg-red-500" />
        <StatCard icon={Zap} label="AI Runs" value={d?.ai_usage?.total_runs ?? 0}
          sub={`Avg ${d?.ai_usage?.avg_latency_ms ?? 0}ms`} color="bg-indigo-500" />
        <StatCard icon={DollarSign} label="AI Cost" value={`$${d?.cost_summary?.total_cost_usd ?? 0}`}
          sub={`$${d?.cost_summary?.avg_cost_per_run ?? 0} per run`} color="bg-green-500" />
      </div>

      <div className="grid grid-cols-2 gap-6 mb-6">
        {/* PR Risk Distribution */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <GitPullRequest size={16} className="text-gray-500" />
              <h2 className="font-semibold text-gray-800">PR Review Risk Distribution</h2>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <RiskBar label="Critical" value={d?.pr_trends?.by_risk_level?.critical ?? 0} total={prTotal || 1} color="bg-red-500" />
              <RiskBar label="High"     value={d?.pr_trends?.by_risk_level?.high ?? 0}     total={prTotal || 1} color="bg-orange-400" />
              <RiskBar label="Medium"   value={d?.pr_trends?.by_risk_level?.medium ?? 0}   total={prTotal || 1} color="bg-yellow-400" />
              <RiskBar label="Low"      value={d?.pr_trends?.by_risk_level?.low ?? 0}       total={prTotal || 1} color="bg-green-400" />
            </div>
            <p className="text-xs text-gray-400 mt-3">{prTotal} total PR reviews in last {days} days</p>
          </CardContent>
        </Card>

        {/* AI Usage Breakdown */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <BarChart2 size={16} className="text-gray-500" />
              <h2 className="font-semibold text-gray-800">AI Usage Breakdown</h2>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {Object.entries(d?.ai_usage?.by_task_type ?? {}).map(([task, count]: [string, any]) => (
                <div key={task} className="flex items-center gap-3">
                  <span className="w-32 text-xs text-gray-500 truncate">{task}</span>
                  <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-full bg-indigo-400 rounded-full"
                      style={{ width: `${(count / (d?.ai_usage?.total_runs || 1)) * 100}%` }} />
                  </div>
                  <span className="text-xs font-bold text-gray-700 w-6">{count}</span>
                </div>
              ))}
              {!Object.keys(d?.ai_usage?.by_task_type ?? {}).length && (
                <p className="text-sm text-gray-400">No AI runs recorded yet.</p>
              )}
            </div>
            {topTask && <p className="text-xs text-gray-400 mt-3">Top task: <strong>{topTask[0]}</strong> ({String(topTask[1])} runs)</p>}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Cost Trend */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <DollarSign size={16} className="text-gray-500" />
              <h2 className="font-semibold text-gray-800">Daily Cost Trend</h2>
            </div>
          </CardHeader>
          <CardContent>
            {d?.cost_summary?.trend?.length ? (
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {d.cost_summary.trend.slice(-14).map((row: any) => (
                  <div key={row.date} className="flex items-center gap-3">
                    <span className="text-xs text-gray-500 w-24">{row.date}</span>
                    <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-full bg-green-400 rounded-full"
                        style={{ width: `${Math.min((row.cost_usd / 0.1) * 100, 100)}%` }} />
                    </div>
                    <span className="text-xs font-mono text-gray-700">${row.cost_usd}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-400">No cost data yet.</p>
            )}
          </CardContent>
        </Card>

        {/* Repository Health */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Database size={16} className="text-gray-500" />
              <h2 className="font-semibold text-gray-800">Repository Health</h2>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              {[
                { label: 'Total Repos',   value: d?.repository_health?.total ?? 0,   icon: Database,     color: 'text-blue-500' },
                { label: 'Indexed',       value: d?.repository_health?.indexed ?? 0, icon: CheckCircle2, color: 'text-green-500' },
                { label: 'Total Files',   value: (d?.repository_health?.total_files ?? 0).toLocaleString(),  icon: BarChart2, color: 'text-indigo-500' },
                { label: 'Total Chunks',  value: (d?.repository_health?.total_chunks ?? 0).toLocaleString(), icon: TrendingUp, color: 'text-purple-500' },
              ].map(item => (
                <div key={item.label} className="flex items-center gap-2">
                  <item.icon size={16} className={item.color} />
                  <div>
                    <p className="text-xs text-gray-500">{item.label}</p>
                    <p className="font-bold text-gray-800">{item.value}</p>
                  </div>
                </div>
              ))}
            </div>
            {d?.security_risks?.pending_approvals > 0 && (
              <div className="mt-4 flex items-center gap-2 p-3 bg-orange-50 border border-orange-200 rounded-lg">
                <AlertTriangle size={14} className="text-orange-500" />
                <span className="text-xs text-orange-700">
                  {d.security_risks.pending_approvals} security approvals pending human review
                </span>
              </div>
            )}
            {topModel && (
              <p className="text-xs text-gray-400 mt-3">
                Most used model: <strong className="text-gray-600">{topModel[0]}</strong> ({String(topModel[1])} runs)
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
