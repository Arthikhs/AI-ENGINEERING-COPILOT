import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { FlaskConical, Loader2, Plus, Trash2, CheckCircle, AlertTriangle } from 'lucide-react'
import { getRepositories, evaluateAnswer } from '../services/api'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { cn } from '../lib/utils'

interface EvalResult {
  question: string
  faithfulness: number
  answer_relevancy: number
  context_recall: number
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100)
  const color = pct >= 80 ? 'bg-green-500' : pct >= 60 ? 'bg-yellow-500' : 'bg-red-500'
  const textColor = pct >= 80 ? 'text-green-700' : pct >= 60 ? 'text-yellow-700' : 'text-red-700'
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-gray-600 font-medium">{label}</span>
        <span className={cn('font-bold', textColor)}>{pct}%</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-2">
        <div className={cn('h-2 rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function avgScore(results: EvalResult[], key: keyof EvalResult) {
  if (!results.length) return 0
  return results.reduce((s, r) => s + (r[key] as number), 0) / results.length
}

export default function EvalPage() {
  const [repoId, setRepoId] = useState('')
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [contexts, setContexts] = useState<string[]>([''])
  const [results, setResults] = useState<EvalResult[]>([])

  const { data: repos = [] } = useQuery({
    queryKey: ['repos'],
    queryFn: () => getRepositories().then((r) => r.data),
  })

  const evalMutation = useMutation({
    mutationFn: () =>
      evaluateAnswer(repoId, question, answer, contexts.filter(Boolean)).then((r) => r.data),
    onSuccess: (data) => {
      setResults((prev) => [data, ...prev])
      setQuestion(''); setAnswer(''); setContexts([''])
    },
  })

  const addContext = () => setContexts((prev) => [...prev, ''])
  const updateContext = (i: number, val: string) =>
    setContexts((prev) => prev.map((c, idx) => (idx === i ? val : c)))
  const removeContext = (i: number) =>
    setContexts((prev) => prev.filter((_, idx) => idx !== i))

  const canEval = repoId && question.trim() && answer.trim() && contexts.some(Boolean)

  return (
    <div className="p-8 max-w-4xl">
      <div className="flex items-center gap-2 mb-6">
        <FlaskConical size={22} className="text-indigo-600" />
        <h1 className="text-2xl font-bold text-gray-900">LLM Evaluation</h1>
      </div>
      <p className="text-sm text-gray-500 mb-6">
        Measure RAG answer quality using <span className="font-semibold text-gray-700">Ragas</span> metrics:
        faithfulness, answer relevancy, and context recall.
      </p>

      {/* Average scores if results exist */}
      {results.length > 0 && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          {[
            { label: 'Avg Faithfulness', key: 'faithfulness' as const },
            { label: 'Avg Answer Relevancy', key: 'answer_relevancy' as const },
            { label: 'Avg Context Recall', key: 'context_recall' as const },
          ].map(({ label, key }) => {
            const avg = avgScore(results, key)
            const pct = Math.round(avg * 100)
            const variant = pct >= 80 ? 'success' : pct >= 60 ? 'warning' : 'danger'
            return (
              <Card key={key}>
                <CardContent className="text-center py-5">
                  <p className="text-3xl font-bold text-gray-900">{pct}%</p>
                  <p className="text-xs text-gray-500 mt-1">{label}</p>
                  <Badge variant={variant} className="mt-2">
                    {pct >= 80 ? 'Good' : pct >= 60 ? 'Fair' : 'Poor'}
                  </Badge>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      {/* Eval form */}
      <Card className="mb-6">
        <CardHeader><h2 className="font-semibold text-gray-800">Run Evaluation</h2></CardHeader>
        <CardContent>
          <div className="space-y-4">
            <select
              value={repoId}
              onChange={(e) => setRepoId(e.target.value)}
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">Select repository...</option>
              {repos.filter((r: any) => r.is_indexed).map((r: any) => (
                <option key={r.id} value={r.id}>{r.full_name}</option>
              ))}
            </select>

            <div>
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1 block">Question</label>
              <input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="e.g. How does JWT authentication work?"
                className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1 block">Answer (to evaluate)</label>
              <textarea
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="Paste the AI-generated answer here..."
                rows={4}
                className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Retrieved Contexts</label>
                <button onClick={addContext} className="flex items-center gap-1 text-xs text-indigo-600 hover:underline">
                  <Plus size={12} /> Add context
                </button>
              </div>
              <div className="space-y-2">
                {contexts.map((c, i) => (
                  <div key={i} className="flex gap-2">
                    <textarea
                      value={c}
                      onChange={(e) => updateContext(i, e.target.value)}
                      placeholder={`Context snippet ${i + 1} (paste retrieved code chunk)...`}
                      rows={2}
                      className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none font-mono"
                    />
                    {contexts.length > 1 && (
                      <button onClick={() => removeContext(i)} className="text-gray-400 hover:text-red-500 transition-colors">
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <Button
              onClick={() => evalMutation.mutate()}
              disabled={!canEval}
              loading={evalMutation.isPending}
              className="w-full justify-center"
            >
              <FlaskConical size={15} />
              Evaluate Answer
            </Button>

            {evalMutation.isError && (
              <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 px-4 py-3 rounded-lg">
                <AlertTriangle size={15} />
                {(evalMutation.error as any)?.response?.data?.detail || 'Evaluation failed. Make sure ragas is installed.'}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Loading */}
      {evalMutation.isPending && (
        <div className="flex items-center gap-3 p-6 bg-white border border-gray-200 rounded-xl mb-4">
          <Loader2 className="animate-spin text-indigo-500" size={20} />
          <span className="text-gray-600 text-sm">Running Ragas evaluation (faithfulness · relevancy · recall)...</span>
        </div>
      )}

      {/* Past results */}
      {results.length > 0 && (
        <>
          <h2 className="text-lg font-semibold text-gray-800 mb-3">Evaluation History</h2>
          <div className="space-y-4">
            {results.map((r, i) => (
              <Card key={i}>
                <CardContent className="py-4">
                  <div className="flex items-start justify-between mb-4">
                    <p className="text-sm font-medium text-gray-800 flex-1 mr-4">"{r.question}"</p>
                    <CheckCircle size={16} className="text-green-500 flex-shrink-0 mt-0.5" />
                  </div>
                  <div className="space-y-3">
                    <ScoreBar label="Faithfulness" value={r.faithfulness} />
                    <ScoreBar label="Answer Relevancy" value={r.answer_relevancy} />
                    <ScoreBar label="Context Recall" value={r.context_recall} />
                  </div>
                  <div className="mt-3 pt-3 border-t border-gray-100">
                    <p className="text-xs text-gray-400">
                      Overall: <span className="font-semibold text-gray-600">
                        {Math.round(((r.faithfulness + r.answer_relevancy + r.context_recall) / 3) * 100)}%
                      </span>
                    </p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
