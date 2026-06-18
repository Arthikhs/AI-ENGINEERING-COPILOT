import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { TestTube, Loader2, Copy, Check } from 'lucide-react'
import { getRepositories, generateTests } from '../services/api'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

const LANG_OPTIONS = ['Auto-detect', 'Python', 'Java', 'JavaScript', 'TypeScript']

const EXAMPLES = [
  'AuthService login method',
  'UserRepository findById',
  'PaymentService processPayment',
  'JwtUtils generateToken',
]

export default function TestGenerationPage() {
  const [repoId, setRepoId] = useState('')
  const [target, setTarget] = useState('')
  const [language, setLanguage] = useState('Auto-detect')
  const [result, setResult] = useState<any>(null)
  const [copied, setCopied] = useState(false)

  const { data: repos = [] } = useQuery({
    queryKey: ['repos'],
    queryFn: () => getRepositories().then(r => r.data),
  })

  const mutation = useMutation({
    mutationFn: () =>
      generateTests(repoId, target, language === 'Auto-detect' ? undefined : language).then(r => r.data),
    onSuccess: data => setResult(data),
  })

  const handleCopy = () => {
    if (result?.test_code) {
      navigator.clipboard.writeText(result.test_code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const langForHighlight = (l: string) =>
    ({ Python: 'python', Java: 'java', JavaScript: 'javascript', TypeScript: 'typescript' }[l] ?? 'python')

  return (
    <div className="p-8 max-w-4xl">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 bg-green-100 rounded-xl"><TestTube size={22} className="text-green-600" /></div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Test Generation Agent</h1>
          <p className="text-sm text-gray-500">pytest · JUnit + Mockito · Jest · TypeScript Jest</p>
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
            <select
              value={language}
              onChange={e => setLanguage(e.target.value)}
              className="w-40 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {LANG_OPTIONS.map(l => <option key={l}>{l}</option>)}
            </select>
          </div>
          <div className="flex gap-3">
            <input
              value={target}
              onChange={e => setTarget(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && target && repoId && mutation.mutate()}
              placeholder="Function or class to test (e.g. AuthService login method)"
              className="flex-1 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <Button onClick={() => mutation.mutate()} disabled={!repoId || !target} loading={mutation.isPending}>
              Generate Tests
            </Button>
          </div>
          {/* Examples */}
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map(ex => (
              <button
                key={ex}
                onClick={() => setTarget(ex)}
                className="text-xs px-3 py-1.5 bg-gray-50 border border-gray-200 rounded-lg text-gray-600 hover:bg-green-50 hover:border-green-300 transition-colors"
              >
                {ex}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {mutation.isPending && (
        <div className="flex items-center gap-3 p-6 bg-white border border-gray-200 rounded-xl mb-4">
          <Loader2 className="animate-spin text-green-500" size={20} />
          <span className="text-gray-600">Finding source code and generating tests...</span>
        </div>
      )}

      {result && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <h2 className="font-semibold text-gray-800">Generated Tests</h2>
                <Badge variant="success">{result.language}</Badge>
                <Badge variant="info">{result.test_filename}</Badge>
              </div>
              <Button size="sm" variant="secondary" onClick={handleCopy}>
                {copied ? <><Check size={13} /> Copied!</> : <><Copy size={13} /> Copy</>}
              </Button>
            </div>
            {result.source_file && (
              <p className="text-xs text-gray-400 mt-1">Source: {result.source_file}</p>
            )}
          </CardHeader>
          <CardContent>
            <SyntaxHighlighter
              style={oneDark}
              language={langForHighlight(result.language)}
              PreTag="div"
              className="!text-xs !rounded-xl"
            >
              {result.test_code || '// No tests generated'}
            </SyntaxHighlighter>

            {result.chunks_used?.length > 0 && (
              <div className="mt-3 pt-3 border-t border-gray-100">
                <p className="text-xs font-semibold text-gray-500 mb-1">SOURCE FILES USED</p>
                <div className="flex flex-wrap gap-1.5">
                  {result.chunks_used.map((c: any, i: number) => (
                    <span key={i} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                      {c.file_path}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
