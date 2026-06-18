import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { MessageSquare, CheckCircle2, XCircle, Send, Loader2, Terminal } from 'lucide-react'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { cn } from '../lib/utils'
import { getIntegrationConfig, testIntegrationCommand } from '../services/api'

const COMMANDS = [
  { cmd: '@copilot review pr #123',    desc: 'AI review of a pull request',     icon: '🔍' },
  { cmd: '@copilot security <repo>',   desc: 'Run security vulnerability scan', icon: '🛡️' },
  { cmd: '@copilot ask <question>',    desc: 'Ask anything about your code',    icon: '💬' },
  { cmd: '@copilot status',            desc: 'Check platform health',           icon: '✅' },
  { cmd: '@copilot help',              desc: 'Show all commands',               icon: '📖' },
]

const SETUP_STEPS = {
  slack: [
    'Go to api.slack.com/apps → Create New App → From Scratch',
    'Add OAuth scope: chat:write, commands',
    'Install app to workspace, copy Bot Token',
    'Add SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET to your .env',
    'Create slash command /copilot → URL: https://your-domain/integrations/slack/command',
    'Enable Event Subscriptions → URL: https://your-domain/integrations/slack/events',
    'Subscribe to: app_mention, message.channels',
  ],
  teams: [
    'Go to Teams → channel → Connectors → Incoming Webhook',
    'Create a webhook, copy the URL',
    'Add TEAMS_WEBHOOK_URL to your .env',
    'For bot commands: Teams Admin Center → Apps → Upload custom app',
    'Point outgoing webhook to: https://your-domain/integrations/teams/message',
  ],
}

export default function IntegrationsPage() {
  const [platform, setPlatform] = useState<'slack' | 'teams'>('slack')
  const [testText, setTestText] = useState('')
  const [testResult, setTestResult] = useState<string | null>(null)

  const { data: config } = useQuery({
    queryKey: ['integration-config'],
    queryFn: () => getIntegrationConfig().then(r => r.data),
  })

  const testM = useMutation({
    mutationFn: () => testIntegrationCommand(testText).then(r => r.data),
    onSuccess: data => setTestResult(data.response),
  })

  const slackOk = config?.slack?.configured
  const teamsOk = config?.teams?.configured

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-center gap-2 mb-6">
        <MessageSquare size={22} className="text-indigo-600" />
        <h1 className="text-2xl font-bold text-gray-900">Slack / Teams Integration</h1>
      </div>

      {/* Status cards */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        {/* Slack */}
        <Card className={cn('border-2', slackOk ? 'border-green-200' : 'border-gray-200')}>
          <CardContent className="py-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-xl">💬</span>
                <span className="font-semibold text-gray-800">Slack</span>
              </div>
              {slackOk
                ? <div className="flex items-center gap-1 text-green-600 text-xs font-medium"><CheckCircle2 size={14} /> Connected</div>
                : <div className="flex items-center gap-1 text-gray-400 text-xs"><XCircle size={14} /> Not configured</div>
              }
            </div>
            <p className="text-xs text-gray-500">
              {slackOk
                ? `Bot token configured · Channel: ${config?.slack?.default_channel || '#engineering'}`
                : 'Set SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET in .env'
              }
            </p>
          </CardContent>
        </Card>

        {/* Teams */}
        <Card className={cn('border-2', teamsOk ? 'border-green-200' : 'border-gray-200')}>
          <CardContent className="py-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-xl">🟦</span>
                <span className="font-semibold text-gray-800">Microsoft Teams</span>
              </div>
              {teamsOk
                ? <div className="flex items-center gap-1 text-green-600 text-xs font-medium"><CheckCircle2 size={14} /> Connected</div>
                : <div className="flex items-center gap-1 text-gray-400 text-xs"><XCircle size={14} /> Not configured</div>
              }
            </div>
            <p className="text-xs text-gray-500">
              {teamsOk ? 'Teams webhook configured' : 'Set TEAMS_WEBHOOK_URL in .env'}
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Left: commands + live tester */}
        <div className="space-y-4">
          {/* Command reference */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Terminal size={15} className="text-gray-500" />
                <h2 className="font-semibold text-gray-800">Available Commands</h2>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {COMMANDS.map((c, i) => (
                  <div key={i} className="flex items-start gap-3 p-2 rounded-lg hover:bg-gray-50">
                    <span className="text-base">{c.icon}</span>
                    <div>
                      <p className="text-xs font-mono font-bold text-indigo-700">{c.cmd}</p>
                      <p className="text-xs text-gray-500">{c.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Live command tester */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Send size={15} className="text-gray-500" />
                <h2 className="font-semibold text-gray-800">Test Commands Locally</h2>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-gray-400 mb-3">Test any command without Slack/Teams configured</p>
              <div className="flex gap-2 mb-3">
                <input
                  value={testText}
                  onChange={e => setTestText(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && testText.trim() && testM.mutate()}
                  placeholder="@copilot help"
                  className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <Button onClick={() => testM.mutate()} disabled={!testText.trim()} loading={testM.isPending}>
                  Send
                </Button>
              </div>
              <div className="flex flex-wrap gap-1.5 mb-3">
                {['@copilot help', '@copilot status', '@copilot ask how does auth work?'].map(ex => (
                  <button key={ex} onClick={() => setTestText(ex)}
                    className="text-xs px-2 py-1 bg-gray-50 border border-gray-200 rounded text-gray-500 hover:bg-indigo-50 hover:border-indigo-200">
                    {ex}
                  </button>
                ))}
              </div>
              {testM.isPending && (
                <div className="flex items-center gap-2 text-gray-400 text-xs">
                  <Loader2 size={12} className="animate-spin" /> Processing...
                </div>
              )}
              {testResult && (
                <pre className="text-xs text-gray-700 bg-gray-50 border border-gray-200 rounded-xl p-3 whitespace-pre-wrap font-mono">
                  {testResult}
                </pre>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right: setup guide */}
        <div className="space-y-4">
          {/* Platform toggle */}
          <div className="flex gap-1 bg-gray-100 p-1 rounded-xl w-fit">
            {(['slack', 'teams'] as const).map(p => (
              <button key={p} onClick={() => setPlatform(p)}
                className={cn(
                  'px-4 py-2 rounded-lg text-sm font-medium transition-colors capitalize',
                  platform === p ? 'bg-white text-indigo-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                )}>
                {p === 'slack' ? '💬 Slack' : '🟦 Teams'}
              </button>
            ))}
          </div>

          <Card>
            <CardHeader>
              <h2 className="font-semibold text-gray-800">Setup Guide — {platform === 'slack' ? 'Slack' : 'Microsoft Teams'}</h2>
            </CardHeader>
            <CardContent>
              <ol className="space-y-3">
                {SETUP_STEPS[platform].map((step, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-5 h-5 bg-indigo-100 text-indigo-700 rounded-full text-xs flex items-center justify-center font-bold">
                      {i + 1}
                    </span>
                    <span className="text-sm text-gray-700 leading-relaxed">{step}</span>
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>

          {/* .env reference */}
          <Card>
            <CardHeader><h2 className="font-semibold text-gray-800">.env Variables</h2></CardHeader>
            <CardContent>
              <pre className="text-xs bg-gray-900 text-green-300 rounded-xl p-4 font-mono overflow-x-auto">
                {platform === 'slack'
                  ? `# Slack\nSLACK_BOT_TOKEN=xoxb-...\nSLACK_SIGNING_SECRET=...\nSLACK_DEFAULT_CHANNEL=#engineering`
                  : `# Microsoft Teams\nTEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...`
                }
              </pre>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
