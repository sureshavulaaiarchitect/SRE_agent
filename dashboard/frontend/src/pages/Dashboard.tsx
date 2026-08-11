import { ClusterStats, Incident, ActivityEvent, WsStatus } from '../types'
import { IncidentCard } from '../components/IncidentCard'

interface DashboardProps {
  incidents: Incident[]
  stats: ClusterStats
  activity: ActivityEvent[]
  isLoading: boolean
  wsStatus: WsStatus
  activeIncidents: number
  searchTerm: string
  onSelectIncident: (inc: Incident) => void
  onExecute: (inc: Incident) => void
  onReview: (inc: Incident) => void
  actionLoading: Record<string, boolean>
}

const SkeletonCard = () => (
  <div className="skeleton-card">
    <div className="skeleton" style={{ height: 20, width: '70%' }} />
    <div className="skeleton" style={{ height: 14, width: '40%' }} />
    <div style={{ display: 'flex', gap: 6 }}>
      <div className="skeleton" style={{ height: 22, width: 80, borderRadius: 20 }} />
      <div className="skeleton" style={{ height: 22, width: 90, borderRadius: 20 }} />
    </div>
    <div className="skeleton" style={{ height: 40 }} />
    <div className="skeleton" style={{ height: 36 }} />
    <div style={{ display: 'flex', gap: 8 }}>
      <div className="skeleton" style={{ height: 34, flex: 1 }} />
      <div className="skeleton" style={{ height: 34, flex: 1 }} />
    </div>
  </div>
)

