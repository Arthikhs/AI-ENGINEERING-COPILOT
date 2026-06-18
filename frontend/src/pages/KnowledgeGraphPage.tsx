import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Network, Search, GitBranch, Loader2, Zap,
  ArrowRight, Database, Package, Layers, Code2
} from 'lucide-react'
import ReactFlow, {
  Background, Controls, MiniMap,
  Node, Edge, NodeTypes,
  Handle, Position,
} from 'reactflow'
import 'reactflow/dist/style.css'
import {
  buildKnowledgeGraph, getKnowledgeGraph,
  queryKnowledgeGraph, findDependents, getKnowledgeGraphStats
} from '../services/api'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import ReactMarkdown from 'react-markdown'
import { cn } from '../lib/utils'

const NODE_TYPE_COLOR: Record<string, string> = {
  service:    'bg-indigo-100 text-indigo-700 border-indigo-300',
  controller: 'bg-blue-100 text-blue-700 border-blue-300',
  model:      'bg-green-100 text-green-700 border-green-300',
  repository: 'bg-yellow-100 text-yellow-700 border-yellow-300',
  library:    'bg-purple-100 text-purple-700 border-purple-300',
  config:     'bg-gray-100 text-gray-600 border-gray-300',
  test:       'bg-orange-100 text-orange-700 border-orange-300',
  module:     'bg-slate-100 text-slate-600 border-slate-300',
}

// Custom React Flow node
function KGNode({ data }: { data: any }) {
  const colorClass = NODE_TYPE_COLOR[data.nodeType] ?? 'bg-gray-100 text-gray-600 border-gray-300'
  return (
    <div className={cn('px-3 py-2 rounded-xl border text-xs font-semibold shadow-sm min-w-[80px] text-center', colorClass)}>
      <Handle type="target" position={Position.Top} className="!bg-gray-400 !w-2 !h-2" />
      <div className="truncate max-w-[120px]">{data.label}</div>
      <div className="text-[9px] opacity-60 mt-0.5 font-normal truncate">{data.repo?.split('/')[1]}</div>
      <Handle type="source" position={Position.Bottom} className="!bg-gray-400 !w-2 !h-2" />
    </div>
  )
}

const nodeTypes: NodeTypes = { kgNode: KGNode }

function buildFlowElements(graphData: any): { nodes: Node[]; edges: Edge[] } {
  if (!graphData?.nodes?.length) return { nodes: [], edges: [] }

  // Layout: group by repo in columns
  const repoGroups: Record<string, any[]> = {}
  for (const n of graphData.nodes) {
    if (!repoGroups[n.repo]) repoGroups[n.repo] = []
    repoGroups[n.repo].push(n)
  }

  const nodes: Node[] = []
  const COL_WIDTH = 200, ROW_HEIGHT = 80
  let col = 0
  for (const [, repoNodes] of Object.entries(repoGroups)) {
    repoNodes.forEach((n, row) => {
      nodes.push({
        id: n.id, type: 'kgNode',
        position: { x: col * COL_WIDTH, y: row * ROW_HEIGHT },
        data: { label: n.name, nodeType: n.type, repo: n.repo, file: n.file_path },
      })
    })
    col++
  }

  const edges: Edge[] = graphData.edges.map((e: any, i: number) => ({
    id: `e${i}`, source: e.source, target: e.target,
    label: e.weight > 1 ? `×${e.weight}` : undefined,
    type: 'smoothstep',
    style: { stroke: '#6366f1', strokeWidth: 1.5 },
    labelStyle: { fontSize: 9, fill: '#9ca3af' },
    animated: false,
  }))

  return { nodes, edges }
}

const EXAMPLE_QUESTIONS = [
  'Which services depend on UserService?',
  'Which repos use the auth library?',
  'Show the dependency chain from AuthService to Database.',
  'What shared libraries are used across all services?',
  'Are there any circular dependencies?',
]

