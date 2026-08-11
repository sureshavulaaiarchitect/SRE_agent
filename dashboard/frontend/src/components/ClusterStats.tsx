import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'
import { FaChartLine } from 'react-icons/fa'
import { ClusterStats as ClusterStatsType } from '../types'

interface ClusterStatsProps {
  stats: ClusterStatsType
}

const pieData = (stats: ClusterStatsType) => [
  { name: 'Healthy', value: stats.healthy_pods, color: '#10b981' },
  { name: 'Failing', value: stats.failing_pods, color: '#ef4444' }
]

export const ClusterStats = ({ stats }: ClusterStatsProps) => (
  <div className="glass-card lg:col-span-2 xl:col-span-2 p-8 animate-slide-up">
    <div className="flex items-center gap-4 mb-8">
      <FaChartLine className="text-2xl text-blue-400" />
      <h3 className="text-2xl font-bold text-slate-200">Cluster Health</h3>
    </div>
    <ResponsiveContainer width="100%" height={350}>
      <PieChart>
        <Pie
          data={pieData(stats)}
          cx="50%"
          cy="50%"
          outerRadius={100}
          innerRadius={60}
          dataKey="value"
          isAnimationActive={true}
          animationDuration={1500}
        >
          {pieData(stats).map((entry, index) => (
            <Cell key={`cell-${index}`} fill={entry.color} />
          ))}
        </Pie>
        <Tooltip />
      </PieChart>
    </ResponsiveContainer>
    <div className="grid grid-cols-2 gap-6 mt-8 pt-8 border-t border-slate-800/30">
      <div className="text-center p-6 rounded-2xl hover:bg-emerald-500/10 transition-colors">
        <div className="text-4xl font-bold text-emerald-400">{stats.healthy_pods}</div>
        <div className="text-emerald-300 mt-1">Healthy Pods</div>
      </div>
      <div className="text-center p-6 rounded-2xl hover:bg-red-500/10 transition-colors">
        <div className="text-4xl font-bold text-red-400">{stats.failing_pods}</div>
        <div className="text-red-300 mt-1">Failing Pods</div>
      </div>
    </div>
  </div>
)

