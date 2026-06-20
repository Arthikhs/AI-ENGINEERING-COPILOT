import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Play, Terminal, CheckCircle2, XCircle, Clock, Loader2, Shield, Wifi, WifiOff } from 'lucide-react'
import { Button } from '../components/ui/Button'
import api from '../services/api'

const LANGUAGE_TEMPLATES: Record<string, string> = {
  python: `# Python Sandbox — Secure & Isolated
def fibonacci(n: int) -> list[int]:
    a, b = 0, 1
    result = []
    for _ in range(n):
        result.append(a)
        a, b = b, a + b
    return result

print(fibonacci(10))
`,
  javascript: `// JavaScript Sandbox — Secure & Isolated
function fibonacci(n) {
  const result = [];
  let [a, b] = [0, 1];
  for (let i = 0; i < n; i++) {
    result.push(a);
    [a, b] = [b, a + b];
  }
  return result;
}

console.log(fibonacci(10));
`,
  typescript: `// TypeScript Sandbox — Secure & Isolated
function fibonacci(n: number): number[] {
  const result: number[] = [];
  let [a, b] = [0, 1];
  for (let i = 0; i < n; i++) {
    result.push(a);
    [a, b] = [b, a + b];
  }
  return result;
}

console.log(fibonacci(10));
`,
  java: `// Java Sandbox — Secure & Isolated
public class Solution {
    public static int[] fibonacci(int n) {
        int[] result = new int[n];
        int a = 0, b = 1;
        for (int i = 0; i < n; i++) {
            result[i] = a;
            int tmp = a + b;
            a = b;
            b = tmp;
        }
        return result;
    }

    public static void main(String[] args) {
        int[] fib = fibonacci(10);
        for (int x : fib) System.out.print(x + " ");
    }
}
`,
}

const LANGUAGE_COLORS: Record<string, string> = {
  python:     'text-blue-400',
  javascript: 'text-yellow-400',
  typescript: 'text-blue-500',
  java:       'text-orange-400',
}

