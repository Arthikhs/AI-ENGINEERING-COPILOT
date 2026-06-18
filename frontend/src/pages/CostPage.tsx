import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { DollarSign, Zap, TrendingUp, Bot, Loader2 } from 'lucide-react'
import { getCostSummary } from '../services/api'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { cn } from '../lib/utils'

const PERIOD_OPTIONS = [7, 14, 30]

function StatCard({ label, value, sub, icon: Icon, color }: any) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 py-5">
        <div className={cn('p-3 rounded-xl', color)}>
          <Icon size={20} />
        </div>
        <div>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          <p className="text-sm text-gray-500">{label}</p>
          {sub && <p className="text-xs text-gray-400">{sub}</p>}
        </div>
      </CardContent>
    </Card>
  )
}

function BarRow({ label, cost, maxCost, calls, variant }: any) {
  const pct = maxCost > 0 ? Math.round((cost / maxCost) * 100) : 0
  const colors: Record<string, string> = {
    indigo: 'bg-indigo-500', blue: 'bg-blue-500', green: 'bg-green-500',
    orange: 'bg-orange-400', purple: 'bg-purple-500', pink: 'bg-pink-500',
  }
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-gray-600 w-44 truncate font-mono">{label}</span>
      <div className="flex-1 bg-gray-100 rounded-full h-2">
        <div className={cn('h-2 rounded-full', colors[variant] ?? 'bg-indigo-500')} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-semibold text-gray-700 w-16 text-right">${cost.toFixed(4)}</span>
      <span className="text-xs text-gray-400 w-14 text-right">{calls} calls</span>
    </div>
  )
}

const MODEL_COLORS: Record<string, string> = {
  'gpt-4o': 'indigo', 'gpt-4o-mini': 'blue', 'gpt-4-turbo': 'purple',
  'text-embedding-3-large': 'green', 'text-embedding-3-small': 'orange',
}

const AGENT_COLORS = ['indigo', 'blue', 'green', 'orange', 'purple', 'pink']

export default function CostPage() {
  const [days, setDays] = useState(7)

  const { data, isLoading, error } = useQuery({
    queryKey: ['costs', days],
    queryFn: () => getCostSummary(days).then((r) => r.data),
    refetchInterval: 30_000,
  })

  const maxModelCost = data ? Math.max(...Object.values(data.by_model as any).map((m: any) => m.cost), 0.001) : 1
  const maxAgentCost = data ? Math.max(...Object.values(data.by_agent as any).map((a: any) => a.cost), 0.001) : 1

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <DollarSign size={22} className="text-indigo-600" />
          <h1 className="text-2xl font-bold text-gray-900">Cost Analytics</h1>
        </div>
        <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
          {PERIOD_OPTIONS.map((d) => (
            <button key={d} onClick={() => setDays(d)}
              className={cn('px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                days === d ? 'bg-white text-indigo-700 shadow-sm' : 'text-gray-500 hover:text-gray-700')}>
              {d}d
            </button>
          ))}
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center gap-3 p-8 justify-center">
          <Loader2 className="animate-spin text-indigo-500" size={20} />
          <span className="text-gray-500 text-sm">Loading cost data...</span>
        </div>
      )}

      {error && (
        <Card><CardContent className="text-center py-10 text-gray-400">
          Cost tracking requires Redis. Make sure Redis is running.
        </CardContent></Card>
      )}

      {data && (
        <div className="space-y-6">
          {/* Summary stats */}
          <div className="grid grid-cols-3 gap-4">
            <StatCard label={`Total Cost (${days}d)`} value={`$${data.total_cost_usd.toFixed(4)}`}
              icon={DollarSign} color="bg-indigo-50 text-indigo-600" />
            <StatCard label="Total LLM Calls" value={data.total_calls.toLocaleString()}
              sub={`${days}-day period`} icon={Zap} color="bg-blue-50 text-blue-600" />
            <StatCard label="Avg Cost / Call"
              value={data.total_calls > 0 ? `$${(data.total_cost_usd / data.total_calls).toFixed(5)}` : '$0'}
              icon={TrendingUp} color="bg-green-50 text-green-600" />
          </div>

          {/* Daily chart */}
          <Card>
            <CardHeader><h2 className="font-semibold text-gray-800">Daily Spend</h2></CardHeader>
            <CardContent>
              <div className="space-y-2">
                {data.daily.map((d: any) => {
                  const maxDay = Math.max(...data.daily.map((x: any) => x.cost), 0.001)
                  const pct = Math.round((d.cost / maxDay) * 100)
                  return (
                    <div key={d.date} className="flex items-center gap-3">
                      <span className="text-xs text-gray-500 w-24">{d.date}</span>
                      <div className="flex-1 bg-gray-100 rounded-full h-2">
                        <div className="h-2 bg-indigo-400 rounded-full" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="text-xs font-mono text-gray-700 w-16 text-right">${d.cost.toFixed(4)}</span>
                      <span className="text-xs text-gray-400 w-16 text-right">{d.calls} calls</span>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>

          {/* By model */}
          {Object.keys(data.by_model).length > 0 && (
            <Card>
              <CardHeader><h2 className="font-semibold text-gray-800">Cost by Model</h2></CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {Object.entries(data.by_model as Record<string, any>)
                    .sort((a, b) => b[1].cost - a[1].cost)
                    .map(([model, stats]) => (
                      <div key={model}>
                        <BarRow label={model} cost={stats.cost} maxCost={maxModelCost}
                          calls={stats.calls} variant={MODEL_COLORS[model] ?? 'indigo'} />
                        <div className="flex gap-4 ml-48 mt-1">
                          <span className="text-[10px] text-gray-400">
                            ↑ {(stats.prompt_tokens ?? 0).toLocaleString()} prompt tokens
                          </span>
                          <span className="text-[10px] text-gray-400">
                            ↓ {(stats.completion_tokens ?? 0).toLocaleString()} completion tokens
                          </span>
                        </div>
                      </div>
                    ))}
                </div>

                {/* Pricing reference */}
                <details className="mt-4">
                  <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600">
                    Pricing reference (per 1M tokens)
                  </summary>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {Object.entries(data.pricing_reference as Record<string, any>).map(([model, p]) => (
                      <div key={model} className="text-[10px] bg-gray-50 border border-gray-200 px-2 py-1 rounded font-mono">
                        {model}: in ${p.input} / out ${p.output}
                      </div>
                    ))}
                  </div>
                </details>
              </CardContent>
            </Card>
          )}

          {/* By agent */}
          {Object.keys(data.by_agent).length > 0 && (
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Bot size={15} className="text-gray-500" />
                  <h2 className="font-semibold text-gray-800">Cost by Agent</h2>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {Object.entries(data.by_agent as Record<string, any>)
                    .sort((a, b) => b[1].cost - a[1].cost)
                    .map(([agent, stats], i) => (
                      <BarRow key={agent} label={agent} cost={stats.cost} maxCost={maxAgentCost}
                        calls={stats.calls} variant={AGENT_COLORS[i % AGENT_COLORS.length]} />
                    ))}
                </div>
              </CardContent>
            </Card>
          )}

          {data.total_calls === 0 && (
            <Card><CardContent className="text-center py-10 text-gray-400">
              <DollarSign size={32} className="mx-auto mb-3 opacity-20" />
              <p>No cost data yet. Start using agents to track spending.</p>
            </CardContent></Card>
          )}
        </div>
      )}
    </div>
  )
}