export default function KnowledgeGraphPage() {
  const [question, setQuestion] = useState('')
  const [depInput, setDepInput] = useState('')
  const [queryResult, setQueryResult] = useState<any>(null)
  const [depResult, setDepResult] = useState<any>(null)
  const [activeTab, setActiveTab] = useState<'graph' | 'query' | 'dependents'>('graph')
  const qc = useQueryClient()

  const { data: stats } = useQuery({
    queryKey: ['kg-stats'],
    queryFn: () => getKnowledgeGraphStats().then(r => r.data),
  })

  const { data: graph, isLoading: graphLoading } = useQuery({
    queryKey: ['kg-graph'],
    queryFn: () => getKnowledgeGraph().then(r => r.data),
  })

  const buildMutation = useMutation({
    mutationFn: () => buildKnowledgeGraph().then(r => r.data),
    onSuccess: () => {
      setTimeout(() => qc.invalidateQueries({ queryKey: ['kg-graph', 'kg-stats'] }), 3000)
    },
  })

  const queryMutation = useMutation({
    mutationFn: (q: string) => queryKnowledgeGraph(q).then(r => r.data),
    onSuccess: (data) => setQueryResult(data),
  })

  const depMutation = useMutation({
    mutationFn: (name: string) => findDependents(name).then(r => r.data),
    onSuccess: (data) => setDepResult(data),
  })

  const { nodes: flowNodes, edges: flowEdges } = buildFlowElements(graph)
  const [selectedNode, setSelectedNode] = useState<any>(null)

  const onNodeClick = useCallback((_: any, node: Node) => {
    const original = graph?.nodes?.find((n: any) => n.id === node.id)
    setSelectedNode(original ?? null)
  }, [graph])

  return (
    <div className="p-8 max-w-6xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-100 rounded-xl">
            <Network size={22} className="text-indigo-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Multi-Repository Knowledge Graph</h1>
            <p className="text-sm text-gray-500">Cross-repo service dependency mapping & analysis</p>
          </div>
        </div>
        <Button
          onClick={() => buildMutation.mutate()}
          loading={buildMutation.isPending}
        >
          <Zap size={15} /> Build Graph
        </Button>
      </div>

      {buildMutation.isSuccess && (
        <div className="mb-4 px-4 py-3 bg-green-50 border border-green-200 rounded-xl text-sm text-green-700">
          ✅ Knowledge graph build started for: {buildMutation.data?.repos?.join(', ')}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Nodes', value: stats?.total_nodes ?? 0, icon: Code2, color: 'text-indigo-600' },
          { label: 'Edges', value: stats?.total_edges ?? 0, icon: ArrowRight, color: 'text-blue-600' },
          { label: 'Repos', value: stats?.total_repos ?? 0, icon: GitBranch, color: 'text-green-600' },
          { label: 'Node Types', value: Object.keys(stats?.node_type_breakdown ?? {}).length, icon: Layers, color: 'text-purple-600' },
        ].map(({ label, value, icon: Icon, color }) => (
          <Card key={label}>
            <CardContent className="flex items-center gap-3 py-3">
              <Icon size={18} className={color} />
              <div>
                <p className="text-xl font-bold text-gray-900">{value}</p>
                <p className="text-xs text-gray-500">{label}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Node type breakdown */}
      {stats?.node_type_breakdown && Object.keys(stats.node_type_breakdown).length > 0 && (
        <div className="flex flex-wrap gap-2 mb-6">
          {Object.entries(stats.node_type_breakdown).map(([type, count]: [string, any]) => (
            <span key={type} className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${NODE_TYPE_COLOR[type] ?? 'bg-gray-100 text-gray-600'}`}>
              {type} · {count}
            </span>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-xl w-fit">
        {(['graph', 'query', 'dependents'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors capitalize ${
              activeTab === tab ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab === 'graph' ? '🗺 Graph View' : tab === 'query' ? '💬 AI Query' : '🔍 Find Dependents'}
          </button>
        ))}
      </div>

      {/* Tab: Graph View — React Flow */}
      {activeTab === 'graph' && (
        <div className="space-y-4">
          {graphLoading && (
            <div className="flex items-center gap-3 p-6 bg-white border border-gray-200 rounded-xl">
              <Loader2 className="animate-spin text-indigo-500" size={20} />
              <span className="text-gray-600">Loading knowledge graph...</span>
            </div>
          )}

          {!graphLoading && (!graph?.nodes || graph.nodes.length === 0) && (
            <Card>
              <CardContent className="text-center py-14">
                <Network size={40} className="mx-auto mb-3 text-gray-300" />
                <p className="font-medium text-gray-600">No knowledge graph built yet</p>
                <p className="text-sm text-gray-400 mt-1 mb-4">Click <strong>Build Graph</strong> to analyze your repositories</p>
                <Button onClick={() => buildMutation.mutate()} loading={buildMutation.isPending} size="sm">
                  <Zap size={14} /> Build Now
                </Button>
              </CardContent>
            </Card>
          )}

          {graph?.nodes?.length > 0 && (
            <div className="flex gap-4">
              {/* React Flow canvas */}
              <div className="flex-1 bg-white border border-gray-200 rounded-2xl overflow-hidden" style={{ height: 520 }}>
                <ReactFlow
                  nodes={flowNodes}
                  edges={flowEdges}
                  nodeTypes={nodeTypes}
                  onNodeClick={onNodeClick}
                  fitView
                  fitViewOptions={{ padding: 0.2 }}
                >
                  <Background color="#e5e7eb" gap={20} />
                  <Controls />
                  <MiniMap
                    nodeColor={(n) => {
                      const colors: Record<string, string> = {
                        service: '#818cf8', controller: '#60a5fa', model: '#34d399',
                        repository: '#fbbf24', library: '#a78bfa', module: '#94a3b8',
                      }
                      return colors[n.data?.nodeType] ?? '#d1d5db'
                    }}
                    className="!bg-gray-50 !border !border-gray-200 !rounded-xl"
                  />
                </ReactFlow>
              </div>

              {/* Node detail panel */}
              <div className="w-56 flex-shrink-0">
                {selectedNode ? (
                  <Card>
                    <CardHeader><h3 className="font-semibold text-gray-800 text-sm">Node Detail</h3></CardHeader>
                    <CardContent className="space-y-2">
                      <p className="font-bold text-indigo-700">{selectedNode.name}</p>
                      <Badge variant="info">{selectedNode.type}</Badge>
                      <p className="text-xs text-gray-500 break-all">{selectedNode.file_path}</p>
                      <p className="text-xs text-gray-400">{selectedNode.repo}</p>
                      {selectedNode.language && <Badge variant="default">{selectedNode.language}</Badge>}
                    </CardContent>
                  </Card>
                ) : (
                  <Card>
                    <CardContent className="text-center py-8 text-gray-400 text-xs">
                      Click a node to see details
                    </CardContent>
                  </Card>
                )}

                {/* Legend */}
                <Card className="mt-3">
                  <CardHeader><h3 className="text-xs font-semibold text-gray-500">LEGEND</h3></CardHeader>
                  <CardContent>
                    <div className="space-y-1.5">
                      {Object.entries(NODE_TYPE_COLOR).map(([type, cls]) => (
                        <div key={type} className="flex items-center gap-2">
                          <span className={cn('w-3 h-3 rounded-sm border', cls)} />
                          <span className="text-xs text-gray-600 capitalize">{type}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab: AI Query */}
      {activeTab === 'query' && (
        <div className="space-y-4">
          <Card>
            <CardContent className="pt-4">
              <div className="flex gap-3">
                <input
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && question.trim() && queryMutation.mutate(question)}
                  placeholder="Ask a cross-repository question..."
                  className="flex-1 px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <Button
                  onClick={() => queryMutation.mutate(question)}
                  disabled={!question.trim()}
                  loading={queryMutation.isPending}
                >
                  <Search size={15} /> Ask
                </Button>
              </div>
              {/* Example questions */}
              <div className="mt-3 flex flex-wrap gap-2">
                {EXAMPLE_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => { setQuestion(q); queryMutation.mutate(q) }}
                    className="text-xs px-3 py-1.5 bg-gray-50 border border-gray-200 rounded-lg text-gray-600 hover:bg-indigo-50 hover:border-indigo-300 transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>

          {queryMutation.isPending && (
            <div className="flex items-center gap-3 p-5 bg-white border border-gray-200 rounded-xl">
              <Loader2 className="animate-spin text-indigo-500" size={20} />
              <span className="text-gray-600">Searching across all repositories...</span>
            </div>
          )}

          {queryResult && (
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2 flex-wrap">
                  <Network size={15} className="text-indigo-600" />
                  <span className="font-semibold text-gray-800">Knowledge Graph Answer</span>
                  <Badge variant="info">KG + RAG Fusion</Badge>
                  {queryResult.fusion_stats && (
                    <div className="ml-auto flex gap-2 text-xs text-gray-400">
                      <span>Vector: {queryResult.fusion_stats.hybrid_candidates}</span>
                      <span>·</span>
                      <span>KG: {queryResult.fusion_stats.kg_candidates}</span>
                      <span>·</span>
                      <span>Reranked: {queryResult.fusion_stats.returned_after_rerank}</span>
                    </div>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <div className="prose prose-sm max-w-none text-gray-700 mb-4">
                  <ReactMarkdown>{queryResult.answer}</ReactMarkdown>
                </div>

                {/* KG Traversal Chain */}
                {queryResult.kg_traversal?.edges?.length > 0 && (
                  <div className="mb-4 p-3 bg-indigo-50 border border-indigo-100 rounded-xl">
                    <p className="text-xs font-semibold text-indigo-600 mb-2">GRAPH TRAVERSAL CHAIN</p>
                    <div className="flex flex-wrap items-center gap-1.5">
                      {queryResult.kg_traversal.edges.slice(0, 8).map((e: any, i: number) => (
                        <span key={i} className="flex items-center gap-1 text-xs">
                          <span className="px-2 py-0.5 bg-white border border-indigo-200 rounded text-indigo-700 font-medium">{e.source_name}</span>
                          <ArrowRight size={10} className="text-indigo-400" />
                          <span className="px-2 py-0.5 bg-white border border-indigo-200 rounded text-indigo-700 font-medium">{e.target_name}</span>
                          {i < queryResult.kg_traversal.edges.slice(0, 8).length - 1 && (
                            <span className="text-gray-300 mx-1">|</span>
                          )}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {queryResult.repos_searched?.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-100">
                    <p className="text-xs font-semibold text-gray-500 mb-2">REPOS SEARCHED</p>
                    <div className="flex flex-wrap gap-1.5">
                      {queryResult.repos_searched.map((r: string) => (
                        <Badge key={r} variant="info">{r}</Badge>
                      ))}
                    </div>
                  </div>
                )}

                {queryResult.sources?.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-100">
                    <p className="text-xs font-semibold text-gray-500 mb-2">SOURCE FILES</p>
                    <div className="space-y-1">
                      {queryResult.sources.map((s: any, i: number) => (
                        <div key={i} className="flex items-center gap-2 text-xs text-gray-500">
                          <Code2 size={11} />
                          <span>{s.file_path}</span>
                          {s.chunk_name && <span className="text-gray-400">→ {s.chunk_name}</span>}
                          <span className={`ml-auto text-xs font-medium px-1.5 py-0.5 rounded ${
                            s.source === 'fusion' ? 'bg-indigo-50 text-indigo-600' :
                            s.source === 'kg' ? 'bg-green-50 text-green-600' :
                            'bg-gray-50 text-gray-500'
                          }`}>{s.source}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Tab: Find Dependents */}
      {activeTab === 'dependents' && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <h2 className="font-semibold text-gray-800">Find What Depends On a Service</h2>
              <p className="text-xs text-gray-500 mt-0.5">Enter a service or module name to see all dependents</p>
            </CardHeader>
            <CardContent>
              <div className="flex gap-3">
                <input
                  value={depInput}
                  onChange={(e) => setDepInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && depInput.trim() && depMutation.mutate(depInput)}
                  placeholder="e.g. UserService, AuthModule, billing..."
                  className="flex-1 px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <Button
                  onClick={() => depMutation.mutate(depInput)}
                  disabled={!depInput.trim()}
                  loading={depMutation.isPending}
                >
                  Find Dependents
                </Button>
              </div>
            </CardContent>
          </Card>

          {depMutation.isPending && (
            <div className="flex items-center gap-3 p-5 bg-white border border-gray-200 rounded-xl">
              <Loader2 className="animate-spin text-indigo-500" size={20} />
              <span className="text-gray-600">Traversing dependency graph...</span>
            </div>
          )}

          {depResult && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <h2 className="font-semibold text-gray-800">
                    Services depending on <span className="text-indigo-600">"{depResult.target}"</span>
                  </h2>
                  <Badge variant={depResult.count > 0 ? 'danger' : 'success'}>
                    {depResult.count} dependent{depResult.count !== 1 ? 's' : ''}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                {depResult.dependents?.length === 0 && (
                  <div className="text-center py-8 text-gray-400">
                    <Package size={32} className="mx-auto mb-2 opacity-30" />
                    <p>{depResult.message ?? 'No dependents found.'}</p>
                  </div>
                )}

                {depResult.dependents?.length > 0 && (
                  <div className="space-y-2">
                    {depResult.dependents.map((dep: any, i: number) => (
                      <div key={i} className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
                        <div className="flex items-center gap-3">
                          <div className={`px-2 py-0.5 rounded text-xs font-medium ${NODE_TYPE_COLOR[dep.type] ?? 'bg-gray-100 text-gray-600'}`}>
                            {dep.type}
                          </div>
                          <div>
                            <p className="font-medium text-gray-800 text-sm">{dep.name}</p>
                            <p className="text-xs text-gray-400">{dep.repo} · {dep.file_path}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant="info">{dep.edge_type}</Badge>
                          {dep.weight > 1 && (
                            <span className="text-xs text-gray-400">×{dep.weight}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Dependency chain visual */}
                {depResult.dependents?.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-gray-100">
                    <p className="text-xs font-semibold text-gray-500 mb-2">DEPENDENCY CHAIN</p>
                    <div className="flex flex-wrap items-center gap-1.5 text-sm">
                      {depResult.dependents.slice(0, 5).map((dep: any, i: number) => (
                        <span key={i} className="flex items-center gap-1.5">
                          <span className="px-2 py-1 bg-indigo-50 text-indigo-700 rounded-lg font-medium text-xs">
                            {dep.name}
                          </span>
                          <ArrowRight size={12} className="text-gray-400" />
                        </span>
                      ))}
                      <span className="px-2 py-1 bg-green-50 text-green-700 rounded-lg font-medium text-xs">
                        {depResult.target}
                      </span>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
