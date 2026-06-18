import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { githubCallback } from '../services/api'
import { useAppStore } from '../store'

export default function GitHubCallbackPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { setToken, setUser } = useAppStore()

  useEffect(() => {
    const code = params.get('code')
    if (!code) { navigate('/login'); return }

    githubCallback(code)
      .then((res) => {
        setToken(res.data.access_token)
        setUser(res.data.user)
        navigate('/')
      })
      .catch(() => navigate('/login'))
  }, [])

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="text-center">
        <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-gray-400">Authenticating with GitHub...</p>
      </div>
    </div>
  )
}
