import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileText, TrendingUp, BarChart3, Calendar } from 'lucide-react'
import { Button } from '../components/ui/Button'
import api from '../services/api'

type ReportType = 'daily' | 'weekly' | 'monthly'

const REPORT_CONFIG = {
  daily: { icon: Calendar, label: 'Daily Report', desc: 'Risks, findings, failed reviews' },
  weekly: { icon: TrendingUp, label: 'Weekly Report', desc: 'Debt trends, cost analytics, productivity' },
  monthly: { icon: BarChart3, label: 'Monthly Executive', desc: 'Executive summary, architecture trends' },
}

function ReportCard({ data }: { data: any }) {
  if (!data) return null
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-4">
      <pre className="text-xs text-gray-700 bg-gray-50 rounded-lg p-4 overflow-auto max-h-96 whitespace-pre-wrap">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  )
}

export default function ReportsPage() {
  const [activeReport, setActiveReport] = useState<ReportType>('daily')

  const { data: dailyData, isLoading: dailyLoading, refetch: refetchDaily } = useQuery({
    queryKey: ['report-daily'],
    queryFn: () => api.get('/enterprise/reports/daily').then(r => r.data),
    enabled: activeReport === 'daily',
  })

  const { data: weeklyData, isLoading: weeklyLoading, refetch: refetchWeekly } = useQuery({
    queryKey: ['report-weekly'],
    queryFn: () => api.get('/enterprise/reports/weekly').then(r => r.data),
    enabled: activeReport === 'weekly',
  })

  const { data: monthlyData, isLoading: monthlyLoading, refetch: refetchMonthly } = useQuery({
    queryKey: ['report-monthly'],
    queryFn: () => api.get('/enterprise/reports/monthly').then(r => r.data),
    enabled: activeReport === 'monthly',
  })

  const activeData = activeReport === 'daily' ? dailyData : activeReport === 'weekly' ? weeklyData : monthlyData
  const isLoading = activeReport === 'daily' ? dailyLoading : activeReport === 'weekly' ? weeklyLoading : monthlyLoading
  const refetch = activeReport === 'daily' ? refetchDaily : activeReport === 'weekly' ? refetchWeekly : refetchMonthly

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Engineering Intelligence Reports</h1>
          <p className="text-gray-500 text-sm mt-1">Automated insights for engineering teams and executives</p>
        </div>
        <Button onClick={() => refetch()} loading={isLoading} className="gap-2">
          <FileText size={14} /> Generate
        </Button>
      </div>

      {/* Report Type Selector */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        {(Object.entries(REPORT_CONFIG) as [ReportType, any][]).map(([type, cfg]) => {
          const Icon = cfg.icon
          return (
            <button
              key={type}
              onClick={() => setActiveReport(type)}
              className={`border rounded-xl p-4 text-left transition-all ${
                activeReport === type
                  ? 'border-indigo-500 bg-indigo-50 ring-1 ring-indigo-500'
                  : 'border-gray-200 bg-white hover:border-indigo-300'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <Icon size={16} className="text-indigo-600" />
                <span className="font-semibold text-sm text-gray-800">{cfg.label}</span>
              </div>
              <p className="text-xs text-gray-500">{cfg.desc}</p>
            </button>
          )
        })}
      </div>

      {isLoading && <div className="text-center py-20 text-gray-400">Generating report...</div>}

      {activeData && (
        <>
          {/* Summary Stats */}
          {activeData.summary && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
              {Object.entries(activeData.summary).map(([key, val]) => (
                <div key={key} className="bg-white border border-gray-200 rounded-xl p-4">
                  <p className="text-xs text-gray-500 capitalize mb-1">{key.replace(/_/g, ' ')}</p>
                  <p className="text-xl font-bold text-gray-900">{String(val)}</p>
                </div>
              ))}
            </div>
          )}

          {/* Full Report */}
          <ReportCard data={activeData} />

          {/* Recommendations */}
          {activeData.recommendations?.length > 0 && (
            <div className="mt-4 bg-green-50 border border-green-200 rounded-xl p-4">
              <p className="font-semibold text-green-800 mb-2">💡 Recommendations</p>
              <ul className="space-y-1">
                {activeData.recommendations.map((r: string, i: number) => (
                  <li key={i} className="text-sm text-green-700">• {r}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  )
}
