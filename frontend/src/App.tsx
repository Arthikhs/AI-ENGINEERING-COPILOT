import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Layout } from './components/Layout'
import LoginPage from './pages/LoginPage'
import GitHubCallbackPage from './pages/GitHubCallbackPage'
import DashboardPage from './pages/DashboardPage'
import RepositoriesPage from './pages/RepositoriesPage'
import ChatPage from './pages/ChatPage'
import PRReviewPage from './pages/PRReviewPage'
import ArchitecturePage from './pages/ArchitecturePage'
import KnowledgeGraphPage from './pages/KnowledgeGraphPage'
import SecurityPage from './pages/SecurityPage'
import RefactoringPage from './pages/RefactoringPage'
import TestGenerationPage from './pages/TestGenerationPage'
import SemanticSearchPage from './pages/SemanticSearchPage'
import SystemDesignPage from './pages/SystemDesignPage'
import PlaygroundPage from './pages/PlaygroundPage'
import PromptsPage from './pages/PromptsPage'
import BenchmarkPage from './pages/BenchmarkPage'
import ExecutivePage from './pages/ExecutivePage'
import ChangeIntelligencePage from './pages/ChangeIntelligencePage'
import IntegrationsPage from './pages/IntegrationsPage'
import AutonomousEngineerPage from './pages/AutonomousEngineerPage'
import AgentsPage from './pages/AgentsPage'
import EvalPage from './pages/EvalPage'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/auth/github/callback" element={<GitHubCallbackPage />} />
          <Route element={<Layout />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/repositories" element={<RepositoriesPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/pr-review" element={<PRReviewPage />} />
            <Route path="/architecture" element={<ArchitecturePage />} />
            <Route path="/knowledge-graph" element={<KnowledgeGraphPage />} />
            <Route path="/security" element={<SecurityPage />} />
            <Route path="/refactoring" element={<RefactoringPage />} />
            <Route path="/test-generation" element={<TestGenerationPage />} />
            <Route path="/search" element={<SemanticSearchPage />} />
            <Route path="/system-design" element={<SystemDesignPage />} />
            <Route path="/playground" element={<PlaygroundPage />} />
            <Route path="/prompts" element={<PromptsPage />} />
            <Route path="/benchmarks" element={<BenchmarkPage />} />
            <Route path="/executive" element={<ExecutivePage />} />
            <Route path="/change-intelligence" element={<ChangeIntelligencePage />} />
            <Route path="/integrations" element={<IntegrationsPage />} />
            <Route path="/autonomous-engineer" element={<AutonomousEngineerPage />} />
            <Route path="/agents" element={<AgentsPage />} />
            <Route path="/eval" element={<EvalPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
