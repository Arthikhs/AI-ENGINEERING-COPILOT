import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { GitBranch, Plus, RefreshCw, Loader2, CheckCircle, XCircle, Zap } from 'lucide-react'
import { getRepositories, connectRepository, indexRepository } from '../services/api'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { formatDate, cn } from '../lib/utils'

const STAGE_LABELS: Record<string, string> = {
  cloning:   'Cloning repository...',
  chunking:  'Chunking source files...',
  embedding: 'Generating embeddings...',
  done:      'Completed!',
  error:     'Failed',
}

function ProgressBar({ syncId, repoId, onDone }: { syncId: string; repoId: string; onDone: () => void }) {
  const [progress, setProgress] = useState({ status: 'running', stage: 'cloning', pct: 5, error: '' })
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    const token = localStorage.getItem('token')
    const url = `/api/repos/${repoId}/index/progress?sync_id=${syncId}`
    // Use fetch-based SSE so we can send auth header
    const controller = new AbortController()

    async function readStream() {
      try {
        const resp = await fetch(url, {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        })
        const reader = resp.body!.getReader()
        const decoder = new TextDecoder()
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          const text = decoder.decode(value)
          for (const line of text.split('\n')) {
            if (!line.startsWith('data: ')) continue
            try {
              const data = JSON.parse(line.slice(6))
              setProgress(data)
              if (data.status === 'completed' || data.status === 'failed') {
                onDone()
                return
              }
            } catch {}
          }
        }
      } catch {}
    }

    readStream()
    return () => controller.abort()
  }, [syncId, repoId])

  const isError = progress.status === 'failed'
  const isDone = progress.status === 'completed'

  return (
    <div className="mt-3 space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className={cn('font-medium', isError ? 'text-red-600' : isDone ? 'text-green-600' : 'text-indigo-600')}>
          {isDone ? <span className="flex items-center gap-1"><CheckCircle size={12} /> Done</span>
            : isError ? <span className="flex items-center gap-1"><XCircle size={12} /> {progress.error}</span>
            : <span className="flex items-center gap-1"><Loader2 size={12} className="animate-spin" />{STAGE_LABELS[progress.stage] ?? progress.stage}</span>}
        </span>
        <span className="text-gray-400 font-mono">{progress.pct}%</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-1.5">
        <div
          className={cn('h-1.5 rounded-full transition-all duration-500',
            isError ? 'bg-red-400' : isDone ? 'bg-green-500' : 'bg-indigo-500')}
          style={{ width: `${progress.pct}%` }}
        />
      </div>
    </div>
  )
}

export default function RepositoriesPage() {
  const [repoInput, setRepoInput] = useState('')
  const [indexingMap, setIndexingMap] = useState<Record<string, string>>({}) // repoId → syncId
  const qc = useQueryClient()

  const { data: repos = [], isLoading } = useQuery({
    queryKey: ['repos'],
    queryFn: () => getRepositories().then((r) => r.data),
    refetchInterval: 8000,
  })

  const connectMutation = useMutation({
    mutationFn: (fullName: string) => connectRepository(fullName),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['repos'] }); setRepoInput('') },
  })

  const indexMutation = useMutation({
    mutationFn: (repoId: string) => indexRepository(repoId).then(r => r.data),
    onSuccess: (data, repoId) => {
      if (data?.sync_id) {
        setIndexingMap(prev => ({ ...prev, [repoId]: data.sync_id }))
      }
    },
  })

  const handleConnect = (e: React.FormEvent) => {
    e.preventDefault()
    if (repoInput.trim()) connectMutation.mutate(repoInput.trim())
  }

  const handleIndexDone = (repoId: string) => {
    setIndexingMap(prev => { const n = { ...prev }; delete n[repoId]; return n })
    qc.invalidateQueries({ queryKey: ['repos'] })
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Repositories</h1>
      </div>

      {/* Connect Form */}
      <Card className="mb-6">
        <CardHeader>
          <h2 className="font-semibold text-gray-800 flex items-center gap-2">
            <Plus size={16} /> Connect Repository
          </h2>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleConnect} className="flex gap-3">
            <input
              value={repoInput}
              onChange={(e) => setRepoInput(e.target.value)}
              placeholder="owner/repository (e.g. facebook/react)"
              className="flex-1 px-4 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <Button type="submit" loading={connectMutation.isPending}>Connect</Button>
          </form>
          {connectMutation.isError && (
            <p className="text-red-500 text-sm mt-2">Failed to connect. Check the name and try again.</p>
          )}
        </CardContent>
      </Card>

      {/* Repos List */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="animate-spin text-indigo-500" size={28} />
        </div>
      ) : (
        <div className="space-y-3">
          {repos.map((repo: any) => {
            const syncId = indexingMap[repo.id]
            const isIndexing = !!syncId

            return (
              <Card key={repo.id}>
                <CardContent>
                  <div className="flex items-center justify-between">
                    <div className="flex items-start gap-3">
                      <GitBranch size={18} className="text-gray-400 mt-0.5" />
                      <div>
                        <p className="font-semibold text-gray-800">{repo.full_name}</p>
                        {repo.description && (
                          <p className="text-xs text-gray-500 mt-0.5">{repo.description}</p>
                        )}
                        <div className="flex items-center gap-3 mt-1.5 text-xs text-gray-400">
                          <span>{repo.default_branch}</span>
                          {repo.is_indexed && (
                            <>
                              <span>·</span>
                              <span>{repo.total_files} files</span>
                              <span>·</span>
                              <span>{repo.total_chunks} chunks</span>
                              {repo.last_synced_at && (
                                <>
                                  <span>·</span>
                                  <span>synced {formatDate(repo.last_synced_at)}</span>
                                </>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {repo.language && <Badge variant="info">{repo.language}</Badge>}
                      {isIndexing
                        ? <Badge variant="warning"><Loader2 size={10} className="animate-spin mr-1" />Indexing</Badge>
                        : <Badge variant={repo.is_indexed ? 'success' : 'warning'}>
                            {repo.is_indexed ? 'Indexed' : 'Not indexed'}
                          </Badge>}
                      {!isIndexing && (
                        <Button size="sm" variant={repo.is_indexed ? 'ghost' : 'secondary'}
                          onClick={() => indexMutation.mutate(repo.id)}
                          loading={indexMutation.isPending && indexMutation.variables === repo.id}>
                          <RefreshCw size={13} />
                          {repo.is_indexed ? 'Re-index' : 'Index'}
                        </Button>
                      )}
                    </div>
                  </div>

                  {/* Real-time progress bar via SSE */}
                  {isIndexing && (
                    <ProgressBar
                      syncId={syncId}
                      repoId={repo.id}
                      onDone={() => handleIndexDone(repo.id)}
                    />
                  )}
                </CardContent>
              </Card>
            )
          })}

          {repos.length === 0 && (
            <div className="text-center py-16 text-gray-400">
              <GitBranch size={40} className="mx-auto mb-3 opacity-20" />
              <p>No repositories yet. Connect one above to get started.</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