export default function SandboxPage() {
  const [language, setLanguage]   = useState('python')
  const [code, setCode]           = useState(LANGUAGE_TEMPLATES.python)
  const [stdin, setStdin]         = useState('')
  const [showStdin, setShowStdin] = useState(false)

  // Check sandbox status
  const { data: statusData } = useQuery({
    queryKey: ['sandbox-status'],
    queryFn: () => api.get('/sandbox/status').then(r => r.data),
    refetchInterval: 30_000,
  })

  // Get supported languages
  const { data: langData } = useQuery({
    queryKey: ['sandbox-languages'],
    queryFn: () => api.get('/sandbox/languages').then(r => r.data),
  })

  // Execute code
  const executeMutation = useMutation({
    mutationFn: () => api.post('/sandbox/execute', {
      code, language, stdin: stdin || undefined
    }).then(r => r.data),
  })

  const handleLanguageChange = (lang: string) => {
    setLanguage(lang)
    setCode(LANGUAGE_TEMPLATES[lang] || '')
  }

  const result = executeMutation.data
  const isRunning = executeMutation.isPending

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gray-900 rounded-xl">
            <Terminal size={20} className="text-green-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Code Execution Sandbox</h1>
            <p className="text-sm text-gray-500">Secure isolated Docker environment — no network, CPU/memory limited</p>
          </div>
        </div>

        {/* Sandbox Status */}
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium border ${
          statusData?.available
            ? 'bg-green-50 border-green-200 text-green-700'
            : 'bg-red-50 border-red-200 text-red-700'
        }`}>
          {statusData?.available
            ? <><Wifi size={12} /> Sandbox Ready</>
            : <><WifiOff size={12} /> Docker Unavailable</>
          }
        </div>
      </div>

      {/* Security Banner */}
      <div className="flex items-center gap-3 bg-gray-900 text-gray-300 rounded-xl px-4 py-3 mb-6 text-xs">
        <Shield size={14} className="text-green-400 flex-shrink-0" />
        <span>
          Execution is <span className="text-green-400 font-medium">fully isolated</span> —
          no network access · 256MB RAM limit · 50% CPU limit · 30s timeout · read-only filesystem
        </span>
        {langData?.limits && (
          <span className="ml-auto text-gray-500">
            Supports: {(langData.languages || []).join(' · ')}
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Left: Editor */}
        <div className="flex flex-col gap-3">
          {/* Language Selector */}
          <div className="flex gap-2">
            {['python', 'javascript', 'typescript', 'java'].map(lang => (
              <button
                key={lang}
                onClick={() => handleLanguageChange(lang)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                  language === lang
                    ? 'bg-gray-900 border-gray-700 text-white'
                    : 'bg-white border-gray-200 text-gray-500 hover:border-gray-400'
                }`}
              >
                <span className={language === lang ? LANGUAGE_COLORS[lang] : ''}>
                  {lang}
                </span>
              </button>
            ))}
          </div>

          {/* Code Editor */}
          <div className="relative">
            <textarea
              value={code}
              onChange={e => setCode(e.target.value)}
              className="w-full h-80 bg-gray-950 text-gray-100 font-mono text-sm p-4 rounded-xl border border-gray-800 focus:outline-none focus:border-indigo-500 resize-none leading-relaxed"
              spellCheck={false}
              placeholder="Write your code here..."
            />
            <div className="absolute top-3 right-3 text-xs text-gray-600 font-mono">
              {code.split('\n').length} lines
            </div>
          </div>

          {/* Stdin Toggle */}
          <button
            onClick={() => setShowStdin(!showStdin)}
            className="text-xs text-gray-400 hover:text-gray-600 text-left"
          >
            {showStdin ? '▼' : '▶'} Standard Input (stdin)
          </button>
          {showStdin && (
            <textarea
              value={stdin}
              onChange={e => setStdin(e.target.value)}
              placeholder="Input data for your program..."
              className="w-full h-20 bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
            />
          )}

          {/* Run Button */}
          <Button
            onClick={() => executeMutation.mutate()}
            disabled={!code.trim() || isRunning}
            loading={isRunning}
            className="gap-2 w-full justify-center"
          >
            {isRunning ? <><Loader2 size={14} className="animate-spin" /> Running...</> : <><Play size={14} /> Run Code</>}
          </Button>
        </div>

        {/* Right: Output */}
        <div className="flex flex-col gap-3">
          {/* Result Header */}
          <div className="flex items-center justify-between h-8">
            <span className="text-sm font-semibold text-gray-700">Output</span>
            {result && (
              <div className="flex items-center gap-3">
                <div className={`flex items-center gap-1 text-xs font-medium ${result.success ? 'text-green-600' : 'text-red-600'}`}>
                  {result.success ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
                  {result.success ? 'Passed' : `Exit ${result.exit_code}`}
                </div>
                <div className="flex items-center gap-1 text-xs text-gray-400">
                  <Clock size={11} />
                  {result.execution_time_ms}ms
                </div>
                {result.timed_out && (
                  <span className="text-xs text-orange-500 font-medium">⏰ Timed out</span>
                )}
              </div>
            )}
          </div>

          {/* stdout */}
          <div className="bg-gray-950 rounded-xl border border-gray-800 overflow-hidden flex-1">
            <div className="px-3 py-2 border-b border-gray-800 flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-green-500" />
              <span className="text-xs text-gray-500 font-mono">stdout</span>
            </div>
            <pre className="p-4 text-sm font-mono text-green-300 overflow-auto max-h-52 whitespace-pre-wrap min-h-16">
              {isRunning
                ? <span className="text-gray-500 animate-pulse">Executing in sandbox...</span>
                : result?.stdout
                  ? result.stdout
                  : <span className="text-gray-600">No output yet. Run your code!</span>
              }
            </pre>
          </div>

          {/* stderr */}
          {(result?.stderr || isRunning) && (
            <div className="bg-gray-950 rounded-xl border border-red-900 overflow-hidden">
              <div className="px-3 py-2 border-b border-red-900 flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-red-500" />
                <span className="text-xs text-red-400 font-mono">stderr</span>
              </div>
              <pre className="p-4 text-sm font-mono text-red-300 overflow-auto max-h-36 whitespace-pre-wrap">
                {result?.stderr || ''}
              </pre>
            </div>
          )}

          {/* Sandbox info */}
          {result && (
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-2 text-center">
                <p className="text-gray-400">Language</p>
                <p className="font-semibold text-gray-700 capitalize">{result.language}</p>
              </div>
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-2 text-center">
                <p className="text-gray-400">Exit Code</p>
                <p className={`font-semibold ${result.exit_code === 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {result.exit_code}
                </p>
              </div>
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-2 text-center">
                <p className="text-gray-400">Time</p>
                <p className="font-semibold text-gray-700">{result.execution_time_ms}ms</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
