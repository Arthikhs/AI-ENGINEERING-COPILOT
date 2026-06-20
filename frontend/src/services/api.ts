import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// Auth
export const getGithubLoginUrl = () => api.get('/auth/github/login')
export const githubCallback = (code: string) => api.get(`/auth/github/callback?code=${code}`)

// Repositories
export const getRepositories = () => api.get('/repos')
export const connectRepository = (full_name: string, branch?: string) =>
  api.post('/repos/connect', { full_name, branch })
export const indexRepository = (repo_id: string) => api.post(`/repos/${repo_id}/index`)
export const getRepository = (repo_id: string) => api.get(`/repos/${repo_id}`)
export const getSyncStatus = (repo_id: string) => api.get(`/repos/${repo_id}/sync/status`)

// Chat
export const sendMessage = (repo_id: string, message: string, conversation_id?: string, mode: string = 'simple') =>
  api.post('/chat', { repo_id, message, conversation_id, mode })
export const getConversations = (repo_id?: string) =>
  api.get('/chat/conversations', { params: repo_id ? { repo_id } : {} })
export const getMessages = (conv_id: string) =>
  api.get(`/chat/conversations/${conv_id}/messages`)

// PR Review
export const reviewPR = (repo_id: string, pr_number: number) =>
  api.post('/review/pr', { repo_id, pr_number })
export const getPRReviews = (repo_id: string) => api.get(`/review/pr/${repo_id}`)

// Architecture
export const analyzeArchitecture = (repo_id: string) =>
  api.post('/analyze/architecture', { repo_id })
export const getLatestArchitectureReport = (repo_id: string) =>
  api.get(`/analyze/architecture/${repo_id}/latest`)

// Knowledge Graph
export const buildKnowledgeGraph = (repo_ids?: string[]) =>
  api.post('/knowledge-graph/build', { repo_ids })
export const getKnowledgeGraph = () =>
  api.get('/knowledge-graph/graph')
export const queryKnowledgeGraph = (question: string) =>
  api.post('/knowledge-graph/query', { question })
export const findDependents = (node_name: string) =>
  api.post('/knowledge-graph/dependents', { node_name })
export const getKnowledgeGraphStats = () =>
  api.get('/knowledge-graph/stats')

// Security Review
export const securityReview = (repo_id: string) =>
  api.post('/agents/security/review', { repo_id })
export const runSecurityReview = securityReview  // alias used by SecurityPage

// Refactoring
export const refactorAnalyze = (repo_id: string, target_file?: string) =>
  api.post('/agents/refactor/analyze', { repo_id, target_file })
export const analyzeRefactoring = refactorAnalyze  // alias used by RefactoringPage

// Test Generation
export const generateTests = (repo_id: string, target: string, language?: string) =>
  api.post('/agents/tests/generate', { repo_id, target, language })

// System Design
export const generateSystemDesign = (repo_id: string, query: string) =>
  api.post('/agents/system-design/generate', { repo_id, query })

// Semantic Search
export const semanticSearch = (
  repo_id: string,
  query: string,
  top_k = 10,
  language_filter?: string,
  chunk_type_filter?: string
) => api.post('/agents/search', { repo_id, query, top_k, language_filter, chunk_type_filter })

// Documentation
export const generateDocumentation = (repo_id: string, target?: string) =>
  api.post('/agents/docs/generate', { repo_id, target })

// LLM Evaluation
export const evaluateAnswer = (repo_id: string, question: string, answer: string, contexts: string[]) =>
  api.post('/agents/eval', { repo_id, question, answer, contexts })

// Model Router
export const getRoutingTable = () => api.get('/router/routing-table')
export const getRouterStats = () => api.get('/router/stats')
export const invokeRouter = (task_type: string, prompt: string, override_model?: string) =>
  api.post('/router/invoke', { task_type, prompt, override_model })

// HITL
export const triggerHITL = (repo_id: string, pr_number?: number, github_token?: string) =>
  api.post('/hitl/trigger', { repo_id, pr_number, github_token })
export const listHITLApprovals = () => api.get('/hitl/approvals')
export const getHITLApproval = (id: string) => api.get(`/hitl/approvals/${id}`)
export const hitlAction = (id: string, action: 'approve' | 'reject') =>
  api.post(`/hitl/approvals/${id}/action`, { action })

