import { useState, useRef, useEffect, useCallback } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Send, Bot, User, FileCode, Loader2, Zap, GitBranch } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { getRepositories, sendMessage } from '../services/api'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { useAppStore } from '../store'
import { cn } from '../lib/utils'

const EXAMPLE_QUESTIONS = [
  'How does user authentication work?',
  'Which services call the payment API?',
  'Explain the database connection setup.',
  'Where is Redis used in this codebase?',
]

export default function ChatPage() {
  const { selectedRepo, setSelectedRepo } = useAppStore()
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<any[]>([])
  const [convId, setConvId] = useState<string | null>(null)
  const [multiAgent, setMultiAgent] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  const { data: repos = [] } = useQuery({
    queryKey: ['repos'],
    queryFn: () => getRepositories().then((r) => r.data),
  })

  const indexedRepos = repos.filter((r: any) => r.is_indexed)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // SSE streaming handler
  const streamMessage = useCallback(async (msg: string, repoId: string) => {
    if (!msg.trim() || !repoId) return
    setMessages((prev) => [...prev, { role: 'user', content: msg, id: Date.now() }])
    setInput('')
    setStreaming(true)

    const streamingId = Date.now() + 1
    setMessages((prev) => [...prev, { role: 'assistant', content: '', id: streamingId, streaming: true }])

    abortRef.current = new AbortController()
    const token = localStorage.getItem('token')
    const mode = multiAgent ? 'multi_agent' : 'simple'

    try {
      const resp = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ repo_id: repoId, message: msg, conversation_id: convId, mode }),
        signal: abortRef.current.signal,
      })

      const reader = resp.body!.getReader()
      const decoder = new TextDecoder()
      let doneData: any = null

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const text = decoder.decode(value)
        for (const line of text.split('\n')) {
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6).trim()
          if (payload === '[DONE]') break
          try {
            const chunk = JSON.parse(payload)
            if (chunk.type === 'token') {
              setMessages((prev) => prev.map((m) =>
                m.id === streamingId ? { ...m, content: m.content + chunk.content } : m
              ))
            } else if (chunk.type === 'done') {
              doneData = chunk
            }
          } catch {}
        }
      }

      // Finalise message with metadata
      setMessages((prev) => prev.map((m) =>
        m.id === streamingId
          ? { ...m, streaming: false, agent_type: doneData?.agent_type, agents_used: doneData?.agents_used, plan: doneData?.plan, sources: doneData?.sources }
          : m
      ))
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        setMessages((prev) => prev.map((m) =>
          m.id === streamingId ? { ...m, content: 'Something went wrong. Please try again.', streaming: false } : m
        ))
      }
    } finally {
      setStreaming(false)
    }
  }, [convId, multiAgent])

  const sendMutation = useMutation({
    mutationFn: ({ msg, repoId }: { msg: string; repoId: string }) =>
      sendMessage(repoId, msg, convId ?? undefined, multiAgent ? 'multi_agent' : 'simple').then((r) => r.data),
    onMutate: ({ msg }) => {
      setMessages((prev) => [...prev, { role: 'user', content: msg, id: Date.now() }])
      setInput('')
    },
    onSuccess: (data) => {
      setConvId(data.conversation_id)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.content,
          agent_type: data.agent_type,
          agents_used: data.agents_used,
          plan: data.plan,
          sources: data.sources,
          id: data.message_id,
        },
      ])
    },
    onError: () => {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Something went wrong. Please try again.', id: Date.now() },
      ])
    },
  })

  const isLoading = streaming || sendMutation.isPending

  const handleSend = (msg?: string) => {
    const text = msg ?? input
    if (!text.trim() || !selectedRepo || isLoading) return
    streamMessage(text, selectedRepo.id)
  }

  return (
    <div className="flex h-screen">
      {/* Sidebar: repo selector */}
      <div className="w-56 border-r border-gray-200 bg-white flex flex-col">
        <div className="p-4 border-b border-gray-100">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Repository</p>
          <select
            value={selectedRepo?.id ?? ''}
            onChange={(e) => {
              const r = repos.find((x: any) => x.id === e.target.value)
              setSelectedRepo(r ?? null)
              setMessages([])
              setConvId(null)
            }}
            className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">Select repo...</option>
            {indexedRepos.map((r: any) => (
              <option key={r.id} value={r.id}>{r.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 bg-white flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bot size={18} className="text-indigo-600" />
            <span className="font-semibold text-gray-800">
              {selectedRepo ? selectedRepo.full_name : 'Select a repository to start'}
            </span>
          </div>
          {/* Multi-Agent toggle */}
          <button
            onClick={() => setMultiAgent(!multiAgent)}
            className={cn(
              'flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border',
              multiAgent
                ? 'bg-indigo-600 text-white border-indigo-600'
                : 'bg-white text-gray-500 border-gray-200 hover:border-indigo-300'
            )}
          >
            <Zap size={13} />
            {multiAgent ? 'Multi-Agent ON' : 'Multi-Agent OFF'}
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {messages.length === 0 && selectedRepo && (
            <div className="mt-8">
              <p className="text-sm text-gray-500 text-center mb-4">Try asking:</p>
              <div className="grid grid-cols-2 gap-2 max-w-xl mx-auto">
                {EXAMPLE_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => handleSend(q)}
                    className="text-left text-sm p-3 bg-white border border-gray-200 rounded-xl hover:border-indigo-300 hover:bg-indigo-50 transition-colors text-gray-600"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div key={msg.id} className={cn('flex gap-3', msg.role === 'user' ? 'flex-row-reverse' : '')}>
              <div className={cn(
                'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
                msg.role === 'user' ? 'bg-indigo-600' : 'bg-gray-100'
              )}>
                {msg.role === 'user'
                  ? <User size={15} className="text-white" />
                  : <Bot size={15} className="text-indigo-600" />}
              </div>
              <div className={cn('max-w-2xl', msg.role === 'user' ? 'items-end' : '')}>
                <div className={cn(
                  'px-4 py-3 rounded-2xl text-sm',
                  msg.role === 'user'
                    ? 'bg-indigo-600 text-white rounded-tr-sm'
                    : 'bg-white border border-gray-200 text-gray-800 rounded-tl-sm'
                )}>
                  {msg.role === 'assistant' ? (
                    <ReactMarkdown
                      components={{
                        code({ node, inline, className, children, ...props }: any) {
                          const match = /language-(\w+)/.exec(className || '')
                          return !inline && match ? (
                            <SyntaxHighlighter style={oneDark} language={match[1]} PreTag="div" {...props}>
                              {String(children).replace(/\n$/, '')}
                            </SyntaxHighlighter>
                          ) : (
                            <code className="bg-gray-100 px-1 py-0.5 rounded text-xs" {...props}>{children}</code>
                          )
                        },
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  ) : (
                    msg.content
                  )}
                </div>
                {msg.sources?.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {msg.sources.map((s: any, i: number) => (
                      <div key={i} className="flex items-center gap-1 text-xs text-gray-500 bg-gray-50 border border-gray-200 px-2 py-1 rounded-lg">
                        <FileCode size={11} />
                        {s.file_path.split('/').slice(-2).join('/')}
                      </div>
                    ))}
                  </div>
                )}
                {/* Plan / agents used for multi-agent responses */}
                {msg.agents_used?.length > 0 && (
                  <div className="mt-2">
                    <div className="flex flex-wrap gap-1">
                      <span className="text-xs text-gray-400">Agents:</span>
                      {msg.agents_used.map((a: string) => (
                        <Badge key={a} variant="info" className="text-[10px]">{a}</Badge>
                      ))}
                    </div>
                    {msg.plan?.length > 0 && (
                      <div className="flex items-center gap-1 mt-1">
                        <GitBranch size={10} className="text-gray-400" />
                        <span className="text-[10px] text-gray-400">Plan: {msg.plan.join(' → ')}</span>
                      </div>
                    )}
                  </div>
                )}
                {msg.agent_type && !msg.agents_used?.length && (
                  <div className="mt-1.5 flex items-center gap-2">
                    <Badge variant="info" className="text-[10px]">{msg.agent_type} agent</Badge>
                    {msg.model_used && <span className="text-[10px] text-gray-400 font-mono">{msg.model_used}</span>}
                    {msg.latency_ms > 0 && <span className="text-[10px] text-gray-400">{msg.latency_ms}ms</span>}
                    {msg.estimated_cost_usd > 0 && <span className="text-[10px] text-gray-400">${msg.estimated_cost_usd}</span>}
                  </div>
                )}
              </div>
            </div>
          ))}

          {sendMutation.isPending || (streaming && messages[messages.length - 1]?.role !== 'assistant') ? (
            <div className="flex gap-3">
              <div className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center">
                <Loader2 size={15} className="text-indigo-600 animate-spin" />
              </div>
              <div className="bg-white border border-gray-200 px-4 py-3 rounded-2xl rounded-tl-sm">
                <div className="flex gap-1">
                  {[0, 1, 2].map((i) => (
                    <span key={i} className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                  ))}
                </div>
              </div>
            </div>
          ) : null}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="px-6 py-4 border-t border-gray-200 bg-white">
          {!selectedRepo && (
            <p className="text-center text-sm text-gray-400 mb-3">Select an indexed repository to start chatting</p>
          )}
          <div className="flex gap-3">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
              placeholder={selectedRepo ? 'Ask about your codebase...' : 'Select a repository first'}
              disabled={!selectedRepo || isLoading}
              className="flex-1 px-4 py-3 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-50"
            />
            <Button
              onClick={() => handleSend()}
              disabled={!input.trim() || !selectedRepo}
              loading={isLoading}
              className="px-4"
            >
              <Send size={16} />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
