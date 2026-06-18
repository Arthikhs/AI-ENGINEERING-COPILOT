import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Search, FileCode, Loader2 } from 'lucide-react'
import { getRepositories, semanticSearch } from '../services/api'
import { Card, CardContent } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

const EXAMPLES = [
  'Find JWT validation logic',
  'Find Kafka producers',
  'Find Redis cache usage',
  'Find database connection setup',
  'Find authentication middleware',
  'Find API rate limiting',
]

const SOURCE_BADGE: Record<string, string> = {
  hybrid: 'bg-indigo-100 text-indigo-700',
  vector: 'bg-blue-100 text-blue-700',
  bm25:   'bg-green-100 text-green-700',
}

export default function SemanticSearchPage() {
  const [repoId, setRepoId]       = useState('')
  const [query, setQuery]         = useState('')
  const [langFilter, setLangFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [results, setResults]     = useState<any[]>([])

  const { data: repos = [] } = useQuery({
    queryKey: ['repos'],
    queryFn: () => getRepositories().then(r => r.data),
  })

  const searchMutation = useMutation({
    mutationFn: (q: string) =>
      semanticSearch(repoId, q, 10, langFilter || undefined, typeFilter || undefined).then(r => r.data),
    onSuccess: data => setResults(data.results ?? []),
  })

  const handleSearch = (q?: string) => {
    const text = q ?? query
    if (!text.trim() || !repoId) return
    if (q) setQuery(q)
    searchMutation.mutate(text)
  }

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 bg-blue-100 rounded-xl"><Search size={22} className="text-blue-600" /></div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Semantic Code Search</h1>
          <p className="text-sm text-gray-500">Hybrid BM25 + Vector + Reranker · Google-like code search</p>
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
              <option value="">Select repository...</option>
              {repos.filter((r: any) => r.is_indexed).map((r: any) => (
                <option key={r.id} value={r.id}>{r.full_name}</option>
              ))}
            </select>
            <select
              value={langFilter}
              onChange={e => setLangFilter(e.target.value)}
              className="w-36 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">All languages</option>
              {['Python','JavaScript','TypeScript','Java','Go','Ruby'].map(l => (
                <option key={l}>{l}</option>
              ))}
            </select>
            <select
              value={typeFilter}
              onChange={e => setTypeFilter(e.target.value)}
              className="w-36 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">All types</option>
              {['function','class','module','block'].map(t => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </div>

          <div className="flex gap-3">
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              placeholder="Search your codebase semantically..."
              className="flex-1 px-4 py-3 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <Button onClick={() => handleSearch()} disabled={!query.trim() || !repoId} loading={searchMutation.isPending}>
              <Search size={15} /> Search
            </Button>
          </div>

          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map(ex => (
              <button
                key={ex}
                onClick={() => handleSearch(ex)}
                className="text-xs px-3 py-1.5 bg-gray-50 border border-gray-200 rounded-lg text-gray-600 hover:bg-blue-50 hover:border-blue-300 transition-colors"
              >
                {ex}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {searchMutation.isPending && (
        <div className="flex items-center gap-3 p-5 bg-white border border-gray-200 rounded-xl mb-4">
          <Loader2 className="animate-spin text-blue-500" size={20} />
          <span className="text-gray-600">Running BM25 + Vector search + Reranking...</span>
        </div>
      )}

      {results.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-semibold text-gray-800">{results.length} Results</h2>
            <div className="flex gap-2 text-xs items-center">
              {(['hybrid','vector','bm25'] as const).map(s => (
                <span key={s} className={`px-2 py-0.5 rounded-full font-medium ${SOURCE_BADGE[s]}`}>{s}</span>
              ))}
              <span className="text-gray-400">= retrieval source</span>
            </div>
          </div>

          {results.map((r: any, i: number) => {
            const score  = r.rerank_score ?? r.score ?? 0
            const source = r.retrieval_source ?? 'hybrid'
            return (
              <Card key={i}>
                <CardContent className="pt-3 pb-3">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <FileCode size={14} className="text-gray-400" />
                      <span className="text-sm font-semibold text-indigo-700">{r.file_path}</span>
                      {r.chunk_name && <span className="text-xs text-gray-500">→ {r.chunk_name}</span>}
                      {r.language   && <Badge variant="info">{r.language}</Badge>}
                      {r.chunk_type && <Badge variant="default">{r.chunk_type}</Badge>}
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${SOURCE_BADGE[source] ?? SOURCE_BADGE.hybrid}`}>
                        {source}
                      </span>
                      <span className="text-xs text-gray-400">{(score * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                  <SyntaxHighlighter
                    style={oneDark}
                    language={(r.language || '').toLowerCase()}
                    PreTag="div"
                    className="!text-xs !rounded-lg !mt-0"
                  >
                    {r.content?.slice(0, 400) + (r.content?.length > 400 ? '\n...' : '')}
                  </SyntaxHighlighter>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      {results.length === 0 && searchMutation.isSuccess && (
        <div className="text-center py-12 text-gray-400">
          <Search size={36} className="mx-auto mb-3 opacity-20" />
          <p>No results found. Try a different query.</p>
        </div>
      )}
    </div>
  )
}
