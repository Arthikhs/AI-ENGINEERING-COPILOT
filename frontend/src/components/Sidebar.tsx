import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, GitBranch, MessageSquare, GitPullRequest,
  Network, LogOut, Share2, Shield, Wrench, TestTube, Search, Cpu,
  Play, BookMarked, BarChart2, TrendingUp, GitCommit, Plug, Bot,
  FlaskConical, Layers,
} from 'lucide-react'
import { useAppStore } from '../store'
import { cn } from '../lib/utils'

const navGroups = [
  {
    label: 'Main',
    items: [
      { to: '/',             icon: LayoutDashboard, label: 'Dashboard' },
      { to: '/repositories', icon: GitBranch,       label: 'Repositories' },
      { to: '/chat',         icon: MessageSquare,   label: 'Chat' },
      { to: '/search',       icon: Search,          label: 'Code Search' },
    ],
  },
  {
    label: 'Analysis',
    items: [
      { to: '/pr-review',      icon: GitPullRequest, label: 'PR Review' },
      { to: '/security',       icon: Shield,         label: 'Security' },
      { to: '/refactoring',    icon: Wrench,         label: 'Refactoring' },
      { to: '/test-generation',icon: TestTube,       label: 'Test Generation' },
      { to: '/agents',         icon: Layers,         label: 'AI Agents' },
      { to: '/eval',           icon: FlaskConical,   label: 'LLM Evaluation' },
    ],
  },
  {
    label: 'Architecture',
    items: [
      { to: '/architecture',    icon: Network,  label: 'Architecture' },
      { to: '/knowledge-graph', icon: Share2,   label: 'Knowledge Graph' },
      { to: '/system-design',   icon: Cpu,      label: 'System Design' },
    ],
  },
  {
    label: 'AI Platform',
    items: [
      { to: '/autonomous-engineer',icon: Bot,        label: '🤖 Auto Engineer' },
      { to: '/playground',         icon: Play,       label: 'Agent Playground' },
      { to: '/prompts',            icon: BookMarked, label: 'Prompts' },
      { to: '/benchmarks',         icon: BarChart2,  label: 'Benchmarks' },
      { to: '/change-intelligence',icon: GitCommit,  label: 'Change Intel' },
      { to: '/integrations',       icon: Plug,       label: 'Slack / Teams' },
      { to: '/executive',          icon: TrendingUp, label: 'Executive' },
    ],
  },
]

export function Sidebar() {
  const { user, logout } = useAppStore()
  const navigate = useNavigate()

  return (
    <aside className="w-60 bg-gray-950 text-gray-300 flex flex-col h-screen sticky top-0 overflow-y-auto">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-gray-800 flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">
            AI
          </div>
          <span className="font-semibold text-white text-sm">Engineering Copilot</span>
        </div>
      </div>

      {/* Nav groups */}
      <nav className="flex-1 px-3 py-4 space-y-5">
        {navGroups.map(group => (
          <div key={group.label}>
            <p className="text-[10px] font-semibold text-gray-600 uppercase tracking-widest px-3 mb-1">
              {group.label}
            </p>
            <div className="space-y-0.5">
              {group.items.map(({ to, icon: Icon, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                      isActive
                        ? 'bg-indigo-600 text-white'
                        : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                    )
                  }
                >
                  <Icon size={15} />
                  {label}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* User footer */}
      <div className="px-3 py-4 border-t border-gray-800 flex-shrink-0">
        {user && (
          <div className="flex items-center gap-2 mb-3 px-2">
            {user.avatar_url ? (
              <img src={user.avatar_url} className="w-7 h-7 rounded-full" alt={user.username} />
            ) : (
              <div className="w-7 h-7 bg-indigo-500 rounded-full flex items-center justify-center text-white text-xs">
                {user.username[0].toUpperCase()}
              </div>
            )}
            <span className="text-sm text-gray-300 truncate">{user.username}</span>
          </div>
        )}
        <button
          onClick={() => { logout(); navigate('/login') }}
          className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
        >
          <LogOut size={15} /> Sign out
        </button>
      </div>
    </aside>
  )
}
