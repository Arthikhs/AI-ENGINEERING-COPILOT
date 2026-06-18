import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { BarChart2, Plus, Play, GitCompare, Loader2, CheckCircle2, Clock } from 'lucide-react'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { cn } from '../lib/utils'
import { listBenchmarks, createBenchmark, runBenchmark, compareBenchmarks } from '../services/api'

const AGENT_TYPES = ['security_review', 'architecture', 'refactoring', 'test_generation', 'simple_qa', 'pr_review']
const MODELS = ['gpt-4o', 'gpt-4o-mini', 'claude-3-5-sonnet', 'claude-3-haiku', 'llama3']

const SAMPLE_CASES = [
  { question: 'Is this code vulnerable to SQL injection?', expected_answer: 'Yes, string concatenation in queries is a SQL injection risk.', contexts: ['cursor.execute("SELECT * FROM users WHERE id=" + user_id)'] },
  { question: 'What does this function do?', expected_answer: 'It authenticates the user and returns a JWT token.', contexts: ['def login(username, password): ...'] },
]

function StatusBadge({ status }: { status: string }) {
  const variants: Record<string, any> = { completed: 'success', running: 'warning', pending: 'default', failed: 'danger' }
  return <Badge variant={variants[status] ?? 'default'}>{status}</Badge>
}

