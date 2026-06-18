import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Cpu, Loader2, Copy, Check, FileCode } from 'lucide-react'
import { getRepositories, generateSystemDesign } from '../services/api'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'

const EXAMPLES = [
  'Explain the user authentication flow',
  'Show the order processing pipeline',
  'Explain how payment is processed',
  'Show the data ingestion flow',
  'Explain the notification system',
]

export default function SystemDesignPage() {
  const [repoId, setRepoId]   = useState('')
  const [query, setQuery]     = useState('')
  const [result, setResult]   = useState<any>(null)
  const [copiedMermaid, setCopiedMermaid] = useState(false)
  const [copiedPlant, setCopiedPlant]     = useState(false)
  const [tab, setTab]         = useState<'mermaid' | 'plantuml' | 'explanation'>('mermaid')

  const { data: repos = [] } = useQuery({
    queryKey: ['repos'],
    queryFn: () => getRepositories().then(r => r.data),
  })

  const mutation = useMutation({
    mutationFn: (q: string) => generateSystemDesign(repoId, q).then(r => r.data),
    onSuccess: data => { setResult(data); setTab('mermaid') },
  })

  const handleGenerate = (q?: string) => {
    const text = q ?? query
    if (!text.trim() || !repoId) return
    if (q) setQuery(q)
    mutation.mutate(text)
  }

  const copy = (text: string, which: 'mermaid' | 'plant') => {
    navigator.clipboard.writeText(text)
    if (which === 'mermaid') { setCopiedMermaid(true); setTimeout(() => setCopiedMermaid(false), 2000) }
    else                     { setCopiedPlant(true);   setTimeout(() => setCopiedPlant(false),   2000) }
  }

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 bg-purple-100 rounded-xl"><Cpu size={22} className="text-purple-600" /></div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">System Design Generator</h1>
          <p className="text-sm text-gray-500">Generates Mermaid + PlantUML diagrams from your codebase</p>
        </div>
      </div>

      <Card className="mb-6">
        <CardContent className="pt-4 space-y-3">
          <select
            value={repoId}
            onChange={e => setRepoId(e.target.value)}
            className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">Select indexed repository...</option>
            {repos.filter((r: any) => r.is_indexed).map((r: any) => (
              <option key={r.id} value={r.id}>{r.full_name}</option>
            ))}
          </select>

          <div className="flex gap-3">
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleGenerate()}
              placeholder="e.g. Explain the order processing flow"
              className="flex-1 px-4 py-3 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <Button onClick={() => handleGenerate()} disabled={!query.trim() || !repoId} loading={mutation.isPending}>
              <Cpu size={15} /> Generate
            </Button>
          </div>

          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map(ex => (
              <button
                key={ex}
                onClick={() => handleGenerate(ex)}
                className="text-xs px-3 py-1.5 bg-gray-50 border border-gray-200 rounded-lg text-gray-600 hover:bg-purple-50 hover:border-purple-300 transition-colors"
              >
                {ex}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {mutation.isPending && (
        <div className="flex items-center gap-3 p-6 bg-white border border-gray-200 rounded-xl mb-4">
          <Loader2 className="animate-spin text-purple-500" size={20} />
          <span className="text-gray-600">Analyzing codebase and generating architecture diagrams...</span>
        </div>
      )}

      {result && (
        <div className="space-y-4">
          {/* Components */}
          {result.components?.length > 0 && (
            <div className="flex flex-wrap gap-2 items-center">
              <span className="text-xs font-semibold text-gray-500 uppercase">Components:</span>
              {result.components.map((c: string) => (
                <Badge key={c} variant="info">{c}</Badge>
              ))}
            </div>
          )}

          {/* Tab switcher */}
          <div className="flex gap-1 bg-gray-100 p-1 rounded-xl w-fit">
            {(['mermaid','plantuml','explanation'] as const).map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors capitalize ${
                  tab === t ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {t === 'mermaid' ? '🗺 Mermaid' : t === 'plantuml' ? '📐 PlantUML' : '📝 Explanation'}
              </button>
            ))}
          </div>

          {/* Mermaid */}
          {tab === 'mermaid' && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <h2 className="font-semibold text-gray-800">Mermaid Diagram</h2>
                  <div className="flex gap-2">
                    <Button size="sm" variant="secondary" onClick={() => copy(result.mermaid, 'mermaid')}>
                      {copiedMermaid ? <><Check size={13} /> Copied!</> : <><Copy size={13} /> Copy</>}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {result.mermaid ? (
                  <pre className="bg-gray-950 text-green-400 text-xs p-4 rounded-xl overflow-x-auto font-mono">
                    {`\`\`\`mermaid\n${result.mermaid}\n\`\`\``}
                  </pre>
                ) : (
                  <p className="text-gray-400 text-sm">No Mermaid diagram generated.</p>
                )}
                <p className="text-xs text-gray-400 mt-2">
                  💡 Paste into <a href="https://mermaid.live" target="_blank" rel="noreferrer" className="text-indigo-500 underline">mermaid.live</a> to visualize
                </p>
              </CardContent>
            </Card>
          )}

          {/* PlantUML */}
          {tab === 'plantuml' && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <h2 className="font-semibold text-gray-800">PlantUML Diagram</h2>
                  <Button size="sm" variant="secondary" onClick={() => copy(result.plantuml, 'plant')}>
                    {copiedPlant ? <><Check size={13} /> Copied!</> : <><Copy size={13} /> Copy</>}
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {result.plantuml ? (
                  <pre className="bg-gray-950 text-blue-300 text-xs p-4 rounded-xl overflow-x-auto font-mono">
                    {result.plantuml}
                  </pre>
                ) : (
                  <p className="text-gray-400 text-sm">No PlantUML diagram generated.</p>
                )}
                <p className="text-xs text-gray-400 mt-2">
                  💡 Paste into <a href="https://www.plantuml.com/plantuml/uml/" target="_blank" rel="noreferrer" className="text-indigo-500 underline">plantuml.com</a> to render
                </p>
              </CardContent>
            </Card>
          )}

          {/* Explanation */}
          {tab === 'explanation' && (
            <Card>
              <CardHeader><h2 className="font-semibold text-gray-800">Architecture Explanation</h2></CardHeader>
              <CardContent>
                <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                  {result.explanation || 'No explanation generated.'}
                </p>
              </CardContent>
            </Card>
          )}

          {/* Sources */}
          {result.sources?.length > 0 && (
            <div className="mt-2">
              <p className="text-xs font-semibold text-gray-500 mb-2">SOURCE FILES</p>
              <div className="flex flex-wrap gap-1.5">
                {result.sources.map((s: any, i: number) => (
                  <div key={i} className="flex items-center gap-1 text-xs bg-gray-50 border border-gray-200 px-2 py-1 rounded-lg text-gray-500">
                    <FileCode size={11} />
                    {s.file_path}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
