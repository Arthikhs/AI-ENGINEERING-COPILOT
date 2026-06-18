import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Play, Shield, Network, Wrench, FlaskConical, Loader2, Zap, DollarSign, Star } from 'lucide-react'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { cn } from '../lib/utils'
import { invokeRouter, getRoutingTable, getRepositories } from '../services/api'

type AgentId = 'security_review' | 'architecture' | 'refactoring' | 'test_generation' | 'simple_qa' | 'pr_review'

const AGENTS: { id: AgentId; label: string; icon: any; color: string; description: string; example: string }[] = [
  { id: 'security_review', label: 'Security',      icon: Shield,      color: 'text-red-500',    description: 'Find vulnerabilities in code', example: 'Review this code for SQL injection and auth flaws' },
  { id: 'architecture',    label: 'Architecture',  icon: Network,     color: 'text-blue-500',   description: 'Analyze system architecture',  example: 'Explain the dependency structure of this service' },
  { id: 'refactoring',     label: 'Refactoring',   icon: Wrench,      color: 'text-orange-500', description: 'Detect code smells & suggest fixes', example: 'Find long methods and suggest refactoring' },
  { id: 'test_generation', label: 'Test Gen',      icon: FlaskConical, color: 'text-green-500', description: 'Generate unit tests',          example: 'Write pytest tests for the AuthService class' },
  { id: 'simple_qa',       label: 'Q&A',           icon: Play,        color: 'text-indigo-500', description: 'Fast code Q&A',                example: 'What does the payment service do?' },
  { id: 'pr_review',       label: 'PR Review',     icon: Zap,         color: 'text-purple-500', description: 'Review pull request changes',  example: 'Summarize the risks in this PR' },
]

function MetricBadge({ icon: Icon, label, value, color }: any) {
  return (
    <div className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-50 border border-gray-200', color)}>
      <Icon size={13} />
      <span className="text-xs font-medium text-gray-600">{label}:</span>
      <span className="text-xs font-bold">{value}</span>
    </div>
  )
}

export default function PlaygroundPage() {
  const [selectedAgent, setSelectedAgent] = useState<AgentId>('simple_qa')
  const [prompt, setPrompt] = useState('')
  const [result, setResult] = useState<any>(null)

  const { data: routingData } = useQuery({
    queryKey: ['routing-table'],
    queryFn: () => getRoutingTable().then(r => r.data),
  })

  const invokeM = useMutation({
    mutationFn: () => invokeRouter(selectedAgent, prompt).then(r => r.data),
    onSuccess: setResult,
  })

  const currentAgent = AGENTS.find(a => a.id === selectedAgent)!
  const routingRow = routingData?.routing_table?.find((r: any) => r.task_type === selectedAgent)

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-center gap-2 mb-6">
        <Play size={22} className="text-indigo-600" />
        <h1 className="text-2xl font-bold text-gray-900">Agent Playground</h1>
        <Badge variant="info" className="ml-2">Live Demo</Badge>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-6">
        {AGENTS.map(agent => {
          const Icon = agent.icon
          const row = routingData?.routing_table?.find((r: any) => r.task_type === agent.id)
          return (
            <button
              key={agent.id}
              onClick={() => { setSelectedAgent(agent.id); setResult(null) }}
              className={cn(
                'flex flex-col items-start gap-2 p-4 rounded-xl border text-left transition-all',
                selectedAgent === agent.id
                  ? 'border-indigo-400 bg-indigo-50 shadow-sm'
                  : 'border-gray-200 bg-white hover:border-indigo-200 hover:bg-gray-50'
              )}
            >
              <div className="flex items-center gap-2">
                <Icon size={16} className={agent.color} />
                <span className="font-semibold text-sm text-gray-800">{agent.label}</span>
              </div>
              <p className="text-xs text-gray-500">{agent.description}</p>
              {row && (
                <span className="text-xs font-mono text-indigo-600 bg-indigo-50 border border-indigo-100 px-2 py-0.5 rounded">
                  → {row.model}
                </span>
              )}
            </button>
          )
        })}
      </div>

      <Card className="mb-4">
        <CardHeader>
          <div className="flex items-center gap-2">
            <currentAgent.icon size={16} className={currentAgent.color} />
            <h2 className="font-semibold text-gray-800">{currentAgent.label} Agent</h2>
            {routingRow && (
              <div className="ml-auto flex items-center gap-2">
                <span className="text-xs text-gray-500">Model:</span>
                <span className="text-xs font-mono font-bold text-indigo-700">{routingRow.model}</span>
                <span className="text-xs text-gray-400">| Quality: {(routingRow.quality_score * 100).toFixed(0)}%</span>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-gray-400 mb-2">Example: <em>{currentAgent.example}</em></p>
          <textarea
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            placeholder={`Enter your prompt for the ${currentAgent.label} agent...`}
            rows={5}
            className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none font-mono"
          />
          <div className="flex justify-end mt-3">
            <Button
              onClick={() => invokeM.mutate()}
              disabled={!prompt.trim()}
              loading={invokeM.isPending}
            >
              <Play size={14} className="mr-1" /> Run Agent
            </Button>
          </div>
        </CardContent>
      </Card>

      {invokeM.isPending && (
        <div className="flex items-center gap-3 p-6 bg-white border border-gray-200 rounded-xl mb-4">
          <Loader2 className="animate-spin text-indigo-500" size={20} />
          <span className="text-gray-600 text-sm">Running {currentAgent.label} agent via {routingRow?.model}...</span>
        </div>
      )}

      {result && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between flex-wrap gap-2">
              <h2 className="font-semibold text-gray-800">Response</h2>
              <div className="flex flex-wrap gap-2">
                <MetricBadge icon={Zap} label="Latency" value={`${result.latency_ms}ms`} color="text-blue-600" />
                <MetricBadge icon={DollarSign} label="Cost" value={`$${result.estimated_cost_usd}`} color="text-green-600" />
                <MetricBadge icon={Star} label="Quality" value={`${(result.quality_score * 100).toFixed(0)}%`} color="text-yellow-600" />
                <Badge variant="info">{result.model}</Badge>
                <Badge variant="default">{result.input_tokens + result.output_tokens} tokens</Badge>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <pre className="text-sm text-gray-700 bg-gray-50 border border-gray-200 rounded-xl p-4 overflow-x-auto whitespace-pre-wrap leading-relaxed">
              {result.content}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