function MetricBar({ label, value, max = 1, color }: { label: string; value: number | null; max?: number; color: string }) {
  const pct = value !== null ? Math.min((value / max) * 100, 100) : 0
  return (
    <div>
      <div className="flex justify-between text-xs text-gray-500 mb-1">
        <span>{label}</span>
        <span className="font-bold text-gray-700">{value !== null ? (max === 1 ? `${(value * 100).toFixed(1)}%` : `${value}`) : '—'}</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={cn('h-full rounded-full', color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function BenchmarkPage() {
  const qc = useQueryClient()
  const [agentFilter, setAgentFilter] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [compareA, setCompareA] = useState('')
  const [compareB, setCompareB] = useState('')
  const [compareResult, setCompareResult] = useState<any>(null)

  // Create form
  const [newAgent, setNewAgent] = useState('security_review')
  const [newLabel, setNewLabel] = useState('')
  const [newModel, setNewModel] = useState('gpt-4o-mini')
  const [useSample, setUseSample] = useState(true)

  const { data: listData, isLoading } = useQuery({
    queryKey: ['benchmarks', agentFilter],
    queryFn: () => listBenchmarks(agentFilter || undefined).then(r => r.data),
  })

  const createM = useMutation({
    mutationFn: () => createBenchmark(newAgent, newLabel, newModel, SAMPLE_CASES).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['benchmarks'] })
      setShowCreate(false)
      setNewLabel('')
    },
  })

  const runM = useMutation({
    mutationFn: (id: string) => runBenchmark(id).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['benchmarks'] }),
  })

  const compareM = useMutation({
    mutationFn: () => compareBenchmarks(compareA, compareB).then(r => r.data),
    onSuccess: setCompareResult,
  })

  const benchmarks = listData?.benchmarks ?? []

  return (
    <div className="p-8 max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <BarChart2 size={22} className="text-indigo-600" />
          <h1 className="text-2xl font-bold text-gray-900">Agent Benchmark Dashboard</h1>
        </div>
        <Button onClick={() => setShowCreate(!showCreate)}>
          <Plus size={14} className="mr-1" /> New Benchmark
        </Button>
      </div>

      {showCreate && (
        <Card className="mb-6">
          <CardHeader><h2 className="font-semibold text-gray-800">Create Benchmark</h2></CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-3 mb-3">
              <select value={newAgent} onChange={e => setNewAgent(e.target.value)}
                className="px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                {AGENT_TYPES.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
              <input value={newLabel} onChange={e => setNewLabel(e.target.value)} placeholder="Version label (e.g. security-v2)"
                className="px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              <select value={newModel} onChange={e => setNewModel(e.target.value)}
                className="px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                {MODELS.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <p className="text-xs text-gray-400 mb-3">Uses {SAMPLE_CASES.length} built-in test cases. Custom test cases coming soon.</p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
              <Button onClick={() => createM.mutate()} disabled={!newLabel} loading={createM.isPending}>Create</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Benchmark list */}
      <div className="space-y-3 mb-8">
        {isLoading && (
          <div className="flex items-center gap-2 text-gray-400 text-sm py-4">
            <Loader2 size={16} className="animate-spin" /> Loading benchmarks...
          </div>
        )}
        {benchmarks.map((b: any) => (
          <Card key={b.id}>
            <CardContent className="py-4">
              <div className="flex items-center gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold text-gray-800">{b.version_label}</span>
                    <Badge variant="info">{b.agent_type}</Badge>
                    <span className="text-xs font-mono text-gray-500">{b.model}</span>
                    <StatusBadge status={b.status} />
                  </div>
                  <div className="flex gap-4 text-xs text-gray-500">
                    <span>{b.test_case_count} test cases</span>
                    {b.accuracy !== null && <span>Accuracy: <strong>{(b.accuracy * 100).toFixed(1)}%</strong></span>}
                    {b.avg_latency_ms !== null && <span>Avg latency: <strong>{b.avg_latency_ms}ms</strong></span>}
                    {b.total_cost_usd !== null && <span>Cost: <strong>${b.total_cost_usd}</strong></span>}
                    {b.hallucination_rate !== null && <span>Hallucination: <strong>{(b.hallucination_rate * 100).toFixed(1)}%</strong></span>}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <input type="radio" name="compare_a" value={b.id} onChange={() => setCompareA(b.id)} className="accent-indigo-600" title="Compare A" />
                  <input type="radio" name="compare_b" value={b.id} onChange={() => setCompareB(b.id)} className="accent-purple-600" title="Compare B" />
                  {b.status === 'pending' && (
                    <Button
                      variant="outline"
                      onClick={() => runM.mutate(b.id)}
                      loading={runM.isPending}
                    >
                      <Play size={13} className="mr-1" /> Run
                    </Button>
                  )}
                  {b.status === 'running' && <Loader2 size={16} className="animate-spin text-indigo-500" />}
                  {b.status === 'completed' && <CheckCircle2 size={16} className="text-green-500" />}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
        {!isLoading && !benchmarks.length && (
          <div className="text-center py-12 text-gray-400 text-sm border border-dashed border-gray-300 rounded-xl">
            No benchmarks yet. Create one to compare agent versions.
          </div>
        )}
      </div>

      {/* Compare section */}
      {compareA && compareB && compareA !== compareB && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <GitCompare size={16} className="text-indigo-600" />
                <h2 className="font-semibold text-gray-800">Compare Benchmarks</h2>
              </div>
              <Button onClick={() => compareM.mutate()} loading={compareM.isPending}>Compare</Button>
            </div>
          </CardHeader>
          {compareResult && (
            <CardContent>
              <div className="grid grid-cols-2 gap-6">
                {(['a', 'b'] as const).map(key => {
                  const d = compareResult[key]
                  return (
                    <div key={key} className={cn('p-4 rounded-xl border', key === 'a' ? 'border-indigo-200 bg-indigo-50' : 'border-purple-200 bg-purple-50')}>
                      <div className="flex items-center gap-2 mb-3">
                        <span className={cn('font-bold text-sm', key === 'a' ? 'text-indigo-700' : 'text-purple-700')}>
                          {key.toUpperCase()}: {d.label}
                        </span>
                        <span className="text-xs text-gray-500">{d.model}</span>
                      </div>
                      <div className="space-y-3">
                        <MetricBar label="Accuracy" value={d.accuracy} color={key === 'a' ? 'bg-indigo-500' : 'bg-purple-500'} />
                        <MetricBar label="Hallucination Rate" value={d.hallucination_rate} color="bg-red-400" />
                        <MetricBar label="Avg Latency" value={d.avg_latency_ms} max={5000} color="bg-yellow-400" />
                      </div>
                    </div>
                  )
                })}
              </div>
              <div className="mt-4 p-3 bg-gray-50 rounded-xl border border-gray-200">
                <p className="text-xs font-semibold text-gray-600 mb-2">Delta (A − B)</p>
                <div className="flex flex-wrap gap-4 text-xs">
                  {Object.entries(compareResult.delta).map(([k, v]: [string, any]) => (
                    <span key={k} className={cn('font-mono', Number(v) > 0 ? 'text-green-600' : Number(v) < 0 ? 'text-red-600' : 'text-gray-500')}>
                      {k}: {v !== null ? (Number(v) > 0 ? '+' : '') + v : '—'}
                    </span>
                  ))}
                </div>
              </div>
            </CardContent>
          )}
        </Card>
      )}
    </div>
  )
}
