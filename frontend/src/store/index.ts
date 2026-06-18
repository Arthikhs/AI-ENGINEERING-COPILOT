import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface User {
  id: string
  username: string
  avatar_url?: string
}

interface Repository {
  id: string
  full_name: string
  name: string
  description?: string
  language?: string
  is_indexed: boolean
  total_files: number
  total_chunks: number
  last_synced_at?: string
  default_branch: string
}

interface AppState {
  user: User | null
  token: string | null
  selectedRepo: Repository | null
  setUser: (user: User | null) => void
  setToken: (token: string | null) => void
  setSelectedRepo: (repo: Repository | null) => void
  logout: () => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      selectedRepo: null,
      setUser: (user) => set({ user }),
      setToken: (token) => {
        if (token) localStorage.setItem('token', token)
        else localStorage.removeItem('token')
        set({ token })
      },
      setSelectedRepo: (repo) => set({ selectedRepo: repo }),
      logout: () => {
        localStorage.removeItem('token')
        set({ user: null, token: null, selectedRepo: null })
      },
    }),
    { name: 'copilot-store', partialize: (s) => ({ user: s.user, token: s.token }) }
  )
)