// Prompts
export const listPrompts = (agent_type?: string) =>
  api.get('/prompts', { params: agent_type ? { agent_type } : {} })
export const createPrompt = (name: string, agent_type: string, content: string, description?: string, ab_group?: string) =>
  api.post('/prompts', { name, agent_type, content, description, ab_group })
export const getPrompt = (id: string) => api.get(`/prompts/${id}`)
export const addPromptVersion = (id: string, content: string) =>
  api.post(`/prompts/${id}/versions`, { content })
export const rollbackPrompt = (id: string, version: number) =>
  api.post(`/prompts/${id}/rollback/${version}`)

// Benchmarks
export const listBenchmarks = (agent_type?: string) =>
  api.get('/benchmarks', { params: agent_type ? { agent_type } : {} })
export const createBenchmark = (agent_type: string, version_label: string, model: string, test_cases: any[]) =>
  api.post('/benchmarks', { agent_type, version_label, model, test_cases })
export const runBenchmark = (id: string) => api.post(`/benchmarks/${id}/run`)
export const compareBenchmarks = (id_a: string, id_b: string) =>
  api.get('/benchmarks/compare', { params: { id_a, id_b } })

// Executive Dashboard
export const getExecutiveDashboard = (days: number = 30) =>
  api.get(`/executive/dashboard?days=${days}`)

// Change Intelligence
export const listChangeReports = (repo_id?: string, limit = 20) =>
  api.get('/change-intelligence/reports', { params: { repo_id, limit } })
export const getChangeReport = (id: string) =>
  api.get(`/change-intelligence/reports/${id}`)
export const manualChangeAnalyze = (repo_id: string, changed_files: string[]) =>
  api.post('/change-intelligence/analyze', { repo_id, changed_files })

// Integrations (Slack / Teams)
export const getIntegrationConfig = () => api.get('/integrations/config')
export const testIntegrationCommand = (text: string) =>
  api.post('/integrations/test-command', { text })

// Autonomous Engineer
export const runAutonomousEngineer = (repo_id: string, issue_number: number) =>
  api.post('/autonomous-engineer/run', { repo_id, issue_number })
export const getAutonomousJob = (job_id: string) =>
  api.get(`/autonomous-engineer/jobs/${job_id}`)
export const listAutonomousJobs = (repo_id?: string) =>
  api.get('/autonomous-engineer/jobs', { params: repo_id ? { repo_id } : {} })

// Cost Analytics
export const getCostSummary = (days: number = 7) =>
  api.get(`/analytics/costs/summary?days=${days}`)

// Enterprise: Health Score
export const getHealthScore = (repo_id: string) =>
  api.get(`/enterprise/health-score/${repo_id}`)
export const getHealthScoreHistory = (repo_id: string) =>
  api.get(`/enterprise/health-score/${repo_id}/history`)

// Enterprise: Governance
export const getGovernanceReport = (repo_id: string) =>
  api.get(`/enterprise/governance/${repo_id}`)
export const getGovernanceViolations = (repo_id: string, severity?: string) =>
  api.get(`/enterprise/governance/${repo_id}/violations`, { params: severity ? { severity } : {} })

// Enterprise: Reports
export const getDailyReport = (date?: string) =>
  api.get('/enterprise/reports/daily', { params: date ? { date } : {} })
export const getWeeklyReport = () => api.get('/enterprise/reports/weekly')
export const getMonthlyReport = () => api.get('/enterprise/reports/monthly')

// Enterprise: Sandbox
export const executeSandbox = (code: string, language: string) =>
  api.post('/enterprise/sandbox/execute', { code, language })

// Enterprise: Feature Flags
export const listFeatureFlags = () => api.get('/enterprise/feature-flags')
export const upsertFeatureFlag = (name: string, is_enabled: boolean, rollout_percentage = 100) =>
  api.post(`/enterprise/feature-flags/${name}`, { is_enabled, rollout_percentage })

// Enterprise: LLM Evaluation
export const runLLMEval = (model: string, task_type: string, question: string, answer: string, contexts: string[]) =>
  api.post('/enterprise/eval/run', { model, task_type, question, answer, contexts })
export const getEvalStats = () => api.get('/enterprise/eval/stats')

export default api
