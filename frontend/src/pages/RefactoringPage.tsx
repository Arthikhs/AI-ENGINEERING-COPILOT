import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Wrench, Loader2, ChevronDown, ChevronUp } from 'lucide-react'
import { getRepositories, analyzeRefactoring } from '../services/api'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

const SEV_COLOR: Record<string, string> = {
  high:   'bg-red-100 text-red-700',
  medium: 'bg-yellow-100 text-yellow-700',
  low:    'bg-blue-100 text-blue-700',
}

function SuggestionCard({ s }: { s: any }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-white hover:bg-gray-50 text-left"
      >
        <div className="flex items-center gap-3">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${SEV_COLOR[s.severity?.toLowerCase()] ?? SEV_COLOR.low}`}>
            {s.severity}
          </span>
          <span className="font-medium text-gray-800 text-sm">{s.issue}</span>
          {s.location && <span className="text-xs text-gray-400">· {s.location}</span>}
        </div>
        {open ? <ChevronUp size={15} className="text-gray-400" /> : <ChevronDown size={15} className="text-gray-400" />}
      </button>

      {open && (
        <div className="px-4 pb-4 bg-gray-50 space-y-3 border-t border-gray-100">
          {s.file && <p className="text-xs text-gray-500 pt-2">📁 {s.file}</p>}
          {s.description && <p className="text-sm text-gray-700">{s.description}</p>}
          {s.before && (
            <div>
              <p className="text-xs font-semibold text-red-600 mb-1">❌ Before</p>
              <SyntaxHighlighter style={oneDark} language="python" PreTag="div" className="!text-xs !rounded-lg">
                {s.before}
              </SyntaxHighlighter>
            </div>
          )}
          {s.after && (
            <div>
              <p className="text-xs font-semibold text-green-600 mb-1">✅ After</p>
              <SyntaxHighlighter style={oneDark} language="python" PreTag="div" className="!text-xs !rounded-lg">
                {s.after}
              </SyntaxHighlighter>
            </div>
          )}
          {s.benefit && <p className="text-xs text-indigo-700 bg-indigo-50 px-3 py-2 rounded-lg">💡 {s.benefit}</p>}
        </div>
      )}
    </div>
  )
}

export default function RefactoringPage() {
  const [repoId, setRepoId] = useState('')
  const [targetFile, setTargetFile] = useState('')
  const [result, setResult] = useState<any>(null)

  const { data: repos = [] } = useQuery({
    queryKey: ['repos'],
    queryFn: () => getRepositories().then(r => r.data),
  })

  const mutation = useMutation({
    mutationFn: () => analyzeRefactoring(repoId, targetFile || undefined).then(r => r.data),
    onSuccess: data => setResult(data),
  })

  return (
    <div className="p-8 max-w-4xl">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 bg-orange-100 rounded-xl"><Wrench size={22} className="text-orange-600" /></div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Refactoring Agent</h1>
          <p className="text-sm text-gray-500">Detects code smells · Generates before/after suggestions</p>
        </div>
      </div>

      <Card className="mb-6">
        <CardContent className="pt-4 space-y-3">
          <div className="flex gap-3">
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
            <Button onClick={() => mutation.mutate()} disabled={!repoId} loading={mutation.isPending}>
              Analyze
            </Button>
          </div>
          <input
            value={targetFile}
            onChange={e => setTargetFile(e.target.value)}
            placeholder="Optional: focus on specific file path (e.g. src/services/user.py)"
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </CardContent>
      </Card>

      {mutation.isPending && (
        <div className="flex items-center gap-3 p-6 bg-white border border-gray-200 rounded-xl mb-4">
          <Loader2 className="animate-spin text-orange-500" size={20} />
          <span className="text-gray-600">Detecting code smells and generating refactoring suggestions...</span>
        </div>
      )}

      {result && (
        <div className="space-y-4">
          {/* Stats */}
          <div className="flex gap-4">
            <div className="bg-white border border-gray-200 rounded-xl px-5 py-3 text-center">
              <p className="text-2xl font-bold text-orange-600">{result.suggestions?.length ?? 0}</p>
              <p className="text-xs text-gray-500">Issues Found</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl px-5 py-3 text-center">
              <p className="text-2xl font-bold text-gray-800">{result.files_analyzed ?? 0}</p>
              <p className="text-xs text-gray-500">Files Analyzed</p>
            </div>
          </div>

          {/* Refactoring Plan */}
          {result.refactoring_plan?.length > 0 && (
            <Card>
              <CardHeader><h2 className="font-semibold text-gray-800">📋 Refactoring Plan</h2></CardHeader>
              <CardContent>
                <ol className="space-y-1">
                  {result.refactoring_plan.map((step: string, i: number) => (
                    <li key={i} className="text-sm text-gray-700 flex gap-2">
                      <span className="text-indigo-500 font-bold">{i + 1}.</span>
                      {step}
                    </li>
                  ))}
                </ol>
              </CardContent>
            </Card>
          )}

          {/* Suggestions */}
          {result.suggestions?.length > 0 && (
            <div className="space-y-2">
              <h2 className="font-semibold text-gray-800 mb-2">Suggestions</h2>
              {result.suggestions.map((s: any, i: number) => (
                <SuggestionCard key={i} s={s} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
