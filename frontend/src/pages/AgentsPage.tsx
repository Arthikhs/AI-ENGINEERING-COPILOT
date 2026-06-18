import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  Wrench, FlaskConical, Shapes, BookOpen, Loader2, FileCode, ChevronRight,
} from 'lucide-react'
import {
  getRepositories, refactorAnalyze, generateTests,
  generateSystemDesign, generateDocumentation,
} from '../services/api'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { cn } from '../lib/utils'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

type Tab = 'refactor' | 'tests' | 'design' | 'docs'

const TABS: { id: Tab; label: string; icon: any }[] = [
  { id: 'refactor', label: 'Refactoring',     icon: Wrench },
  { id: 'tests',    label: 'Test Generation', icon: FlaskConical },
  { id: 'design',   label: 'System Design',   icon: Shapes },
  { id: 'docs',     label: 'Documentation',   icon: BookOpen },
]

const SEV: Record<string, any> = { HIGH: 'danger', MEDIUM: 'warning', LOW: 'info' }

function LoadingCard({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-3 p-6 bg-white border border-gray-200 rounded-xl">
      <Loader2 className="animate-spin text-indigo-500 flex-shrink-0" size={20} />
      <span className="text-gray-600 text-sm">{text}</span>
    </div>
  )
}

export default function AgentsPage() {
  const [tab, setTab] = useState<Tab>('refactor')
  const [repoId, setRepoId] = useState('')

  // Refactor
  const [targetFile, setTargetFile] = useState('')
  const [refactorResult, setRefactorResult] = useState<any>(null)

  // Test gen
  const [testTarget, setTestTarget] = useState('')
  const [testLang, setTestLang] = useState('')
  const [testResult, setTestResult] = useState<any>(null)

  // System design
  const [designQuery, setDesignQuery] = useState('')
  const [designResult, setDesignResult] = useState<any>(null)
  const [diagramMode, setDiagramMode] = useState<'mermaid' | 'plantuml'>('mermaid')

  // Docs
  const [docTarget, setDocTarget] = useState('')
  const [docResult, setDocResult] = useState<any>(null)
  const [docTab, setDocTab] = useState<'readme' | 'api' | 'diagram'>('readme')

  const { data: repos = [] } = useQuery({
    queryKey: ['repos'],
    queryFn: () => getRepositories().then((r) => r.data),
  })

  const clearResults = (repoVal: string) => {
    setRepoId(repoVal)
    setRefactorResult(null); setTestResult(null)
    setDesignResult(null);   setDocResult(null)
  }

  const refactorMutation = useMutation({
    mutationFn: () => refactorAnalyze(repoId, targetFile || undefined).then((r) => r.data),
    onSuccess: setRefactorResult,
  })
  const testMutation = useMutation({
    mutationFn: () => generateTests(repoId, testTarget, testLang || undefined).then((r) => r.data),
    onSuccess: setTestResult,
  })
  const designMutation = useMutation({
    mutationFn: () => generateSystemDesign(repoId, designQuery).then((r) => r.data),
    onSuccess: setDesignResult,
  })
  const docMutation = useMutation({
    mutationFn: () => generateDocumentation(repoId, docTarget || undefined).then((r) => r.data),
    onSuccess: setDocResult,
  })

  const RepoSelector = () => (
    <select
      value={repoId}
      onChange={(e) => clearResults(e.target.value)}
      className="flex-1 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
    >
      <option value="">Select an indexed repository...</option>
      {repos.filter((r: any) => r.is_indexed).map((r: any) => (
        <option key={r.id} value={r.id}>{r.full_name}</option>
      ))}
    </select>
  )

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-center gap-2 mb-6">
        <Wrench size={22} className="text-indigo-600" />
        <h1 className="text-2xl font-bold text-gray-900">AI Code Agents</h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-xl w-fit">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
              tab === id ? 'bg-white text-indigo-700 shadow-sm' : 'text-gray-500 hover:text-gray-800'
            )}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>

      {/* ── REFACTOR TAB ── */}
      {tab === 'refactor' && (
        <div className="space-y-4">
          <Card>
            <CardHeader><h2 className="font-semibold text-gray-800">Detect Code Smells & Suggest Refactoring</h2></CardHeader>
            <CardContent>
              <p className="text-sm text-gray-500 mb-3">
                Finds large classes, long methods, duplicate code, dead code, magic numbers, and more.
              </p>
              <div className="flex gap-3 mb-3"><RepoSelector /></div>
              <div className="flex gap-3">
                <input
                  value={targetFile}
                  onChange={(e) => setTargetFile(e.target.value)}
                  placeholder="Optional: filter by file path (e.g. auth/service.py)"
                  className="flex-1 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <Button onClick={() => refactorMutation.mutate()} disabled={!repoId} loading={refactorMutation.isPending}>
                  Analyze
                </Button>
              </div>
            </CardContent>
          </Card>

          {refactorMutation.isPending && <LoadingCard text="Detecting code smells and generating refactoring suggestions..." />}

          {refactorResult && (
            <>
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <h2 className="font-semibold text-gray-800">Suggestions ({refactorResult.suggestions?.length ?? 0})</h2>
                    <span className="text-xs text-gray-400">{refactorResult.files_analyzed} files analyzed</span>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {refactorResult.suggestions?.map((s: any, i: number) => (
                      <details key={i} className="border border-gray-200 rounded-xl">
                        <summary className="flex items-center justify-between px-4 py-3 cursor-pointer select-none">
                          <div className="flex items-center gap-2">
                            <ChevronRight size={14} className="text-gray-400" />
                            <span className="text-sm font-semibold text-gray-800">{s.issue}</span>
                            {s.location && <span className="text-xs text-gray-500 font-mono">— {s.location}</span>}
                          </div>
                          <Badge variant={SEV[s.severity] ?? 'default'}>{s.severity}</Badge>
                        </summary>
                        <div className="px-4 pb-4 space-y-3 border-t border-gray-100 pt-3">
                          {s.file && <div className="flex items-center gap-1 text-xs text-gray-500"><FileCode size={11} /><span className="font-mono">{s.file}</span></div>}
                          {s.description && <p className="text-sm text-gray-700">{s.description}</p>}
                          {s.before && (
                            <div>
                              <p className="text-xs font-semibold text-red-600 mb-1">Before</p>
                              <pre className="text-xs bg-red-50 border border-red-100 rounded-lg p-3 overflow-x-auto font-mono">{s.before}</pre>
                            </div>
                          )}
                          {s.after && (
                            <div>
                              <p className="text-xs font-semibold text-green-600 mb-1">After</p>
                              <pre className="text-xs bg-green-50 border border-green-100 rounded-lg p-3 overflow-x-auto font-mono">{s.after}</pre>
                            </div>
                          )}
                          {s.benefit && <p className="text-xs text-indigo-700 bg-indigo-50 px-3 py-2 rounded-lg"><span className="font-medium">Benefit:</span> {s.benefit}</p>}
                        </div>
                      </details>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {refactorResult.refactoring_plan?.length > 0 && (
                <Card>
                  <CardHeader><h2 className="font-semibold text-gray-800">Refactoring Plan</h2></CardHeader>
                  <CardContent>
                    <ol className="space-y-2">
                      {refactorResult.refactoring_plan.map((step: string, i: number) => (
                        <li key={i} className="flex items-start gap-3 text-sm text-gray-700">
                          <span className="flex-shrink-0 w-6 h-6 bg-indigo-100 text-indigo-700 rounded-full text-xs flex items-center justify-center font-bold">{i + 1}</span>
                          {step}
                        </li>
                      ))}
                    </ol>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </div>
      )}

      {/* ── TEST GENERATION TAB ── */}
      {tab === 'tests' && (
        <div className="space-y-4">
          <Card>
            <CardHeader><h2 className="font-semibold text-gray-800">Generate Unit Tests</h2></CardHeader>
            <CardContent>
              <p className="text-sm text-gray-500 mb-3">Generates pytest, JUnit 5, or Jest tests for any function, class, or module.</p>
              <div className="flex gap-3 mb-3">
                <RepoSelector />
                <select value={testLang} onChange={(e) => setTestLang(e.target.value)}
                  className="w-40 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                  <option value="">Auto-detect</option>
                  <option value="Python">Python</option>
                  <option value="Java">Java</option>
                  <option value="JavaScript">JavaScript</option>
                  <option value="TypeScript">TypeScript</option>
                </select>
              </div>
              <div className="flex gap-3">
                <input value={testTarget} onChange={(e) => setTestTarget(e.target.value)}
                  placeholder="Function or class to test (e.g. AuthService, login())"
                  className="flex-1 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                <Button onClick={() => testMutation.mutate()} disabled={!repoId || !testTarget} loading={testMutation.isPending}>
                  Generate Tests
                </Button>
              </div>
            </CardContent>
          </Card>

          {testMutation.isPending && <LoadingCard text="Generating comprehensive unit tests..." />}

          {testResult && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="font-semibold text-gray-800">{testResult.test_filename}</h2>
                    <p className="text-xs text-gray-500 mt-0.5">Source: <span className="font-mono">{testResult.source_file}</span></p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="info">{testResult.language}</Badge>
                    <button onClick={() => navigator.clipboard.writeText(testResult.test_code)} className="text-xs text-indigo-600 hover:underline">Copy</button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <SyntaxHighlighter style={oneDark}
                  language={testResult.language?.toLowerCase() === 'python' ? 'python' : testResult.language?.toLowerCase() === 'java' ? 'java' : 'typescript'}
                  customStyle={{ borderRadius: '0.75rem', fontSize: '0.75rem', maxHeight: '500px' }}>
                  {testResult.test_code}
                </SyntaxHighlighter>
                {testResult.chunks_used?.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    <span className="text-xs text-gray-500">Based on:</span>
                    {testResult.chunks_used.map((c: any, i: number) => (
                      <div key={i} className="flex items-center gap-1 text-xs text-gray-500 bg-gray-50 border border-gray-200 px-2 py-0.5 rounded">
                        <FileCode size={10} />{c.file_path.split('/').slice(-1)[0]}
                        {c.chunk_name && <span className="text-gray-400">:{c.chunk_name}</span>}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* ── SYSTEM DESIGN TAB ── */}
      {tab === 'design' && (
        <div className="space-y-4">
          <Card>
            <CardHeader><h2 className="font-semibold text-gray-800">Generate Architecture Diagram</h2></CardHeader>
            <CardContent>
              <p className="text-sm text-gray-500 mb-3">Ask about any flow and get Mermaid + PlantUML diagrams generated from your actual code.</p>
              <div className="flex gap-3 mb-3"><RepoSelector /></div>
              <div className="flex gap-3">
                <input value={designQuery} onChange={(e) => setDesignQuery(e.target.value)}
                  placeholder="e.g. Explain the order processing flow, How does auth work?"
                  className="flex-1 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                <Button onClick={() => designMutation.mutate()} disabled={!repoId || !designQuery} loading={designMutation.isPending}>
                  Generate
                </Button>
              </div>
            </CardContent>
          </Card>

          {designMutation.isPending && <LoadingCard text="Analyzing codebase and generating architecture diagram..." />}

          {designResult && (
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <h2 className="font-semibold text-gray-800">Diagram</h2>
                    <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
                      {(['mermaid', 'plantuml'] as const).map((m) => (
                        <button key={m} onClick={() => setDiagramMode(m)}
                          className={cn('px-3 py-1 rounded-md text-xs font-medium transition-colors',
                            diagramMode === m ? 'bg-white text-indigo-700 shadow-sm' : 'text-gray-500')}>
                          {m === 'mermaid' ? 'Mermaid' : 'PlantUML'}
                        </button>
                      ))}
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  {diagramMode === 'mermaid' && designResult.mermaid ? (
                    <div>
                      <div className="flex justify-end mb-2">
                        <button onClick={() => navigator.clipboard.writeText('```mermaid\n' + designResult.mermaid + '\n```')} className="text-xs text-indigo-600 hover:underline">Copy</button>
                      </div>
                      <pre className="bg-gray-900 text-green-300 rounded-xl p-4 text-xs font-mono overflow-x-auto">{designResult.mermaid}</pre>
                    </div>
                  ) : diagramMode === 'plantuml' && designResult.plantuml ? (
                    <div>
                      <div className="flex justify-end mb-2">
                        <button onClick={() => navigator.clipboard.writeText(designResult.plantuml)} className="text-xs text-indigo-600 hover:underline">Copy</button>
                      </div>
                      <pre className="bg-gray-900 text-blue-300 rounded-xl p-4 text-xs font-mono overflow-x-auto">{designResult.plantuml}</pre>
                    </div>
                  ) : (
                    <p className="text-sm text-gray-400">No diagram generated for this format.</p>
                  )}
                </CardContent>
              </Card>

              {designResult.explanation && (
                <Card>
                  <CardHeader><h2 className="font-semibold text-gray-800">Explanation</h2></CardHeader>
                  <CardContent><p className="text-sm text-gray-700 leading-relaxed">{designResult.explanation}</p></CardContent>
                </Card>
              )}

              {designResult.components?.length > 0 && (
                <Card>
                  <CardHeader><h2 className="font-semibold text-gray-800">Components Identified</h2></CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-2">
                      {designResult.components.map((c: string) => <Badge key={c} variant="info">{c}</Badge>)}
                    </div>
                  </CardContent>
                </Card>
              )}

              {designResult.sources?.length > 0 && (
                <Card>
                  <CardHeader><h2 className="font-semibold text-gray-800 text-sm">Code Sources</h2></CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-1.5">
                      {designResult.sources.map((s: any, i: number) => (
                        <div key={i} className="flex items-center gap-1 text-xs text-gray-500 bg-gray-50 border border-gray-200 px-2 py-1 rounded-lg">
                          <FileCode size={10} />{s.file_path.split('/').slice(-2).join('/')}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── DOCUMENTATION TAB ── */}
      {tab === 'docs' && (
        <div className="space-y-4">
          <Card>
            <CardHeader><h2 className="font-semibold text-gray-800">Generate Documentation</h2></CardHeader>
            <CardContent>
              <p className="text-sm text-gray-500 mb-3">Generates README, API docs, and sequence diagrams from your source code.</p>
              <div className="flex gap-3 mb-3"><RepoSelector /></div>
              <div className="flex gap-3">
                <input value={docTarget} onChange={(e) => setDocTarget(e.target.value)}
                  placeholder="Optional: specific service/class to document (e.g. AuthService)"
                  className="flex-1 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                <Button onClick={() => docMutation.mutate()} disabled={!repoId} loading={docMutation.isPending}>
                  Generate Docs
                </Button>
              </div>
            </CardContent>
          </Card>

          {docMutation.isPending && <LoadingCard text="Generating documentation from source code..." />}

          {docResult && (
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <h2 className="font-semibold text-gray-800">Generated Documentation</h2>
                    <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
                      {(['readme', 'api', 'diagram'] as const).map((t) => (
                        <button key={t} onClick={() => setDocTab(t)}
                          className={cn('px-3 py-1 rounded-md text-xs font-medium transition-colors',
                            docTab === t ? 'bg-white text-indigo-700 shadow-sm' : 'text-gray-500')}>
                          {t === 'readme' ? 'README' : t === 'api' ? 'API Docs' : 'Diagram'}
                        </button>
                      ))}
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  {docTab === 'readme' && (
                    <div>
                      <div className="flex justify-end mb-2">
                        <button onClick={() => navigator.clipboard.writeText(docResult.readme ?? '')} className="text-xs text-indigo-600 hover:underline">Copy</button>
                      </div>
                      <pre className="text-xs bg-gray-50 border border-gray-200 rounded-xl p-4 overflow-x-auto font-mono whitespace-pre-wrap">{docResult.readme || 'No README generated.'}</pre>
                    </div>
                  )}
                  {docTab === 'api' && (
                    <div>
                      <div className="flex justify-end mb-2">
                        <button onClick={() => navigator.clipboard.writeText(docResult.api_docs ?? '')} className="text-xs text-indigo-600 hover:underline">Copy</button>
                      </div>
                      <pre className="text-xs bg-gray-50 border border-gray-200 rounded-xl p-4 overflow-x-auto font-mono whitespace-pre-wrap">{docResult.api_docs || 'No API docs generated.'}</pre>
                    </div>
                  )}
                  {docTab === 'diagram' && (
                    docResult.sequence_diagram ? (
                      <div>
                        <div className="flex justify-end mb-2">
                          <button onClick={() => navigator.clipboard.writeText('```mermaid\n' + docResult.sequence_diagram + '\n```')} className="text-xs text-indigo-600 hover:underline">Copy</button>
                        </div>
                        <pre className="bg-gray-900 text-green-300 rounded-xl p-4 text-xs font-mono overflow-x-auto">{docResult.sequence_diagram}</pre>
                      </div>
                    ) : (
                      <p className="text-sm text-gray-400">No sequence diagram generated.</p>
                    )
                  )}
                </CardContent>
              </Card>

              {docResult.summary && (
                <Card>
                  <CardHeader><h2 className="font-semibold text-gray-800">Summary</h2></CardHeader>
                  <CardContent>
                    <p className="text-sm text-gray-700 leading-relaxed">{docResult.summary}</p>
                    <p className="text-xs text-gray-400 mt-2">{docResult.files_documented} files documented</p>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