function timeAgo(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

const ACTIVITY_COLORS: Record<string, string> = {
  incident: '#ef4444',
  remediation: '#10b981',
  approval: '#6366f1',
  alert: '#f59e0b',
}
const ACTIVITY_ICONS: Record<string, string> = {
  incident: 'INC',
  remediation: 'FIX',
  approval: 'APR',
  alert: 'ALT',
}

export const Dashboard = ({
  incidents, stats, activity, isLoading, wsStatus,
  activeIncidents, searchTerm, onSelectIncident, onExecute, onReview, actionLoading
}: DashboardProps) => {
  const filtered = incidents.filter(inc =>
    inc.pod_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    inc.namespace.toLowerCase().includes(searchTerm.toLowerCase()) ||
    inc.root_cause.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const healthPct = stats.total_pods > 0
    ? Math.round((stats.healthy_pods / stats.total_pods) * 100)
    : 100

  return (
    <div className="animate-in">
      {/* Page Header */}
      <div className="page-header">
        <h1 className="page-title gradient-text">Operations Overview</h1>
        <p className="page-subtitle">
          Real-time Kubernetes incident monitoring & AI-powered auto-remediation across your clusters.
        </p>
      </div>

      {/* Cluster Health Center */}
      <div className="ops-hub-header">
        <h2 className="ops-hub-title">
          <span style={{ color: 'var(--accent)' }}>◈</span>
          Infrastructure Health
        </h2>
        <div className="ops-hub-badge">Live System Status</div>
      </div>

      <div className="health-center-grid">
        {/* Core Reliability */}
        <div className="health-card">
          <div className="health-card-glow" />
          <div className="health-card-header">
            <span className="health-card-title">Core Reliability</span>
            <div className="health-card-icon" title="Aggregated cluster health">◉</div>
          </div>
          <div className="health-card-main">
            <div className="health-card-value">{healthPct}%</div>
            <div className="health-card-label">Overall Health Score</div>
          </div>
          <div className="health-card-footer">
            <div className="health-status-bar">
              <div 
                className="health-status-fill" 
                style={{ 
                  width: `${healthPct}%`, 
                  background: healthPct > 90 ? 'var(--success)' : healthPct > 70 ? 'var(--warning)' : 'var(--danger)' 
                }} 
              />
            </div>
            <div className="health-meta">
              <span className="health-meta-item">
                <span className="health-meta-dot" style={{ background: 'var(--success)' }} />
                {stats.healthy_pods} Healthy
              </span>
              <span className="health-meta-item">
                <span className="health-meta-dot" style={{ background: 'var(--danger)' }} />
                {stats.failing_pods} Failing
              </span>
            </div>
          </div>
        </div>

        {/* Incident Management */}
        <div className="health-card">
          <div 
            className="health-card-glow" 
            style={{ background: 'radial-gradient(circle, var(--danger-glow) 0%, transparent 70%)' }} 
          />
          <div className="health-card-header">
            <span className="health-card-title">Active Incidents</span>
            <div className="health-card-icon" style={{ color: 'var(--danger)', borderColor: 'var(--danger-glow)' }}>INC</div>
          </div>
          <div className="health-card-main">
            <div className="health-card-value" style={{ color: activeIncidents > 0 ? 'var(--danger)' : 'inherit' }}>
              {activeIncidents}
            </div>
            <div className="health-card-label">Open Investigations</div>
          </div>
          <div className="health-card-footer">
             <div className="mt-2">
               <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                 MTTR Status: <span style={{ color: activeIncidents > 5 ? 'var(--danger)' : 'var(--success)', fontWeight: 600 }}>
                   {activeIncidents > 0 ? (activeIncidents * 4.5).toFixed(1) + 'm' : 'Optimal'}
                 </span>
               </span>
             </div>
          </div>
        </div>

        {/* Resources: CPU */}
        <div className="health-card">
          <div className="health-card-header">
            <span className="health-card-title">CPU Utilization</span>
            <div className="health-card-icon">⬡</div>
          </div>
          <div className="health-card-main">
            <div className="health-card-value">{(stats.cpu_usage || 0).toFixed(1)}%</div>
            <div className="health-card-label">Average Load</div>
          </div>
          <div className="health-card-footer">
            <div className="gauge-container">
               <div className="gauge-track">
                  <div 
                    className="gauge-thumb" 
                    style={{ 
                      left: `${Math.min(stats.cpu_usage || 0, 100)}%`, 
                      background: (stats.cpu_usage || 0) > 80 ? 'var(--danger)' : 'var(--accent)' 
                    }} 
                  />
               </div>
               <div className="health-meta">
                 <span>{stats.total_nodes} Nodes Active</span>
               </div>
            </div>
          </div>
        </div>

        {/* Resources: Memory */}
        <div className="health-card">
          <div className="health-card-header">
            <span className="health-card-title">Memory Allocation</span>
            <div className="health-card-icon">▦</div>
          </div>
          <div className="health-card-main">
            <div className="health-card-value">{(stats.memory_usage || 0).toFixed(1)}%</div>
            <div className="health-card-label">Used / Reserved</div>
          </div>
          <div className="health-card-footer">
            <div className="gauge-container">
               <div className="gauge-track">
                  <div 
                    className="gauge-thumb" 
                    style={{ 
                      left: `${Math.min(stats.memory_usage || 0, 100)}%`, 
                      background: (stats.memory_usage || 0) > 85 ? 'var(--danger)' : 'var(--purple)' 
                    }} 
                  />
               </div>
               <div className="health-meta">
                 <span>{stats.uptime || '99.9%'} System Uptime</span>
               </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="dashboard-grid">
        {/* Incidents Section */}
        <div className="dashboard-main">
          <div className="section-header-compact">
            <h2 className="section-title-main">Recent Incidents</h2>
            {filtered.length > 0 && (
              <span className="section-count">{filtered.length} active</span>
            )}
          </div>

          {isLoading ? (
            <div className="incidents-grid">
              {Array(4).fill(0).map((_, i) => <SkeletonCard key={i} />)}
            </div>
          ) : filtered.length === 0 ? (
            <div className="glass-card empty-dashboard">
              <div className="empty-state">
                <div className="empty-state-icon">OK</div>
                <div className="empty-state-title">All Systems Operational</div>
                <div className="empty-state-text">
                  No active incidents detected. AutoSRE is monitoring your infrastructure in real-time.
                </div>
              </div>
            </div>
          ) : (
            <div className="incidents-grid">
              {filtered.slice(0, 6).map(inc => (
                <IncidentCard
                  key={inc.incident_id}
                  incident={inc}
                  onSelectIncident={() => onSelectIncident(inc)}
                  onExecute={() => onExecute(inc)}
                  onReview={() => onReview(inc)}
                  isLoading={actionLoading[inc.incident_id || inc.id]}
                />
              ))}
            </div>
          )}
        </div>

        {/* Activity Feed Section */}
        <div className="dashboard-side">
          <div className="section-header-compact">
            <h2 className="section-title-main">Live Activity</h2>
            <div className="live-indicator">
              <span className="status-dot connected" style={{ width: 6, height: 6 }} />
              Live
            </div>
          </div>
          
          <div className="section activity-feed-compact">
            <div className="activity-list">
              {activity.length === 0 ? (
                <div className="p-8 text-center text-muted">No recent activity</div>
              ) : (
                activity.slice(0, 15).map(ev => (
                  <div key={ev.id} className="activity-item-compact">
                    <div
                      className="activity-icon-sm"
                      style={{ background: `${ACTIVITY_COLORS[ev.type]}15`, color: ACTIVITY_COLORS[ev.type] }}
                    >
                      {ACTIVITY_ICONS[ev.type]}
                    </div>
                    <div className="activity-body-sm">
                      <div className="activity-msg-sm">{ev.message}</div>
                      <div className="activity-time-sm">{timeAgo(ev.timestamp)}</div>
                    </div>
                  </div>
                ))
              )}
            </div>
            <div className="activity-footer">
              <button className="btn-link">View full audit log →</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
