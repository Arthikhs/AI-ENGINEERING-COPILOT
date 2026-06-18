import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Github } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { getGithubLoginUrl } from '../services/api'
import { useAppStore } from '../store'

export default function LoginPage() {
  const { token } = useAppStore()
  const navigate = useNavigate()

  useEffect(() => {
    if (token) navigate('/')
  }, [token, navigate])

  const handleLogin = async () => {
    const res = await getGithubLoginUrl()
    window.location.href = res.data.auth_url
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="w-full max-w-md text-center px-6">
        <div className="w-16 h-16 bg-indigo-600 rounded-2xl flex items-center justify-center text-white font-bold text-2xl mx-auto mb-6">
          AI
        </div>
        <h1 className="text-3xl font-bold text-white mb-2">Engineering Copilot</h1>
        <p className="text-gray-400 mb-8">Chat with your codebase using AI-powered analysis</p>

        <div className="bg-gray-900 rounded-2xl p-8 border border-gray-800">
          <p className="text-gray-300 text-sm mb-6">
            Connect your GitHub account to get started. We'll help you understand, review, and analyze your repositories.
          </p>
          <Button onClick={handleLogin} size="lg" className="w-full justify-center gap-3">
            <Github size={20} />
            Continue with GitHub
          </Button>
        </div>

        <p className="text-gray-600 text-xs mt-6">
          Powered by GPT-4o · LangGraph · pgvector
        </p>
      </div>
    </div>
  )
}
