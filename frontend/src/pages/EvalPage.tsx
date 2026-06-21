import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  FlaskConical, Loader2, Plus, Trash2, CheckCircle,
  AlertTriangle, BarChart3, Zap, DollarSign, Brain,
  Trophy, GitCompare, ShieldAlert,
} from 'lucide-react'
import apiClient from '../services/api'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { cn } from '../lib/utils'

const api = {
  runBenchmark:        (d: any) => apiClient.post('/eval/benchmark', d).then(r => r.data),
  compareModels:       (d: any) => apiClient.post('/eval/compare', d).then(r => r.data),
  detectHallucination: (d: any) => apiClient.post('/eval/hallucination', d).then(r => r.data),
  getLeaderboard:      ()       => apiClient.get('/eval/leaderboard').then(r => r.data),
  getHallucinationStats: ()     => apiClient.get('/eval/stats/hallucination').then(r => r.data),
}

const MODELS = [
  'gpt-4o', 'gpt-4o-mini', 'claude-3-5-sonnet',
  'claude-3-haiku', 'gemini-1.5-pro', 'gemini-1.5-flash',
]

function ScoreBar({ label, value, inverse = false }: { label: string; value: number; inverse?: boolean }) {
  const pct = Math.round((value || 0) * 100)
  const good = inverse ? pct <= 30 : pct >= 70
  const warn = inverse ? pct <= 60 : pct >= 40
  const bar  = good ? 'bg-green-500' : warn ? 'bg-yellow-500' : 'bg-red-500'
  const txt  = good ? 'text-green-700' : warn ? 'text-yellow-700' : 'text-red-700'
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-gray-600 font-medium">{label}</span>
        <span className={cn('font-bold', txt)}>{pct}%</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-2">
        <div className={cn('h-2 rounded-full transition-all', bar)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

// ── Benchmark Tab ──────────────────────────────────────────────────────────────

function BenchmarkTab() {
  const [model, setModel]       = useState('gpt-4o-mini')
  const [taskType, setTaskType] = useState('simple_qa')
  const [result, setResult]     = useState<any>(null)

  const mutation = useMutation({
    mutationFn: () => api.runBenchmark({ model, task_type: taskType, use_default_cases: true, max_concurrency: 3 }),
    onSuccess: setResult,
  })

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader><h2 className="font-semibold text-gray-800">Run Model Benchmark</h2></CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="text-xs font-semibold text-gray-500 uppercase mb-1 block">Model</label>
              <select value={model} onChange={e => setModel(e.target.value)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                {MODELS.map(m => <option key={m}>{m}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-500 uppercase mb-1 block">Task Type</label>
              <select value={taskType} onChange={e => setTaskType(e.target.value)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                {['simple_qa', 'code_analysis', 'security_review', 'test_generation'].map(t =>
                  <option key={t}>{t}</option>
                )}
              </select>
            </div>
          </div>
          <Button onClick={() => mutation.mutate()} loading={mutation.isPending} className="w-full justify-center">
            <FlaskConical size={15} /> Run Benchmark (5 test cases)
          </Button>
          {mutation.isError && (
            <p className="text-xs text-red-600 mt-2 flex items-center gap-1">
              <AlertTriangle size={12} /> {String((mutation.error as any)?.message)}
            </p>
          )}
        </CardContent>
      </Card>

      {mutation.isPending && (
        <div className="flex items-center gap-3 p-4 bg-indigo-50 rounded-xl border border-indigo-200">
          <Loader2 className="animate-spin text-indigo-500" size={18} />
          <span className="text-sm text-indigo-700">Running benchmark on {model}...</span>
        </div>
      )}

      {result && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-800">{result.model}</h3>
              <Badge variant={result.quality_score >= 0.7 ? 'success' : result.quality_score >= 0.5 ? 'warning' : 'danger'}>
                Quality {Math.round((result.quality_score || 0) * 100)}%
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4 text-center">
              {[
                { label: 'Accuracy',      value: `${Math.round((result.accuracy || 0) * 100)}%`,      icon: CheckCircle, color: 'text-green-600' },
                { label: 'Hallucination', value: `${Math.round((result.avg_hallucination_rate || 0) * 100)}%`, icon: Brain,       color: 'text-red-500' },
                { label: 'p90 Latency',   value: `${result.p90_latency_ms}ms`,                        icon: Zap,         color: 'text-yellow-600' },
                { label: 'Cost/case',     value: `$${result.cost_per_case_usd}`,                      icon: DollarSign,  color: 'text-indigo-600' },
              ].map(({ label, value, icon: Icon, color }) => (
                <div key={label} className="p-3 bg-gray-50 rounded-xl">
                  <Icon size={16} className={cn('mx-auto mb-1', color)} />
                  <p className="text-lg font-bold text-gray-900">{value}</p>
                  <p className="text-xs text-gray-500">{label}</p>
                </div>
              ))}
            </div>
            <div className="space-y-3">
              <ScoreBar label="Accuracy"         value={result.accuracy} />
              <ScoreBar label="Faithfulness"     value={result.avg_faithfulness} />
              <ScoreBar label="Relevance"        value={result.avg_relevance} />
              <ScoreBar label="Hallucination"    value={result.avg_hallucination_rate} inverse />
            </div>
            <div className="mt-3 pt-3 border-t border-gray-100 flex gap-6 text-sm text-center">
              <div><span className="font-bold text-green-600">{result.passed}</span> <span className="text-gray-500">passed</span></div>
              <div><span className="font-bold text-red-500">{result.failed}</span> <span className="text-gray-500">failed</span></div>
              <div><span className="font-bold text-gray-700">{result.total_cases}</span> <span className="text-gray-500">total</span></div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

// ── Compare Tab ────────────────────────────────────────────────────────────────

function CompareTab() {
  const [selected, setSelected] = useState<string[]>(['gpt-4o-mini', 'gpt-4o'])
  const [taskType, setTaskType] = useState('simple_qa')
  const [result, setResult]     = useState<any>(null)

  const toggle = (m: string) =>
    setSelected(p => p.includes(m) ? p.filter(x => x !== m) : [...p, m])

  const mutation = useMutation({
    mutationFn: () => api.compareModels({ models: selected, task_type: taskType, use_default_cases: true }),
    onSuccess: setResult,
  })

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader><h2 className="font-semibold text-gray-800">Compare Models Side-by-Side</h2></CardHeader>
        <CardContent>
          <div className="mb-4">
            <label className="text-xs font-semibold text-gray-500 uppercase mb-2 block">Select Models</label>
            <div className="flex flex-wrap gap-2">
              {MODELS.map(m => (
                <button key={m} onClick={() => toggle(m)}
                  className={cn('px-3 py-1.5 rounded-full text-xs font-medium border transition-all',
                    selected.includes(m)
                      ? 'bg-indigo-600 text-white border-indigo-600'
                      : 'bg-white text-gray-600 border-gray-300 hover:border-indigo-400')}>
                  {m}
                </button>
              ))}
            </div>
          </div>
          <Button onClick={() => mutation.mutate()} disabled={selected.length < 2} loading={mutation.isPending} className="w-full justify-center">
            <GitCompare size={15} /> Compare {selected.length} Models
          </Button>
        </CardContent>
      </Card>

      {mutation.isPending && (
        <div className="flex items-center gap-3 p-4 bg-indigo-50 rounded-xl border border-indigo-200">
          <Loader2 className="animate-spin text-indigo-500" size={18} />
          <span className="text-sm text-indigo-700">Running parallel benchmarks on {selected.length} models...</span>
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-4 text-sm">
            <span>🏆 Best Quality: <strong className="text-indigo-600">{result.best_quality}</strong></span>
            <span>💰 Lowest Cost: <strong className="text-green-600">{result.lowest_cost}</strong></span>
            <span>⚡ Best Latency: <strong className="text-blue-600">{result.best_latency}</strong></span>
          </div>

          <div className="overflow-x-auto rounded-xl border border-gray-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {['Rank', 'Model', 'Quality', 'Accuracy', 'Hallucination', 'p90 Latency', 'Cost/case', 'Pareto'].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.leaderboard?.map((row: any, i: number) => {
                  const isPareto = result.pareto_optimal?.some((p: any) => p.model === row.model)
                  return (
                    <tr key={row.model} className={cn('border-t border-gray-100', i === 0 && 'bg-yellow-50')}>
                      <td className="px-4 py-3 font-bold text-gray-400">#{i + 1}</td>
                      <td className="px-4 py-3 font-medium text-gray-800">
                        {i === 0 && <Trophy size={12} className="inline text-yellow-500 mr-1" />}{row.model}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={row.quality_score >= 0.7 ? 'success' : 'warning'}>
                          {Math.round((row.quality_score || 0) * 100)}%
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-gray-600">{Math.round((row.accuracy || 0) * 100)}%</td>
                      <td className="px-4 py-3 text-gray-600">{Math.round((row.avg_hallucination_rate || 0) * 100)}%</td>
                      <td className="px-4 py-3 text-gray-600">{row.p90_latency_ms}ms</td>
                      <td className="px-4 py-3 text-gray-600">${row.cost_per_case_usd}</td>
                      <td className="px-4 py-3">{isPareto && <Badge variant="success">✓ Pareto</Badge>}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {result.regression_flags?.length > 0 && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-xl">
              <div className="flex items-center gap-2 mb-2">
                <ShieldAlert size={15} className="text-red-600" />
                <span className="text-sm font-semibold text-red-700">Regression Flags</span>
              </div>
              {result.regression_flags.map((f: any) => (
                <p key={f.model} className="text-xs text-red-600">
                  <span className="font-bold">{f.model}:</span> {f.issues.join(' | ')}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Hallucination Tab ──────────────────────────────────────────────────────────

function HallucinationTab() {
  const [question, setQuestion] = useState('')
  const [answer, setAnswer]     = useState('')
  const [contexts, setContexts] = useState<string[]>([''])
  const [useLLM, setUseLLM]     = useState(false)
  const [result, setResult]     = useState<any>(null)

  const mutation = useMutation({
    mutationFn: () => api.detectHallucination({
      question, answer, contexts: contexts.filter(Boolean), use_llm_judge: useLLM,
    }),
    onSuccess: setResult,
  })

  const riskStyle = (risk: string) =>
    risk === 'high'   ? 'text-red-700 bg-red-50 border-red-200' :
    risk === 'medium' ? 'text-yellow-700 bg-yellow-50 border-yellow-200' :
                        'text-green-700 bg-green-50 border-green-200'

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader><h2 className="font-semibold text-gray-800">Hallucination Detector</h2></CardHeader>
        <CardContent>
          <div className="space-y-4">
            <input value={question} onChange={e => setQuestion(e.target.value)}
              placeholder="Question asked to the model..."
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            <textarea value={answer} onChange={e => setAnswer(e.target.value)}
              placeholder="Model answer to evaluate..." rows={4}
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-semibold text-gray-500 uppercase">Reference Contexts</label>
                <button onClick={() => setContexts(p => [...p, ''])} className="flex items-center gap-1 text-xs text-indigo-600 hover:underline">
                  <Plus size={12} /> Add
                </button>
              </div>
              {contexts.map((c, i) => (
                <div key={i} className="flex gap-2 mb-2">
                  <textarea value={c} onChange={e => setContexts(p => p.map((x, j) => j === i ? e.target.value : x))}
                    placeholder={`Context ${i + 1}...`} rows={2}
                    className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-xs resize-none font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                  {contexts.length > 1 && (
                    <button onClick={() => setContexts(p => p.filter((_, j) => j !== i))} className="text-gray-400 hover:text-red-500">
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              ))}
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
              <input type="checkbox" checked={useLLM} onChange={e => setUseLLM(e.target.checked)} className="rounded" />
              Use LLM-as-Judge (more accurate, higher cost)
            </label>
            <Button onClick={() => mutation.mutate()} disabled={!question || !answer} loading={mutation.isPending} className="w-full justify-center">
              <Brain size={15} /> Detect Hallucination
            </Button>
          </div>
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardContent className="py-5">
            <div className={cn('inline-flex items-center gap-2 px-4 py-2 rounded-full border text-sm font-semibold mb-4', riskStyle(result.risk_level))}>
              <ShieldAlert size={14} /> Risk: {result.risk_level?.toUpperCase()}
            </div>
            <div className="space-y-3">
              <ScoreBar label="Hallucination Score (lower = better)" value={result.hallucination_score} inverse />
              <ScoreBar label="Faithfulness Score"                   value={result.faithfulness_score} />
              <ScoreBar label="N-gram Overlap"                       value={result.ngram_overlap} />
              <ScoreBar label="Entailment Score"                     value={result.entailment_score} />
              {result.llm_judge_score > 0 && <ScoreBar label="LLM Judge Score" value={result.llm_judge_score} />}
            </div>
            {result.llm_reasoning && (
              <div className="mt-4 p-3 bg-gray-50 rounded-lg text-xs text-gray-600 border border-gray-200">
                <span className="font-semibold text-gray-700">LLM Reasoning: </span>{result.llm_reasoning}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

// ── Leaderboard Tab ────────────────────────────────────────────────────────────

function LeaderboardTab() {
  const { data, isLoading } = useQuery({ queryKey: ['eval-leaderboard'], queryFn: api.getLeaderboard })
  const { data: hallStats } = useQuery({ queryKey: ['hallucination-stats'], queryFn: api.getHallucinationStats })

  if (isLoading) return (
    <div className="flex items-center gap-3 p-6 text-gray-500">
      <Loader2 className="animate-spin" size={18} /> Loading leaderboard...
    </div>
  )

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Trophy size={16} className="text-yellow-500" />
            <h2 className="font-semibold text-gray-800">Model Leaderboard</h2>
          </div>
        </CardHeader>
        <CardContent>
          {!data?.leaderboard?.length ? (
            <p className="text-sm text-gray-400 text-center py-8">No benchmark runs yet. Run a benchmark first.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    {['Rank', 'Model', 'Runs', 'Avg Accuracy', 'Hallucination', 'Avg Latency', 'Total Cost'].map(h => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.leaderboard.map((row: any, i: number) => (
                    <tr key={row.model} className={cn('border-b border-gray-100', i === 0 && 'bg-yellow-50')}>
                      <td className="px-4 py-3 font-bold text-gray-400">#{i + 1}</td>
                      <td className="px-4 py-3 font-medium text-gray-800">
                        {i === 0 && <Trophy size={12} className="inline text-yellow-500 mr-1" />}{row.model}
                      </td>
                      <td className="px-4 py-3 text-gray-600">{row.total_runs}</td>
                      <td className="px-4 py-3">
                        <Badge variant={(row.avg_accuracy || 0) >= 0.7 ? 'success' : 'warning'}>
                          {Math.round((row.avg_accuracy || 0) * 100)}%
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-gray-600">{Math.round((row.avg_hallucination_rate || 0) * 100)}%</td>
                      <td className="px-4 py-3 text-gray-600">{Math.round(row.avg_latency_ms || 0)}ms</td>
                      <td className="px-4 py-3 text-gray-600">${(row.total_cost || 0).toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {hallStats?.stats?.length > 0 && (
        <Card>
          <CardHeader><h2 className="font-semibold text-gray-800">Hallucination by Model</h2></CardHeader>
          <CardContent>
            <div className="space-y-3">
              {hallStats.stats.map((s: any) => (
                <div key={s.model} className="flex items-center gap-4">
                  <span className="text-sm font-medium text-gray-700 w-44 shrink-0">{s.model}</span>
                  <div className="flex-1"><ScoreBar label="" value={s.avg_hallucination || 0} inverse /></div>
                  <span className="text-xs text-gray-400 w-16 text-right">{s.total_evals} evals</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────

const TABS = [
  { id: 'benchmark',    label: 'Benchmark',    icon: BarChart3  },
  { id: 'compare',      label: 'Model Compare', icon: GitCompare },
  { id: 'hallucination',label: 'Hallucination', icon: Brain      },
  { id: 'leaderboard',  label: 'Leaderboard',   icon: Trophy     },
]

export default function EvalPage() {
  const [tab, setTab] = useState('benchmark')

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-center gap-2 mb-2">
        <FlaskConical size={22} className="text-indigo-600" />
        <h1 className="text-2xl font-bold text-gray-900">AI Evaluation</h1>
      </div>
      <p className="text-sm text-gray-500 mb-6">
        Benchmark models, detect hallucinations, compare quality vs cost, and track regressions.
      </p>

      <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-xl w-fit">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setTab(id)}
            className={cn('flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all',
              tab === id ? 'bg-white text-indigo-700 shadow-sm' : 'text-gray-600 hover:text-gray-800')}>
            <Icon size={14} />{label}
          </button>
        ))}
      </div>

      {tab === 'benchmark'     && <BenchmarkTab />}
      {tab === 'compare'       && <CompareTab />}
      {tab === 'hallucination' && <HallucinationTab />}
      {tab === 'leaderboard'   && <LeaderboardTab />}
    </div>
  )
}
