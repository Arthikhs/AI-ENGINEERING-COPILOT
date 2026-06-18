import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Search, FileCode, Loader2, Filter } from 'lucide-react'
import { getRepositories, semanticSearch } from '../services/api'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'

const EXAMPLE_QUERIES = [
  'JWT authentication validation',
  'Redis cache usage',
  'Kafka producer publish event',
  'SQL query database interaction',
  'HTTP request external API call',
]

const LANGUAGES = ['', 'Python', 'JavaScript', 'TypeScript', 'Java', 'Go', 'Ruby']
const CHUNK_TYPES = ['', 'function', 'class', 'module']

export default function SearchPage() {
  const [repoId, setRepoId] = useState('')
  const [query, setQuery] = useState('')
  const [language, setLanguage] = useState('')
  const [chunkType, setChunkType] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const [results, setResults] = useState<any>(null)

  const { data: repos = [] } = useQuery({
    queryKey: ['repos'],
    queryFn: () => getRepositories().then((r) => r.data),
  })

  const searchMutation = useMutation({
    mutationFn: (q: string) =>
      semanticSearch(repoId, q, 10, language || undefined, chunkType || undefined).then((r) => r.data),
    onSuccess: setResults,
  })

  const handleSearch = (q?: string) => {
    const text = q ?? query
    if (!text.trim() || !repoId) return
    if (q) setQuery(q)
    searchMutation.mutate(text)
  }

  const sourceTag = (r: any) => {
    const parts = [r.retrieval_source]
    if (r.rerank_score !== undefined) parts.push(`score: ${r.rerank_score.toFixed(2)}`)
    return parts.join(' · ')
  }

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-center gap-2 mb-6">
        <Search size={22} className="text-indigo-600" />
        <h1 className="text-2xl font-bold text-gray-900">Semantic Code Search</h1>
      </div>

      {/* Search bar */}
      <Card className="mb-6">
        <CardContent className="pt-4">
          <div className="flex gap-3 mb-3">
            <select
              value={repoId}
              onChange={(e) => { setRepoId(e.target.value); setResults(null) }}
              className="w-64 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">Select repository...</option>
              {repos.filter((r: any) => r.is_indexed).map((r: any) => (
                <option key={r.id} value={r.id}>{r.full_name}</option>
              ))}
            </select>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="flex items-center gap-1.5 px-3 py-2 text-sm text-gray-500 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <Filter size={14} />
              Filters
            </button>
          </div>

          {showFilters && (
            <div className="flex gap-3 mb-3">
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-44 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">All languages</option>
                {LANGUAGES.filter(Boolean).map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
              <select
                value={chunkType}
                onChange={(e) => setChunkType(e.target.value)}
                className="w-44 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">All types</option>
                {CHUNK_TYPES.filter(Boolean).map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          )}

          <div className="flex gap-3">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Search your codebase... (e.g. JWT authentication logic)"
              className="flex-1 px-4 py-3 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <Button onClick={() => handleSearch()} disabled={!repoId || !query.trim()} loading={searchMutation.isPending}>
              <Search size={16} />
              Search
            </Button>
          </div>

          {/* Example queries */}
          {!results && (
            <div className="mt-4">
              <p className="text-xs text-gray-400 mb-2">Try:</p>
              <div className="flex flex-wrap gap-2">
                {EXAMPLE_QUERIES.map((q) => (
                  <button
                    key={q}
                    onClick={() => handleSearch(q)}
                    disabled={!repoId}
                    className="text-xs px-3 py-1.5 bg-gray-50 border border-gray-200 rounded-full text-gray-600 hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Loading */}
      {searchMutation.isPending && (
        <div className="flex items-center gap-3 p-6 bg-white border border-gray-200 rounded-xl mb-4">
          <Loader2 className="animate-spin text-indigo-500" size={20} />
          <span className="text-gray-600 text-sm">Running hybrid search (BM25 + Vector + Reranker)...</span>
        </div>
      )}

      {/* Results */}
      {results && (
        <>
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm text-gray-600">
              <span className="font-semibold text-gray-900">{results.count}</span> results for{' '}
              <span className="font-medium text-indigo-600">"{results.query}"</span>
            </p>
            <button onClick={() => setResults(null)} className="text-xs text-gray-400 hover:text-gray-600">
              Clear
            </button>
          </div>

          <div className="space-y-3">
            {results.results.map((r: any, i: number) => (
              <Card key={r.id ?? i}>
                <CardContent className="py-4">
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <FileCode size={14} className="text-gray-400 flex-shrink-0" />
                      <span className="text-sm font-mono text-gray-700 truncate">{r.file_path}</span>
                      {r.chunk_name && (
                        <>
                          <span className="text-gray-300">›</span>
                          <span className="text-sm font-semibold text-indigo-700 truncate">{r.chunk_name}</span>
                        </>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      {r.language && <Badge variant="info">{r.language}</Badge>}
                      {r.chunk_type && <Badge variant="default">{r.chunk_type}</Badge>}
                      {r.retrieval_source && (
                        <Badge variant={r.retrieval_source === 'hybrid' ? 'success' : 'default'}>
                          {r.retrieval_source}
                        </Badge>
                      )}
                    </div>
                  </div>

                  <pre className="text-xs bg-gray-950 text-gray-200 rounded-xl p-4 overflow-x-auto font-mono leading-relaxed max-h-48">
                    {r.content?.slice(0, 600)}{r.content?.length > 600 ? '\n...' : ''}
                  </pre>

                  <div className="mt-2 flex items-center gap-3">
                    {r.score !== undefined && (
                      <span className="text-xs text-gray-400">
                        Score: <span className="font-mono text-gray-600">{r.score?.toFixed(4)}</span>
                      </span>
                    )}
                    {r.rerank_score !== undefined && (
                      <span className="text-xs text-gray-400">
                        Rerank: <span className="font-mono text-gray-600">{r.rerank_score?.toFixed(4)}</span>
                      </span>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}

            {results.results.length === 0 && (
              <div className="text-center py-12 text-gray-400">
                <Search size={32} className="mx-auto mb-3 opacity-30" />
                <p>No results found. Try a different query.</p>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
