import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { BookMarked, Plus, RotateCcw, ChevronDown, GitBranch } from 'lucide-react'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { cn } from '../lib/utils'
import {
  listPrompts, createPrompt, getPrompt,
  addPromptVersion, rollbackPrompt
} from '../services/api'

const AGENT_TYPES = ['security', 'architecture', 'refactoring', 'test_generation', 'qa', 'pr_review', 'documentation']

export default function PromptsPage() {
  const qc = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [agentFilter, setAgentFilter] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [showAddVersion, setShowAddVersion] = useState(false)

  // Create form
  const [newName, setNewName] = useState('')
  const [newAgent, setNewAgent] = useState('security')
  const [newContent, setNewContent] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [newAb, setNewAb] = useState('')

  // Add version form
  const [vContent, setVContent] = useState('')

  const { data: listData } = useQuery({
    queryKey: ['prompts', agentFilter],
    queryFn: () => listPrompts(agentFilter || undefined).then(r => r.data),
  })

  const { data: detail } = useQuery({
    queryKey: ['prompt', selectedId],
    queryFn: () => getPrompt(selectedId!).then(r => r.data),
    enabled: !!selectedId,
  })

  const createM = useMutation({
    mutationFn: () => createPrompt(newName, newAgent, newContent, newDesc, newAb || undefined).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['prompts'] })
      setShowCreate(false)
      setNewName(''); setNewContent(''); setNewDesc(''); setNewAb('')
    },
  })

  const addVersionM = useMutation({
    mutationFn: () => addPromptVersion(selectedId!, vContent).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['prompt', selectedId] })
      setShowAddVersion(false)
      setVContent('')
    },
  })

  const rollbackM = useMutation({
    mutationFn: (version: number) => rollbackPrompt(selectedId!, version).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['prompt', selectedId] }),
  })

  return (
    <div className="p-8 max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <BookMarked size={22} className="text-indigo-600" />
          <h1 className="text-2xl font-bold text-gray-900">Prompt Management</h1>
        </div>
        <Button onClick={() => setShowCreate(!showCreate)}>
          <Plus size={14} className="mr-1" /> New Prompt
        </Button>
      </div>

      {showCreate && (
        <Card className="mb-6">
          <CardHeader><h2 className="font-semibold text-gray-800">Create Prompt Template</h2></CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="Prompt name"
                className="px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              <select value={newAgent} onChange={e => setNewAgent(e.target.value)}
                className="px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                {AGENT_TYPES.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
              <input value={newDesc} onChange={e => setNewDesc(e.target.value)} placeholder="Description (optional)"
                className="px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              <input value={newAb} onChange={e => setNewAb(e.target.value)} placeholder="A/B group: A or B (optional)"
                className="px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <textarea value={newContent} onChange={e => setNewContent(e.target.value)}
              placeholder="Enter prompt content..." rows={6}
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono resize-none mb-3" />
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
              <Button onClick={() => createM.mutate()} disabled={!newName || !newContent} loading={createM.isPending}>Create</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="flex gap-6">
        {/* Left: list */}
        <div className="w-64 flex-shrink-0">
          <select value={agentFilter} onChange={e => setAgentFilter(e.target.value)}
            className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-indigo-500">
            <option value="">All agents</option>
            {AGENT_TYPES.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
          <div className="space-y-2">
            {listData?.prompts?.map((p: any) => (
              <button key={p.id} onClick={() => setSelectedId(p.id)}
                className={cn(
                  'w-full text-left px-4 py-3 rounded-xl border transition-colors',
                  selectedId === p.id
                    ? 'border-indigo-400 bg-indigo-50'
                    : 'border-gray-200 bg-white hover:border-indigo-200'
                )}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-semibold text-gray-800 truncate">{p.name}</span>
                  {p.ab_group && <Badge variant="warning" className="text-xs">{p.ab_group}</Badge>}
                </div>
                <span className="text-xs text-gray-500">{p.agent_type}</span>
                <span className="text-xs text-gray-400 ml-2">v{p.active_version}</span>
              </button>
            ))}
            {!listData?.prompts?.length && (
              <p className="text-sm text-gray-400 text-center py-6">No prompts yet</p>
            )}
          </div>
        </div>

        {/* Right: detail */}
        <div className="flex-1 min-w-0">
          {!selectedId && (
            <div className="flex items-center justify-center h-48 border border-dashed border-gray-300 rounded-xl text-gray-400 text-sm">
              Select a prompt to view details
            </div>
          )}
          {detail && (
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="font-semibold text-gray-800">{detail.name}</h2>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="info">{detail.agent_type}</Badge>
                        {detail.ab_group && <Badge variant="warning">Group {detail.ab_group}</Badge>}
                        <span className="text-xs text-gray-500">Active: v{detail.active_version}</span>
                      </div>
                    </div>
                    <Button variant="outline" onClick={() => setShowAddVersion(!showAddVersion)}>
                      <GitBranch size={14} className="mr-1" /> New Version
                    </Button>
                  </div>
                </CardHeader>
                {showAddVersion && (
                  <CardContent className="border-t border-gray-100 pt-4">
                    <textarea value={vContent} onChange={e => setVContent(e.target.value)}
                      placeholder="New prompt content..." rows={5}
                      className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500 mb-3" />
                    <div className="flex justify-end gap-2">
                      <Button variant="outline" onClick={() => setShowAddVersion(false)}>Cancel</Button>
                      <Button onClick={() => addVersionM.mutate()} disabled={!vContent} loading={addVersionM.isPending}>Save Version</Button>
                    </div>
                  </CardContent>
                )}
              </Card>

              <Card>
                <CardHeader><h2 className="font-semibold text-gray-800">Version History</h2></CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {detail.versions?.map((v: any) => (
                      <div key={v.version} className={cn(
                        'border rounded-xl p-4',
                        v.is_active ? 'border-indigo-300 bg-indigo-50' : 'border-gray-200 bg-white'
                      )}>
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-bold text-gray-700">v{v.version}</span>
                            {v.is_active && <Badge variant="success">Active</Badge>}
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-gray-400">{new Date(v.created_at).toLocaleDateString()}</span>
                            {!v.is_active && (
                              <button
                                onClick={() => rollbackM.mutate(v.version)}
                                className="flex items-center gap-1 text-xs text-indigo-600 hover:underline"
                              >
                                <RotateCcw size={11} /> Rollback
                              </button>
                            )}
                          </div>
                        </div>
                        <pre className="text-xs text-gray-600 bg-gray-50 rounded-lg p-3 font-mono whitespace-pre-wrap overflow-x-auto max-h-32">
                          {v.content}
                        </pre>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
