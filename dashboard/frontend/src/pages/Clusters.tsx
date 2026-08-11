import { Cluster } from '../types'

interface ClustersProps {
  clusters: Cluster[]
}

const STATUS_STYLES: Record<string, { color: string; badge: string; icon: string }> = {
  healthy: { color: '#10b981', badge: 'badge-success', icon: '◉' },
  degraded: { color: '#f59e0b', badge: 'badge-warning', icon: '◎' },
  critical: { color: '#ef4444', badge: 'badge-danger', icon: '⊗' },
}

export const ClustersPage = ({ clusters }: ClustersProps) => {
  return (
    <div>
      <div className="page-header" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
        <div>
          <h1 className="page-title gradient-text">Clusters</h1>
          <p className="page-subtitle">Monitor and manage all Kubernetes clusters</p>
        </div>
        <button className="btn btn-accent">+ Add Cluster</button>
      </div>

      {/* Summary stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
        {[
          { label: 'Total Clusters', val: clusters.length, color: '#6366f1', icon: '◈' },
          { label: 'Healthy', val: clusters.filter(c => c.status === 'healthy').length, color: '#10b981', icon: '◉' },
          { label: 'Needs Attention', val: clusters.filter(c => c.status !== 'healthy').length, color: '#f59e0b', icon: 'WARN' },
        ].map(s => (
          <div key={s.label} className="glass-card" style={{ padding: 18, display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{
              width: 40, height: 40, borderRadius: 10,
              background: `${s.color}20`, color: s.color,
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.1rem',
            }}>{s.icon}</div>
            <div>
              <div style={{ fontSize: '1.5rem', fontWeight: 800, color: s.color }}>{s.val}</div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{s.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Cluster cards */}
      <div className="cluster-grid">
        {clusters.map(cluster => {
          const style = STATUS_STYLES[cluster.status]
          return (
            <div key={cluster.id} className="cluster-card animate-in">
              <div className="cluster-header">
                <div className="cluster-icon">☸</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="cluster-name">{cluster.name}</div>
                  <div className="cluster-region">{cluster.region}</div>
                </div>
                <div className="cluster-status">
                  <span className={`badge ${style.badge}`} style={{ fontSize: '0.65rem' }}>
                    {style.icon} {cluster.status}
                  </span>
                </div>
              </div>

              {/* Metrics */}
              <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 4 }}>Node Usage</div>
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width: `${Math.min((cluster.node_count / 15) * 100, 100)}%`, background: style.color }} />
                  </div>
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 4 }}>Pod Usage</div>
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width: `${Math.min((cluster.pod_count / 120) * 100, 100)}%`, background: style.color }} />
                  </div>
                </div>
              </div>

              <div className="cluster-stats">
                <div className="cluster-stat-item">
                  <div className="cluster-stat-value" style={{ color: style.color }}>{cluster.node_count}</div>
                  <div className="cluster-stat-label">Nodes</div>
                </div>
                <div className="cluster-stat-item">
                  <div className="cluster-stat-value">{cluster.pod_count}</div>
                  <div className="cluster-stat-label">Pods</div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8, marginTop: 14, paddingTop: 14, borderTop: '1px solid var(--border)' }}>
                <button className="btn btn-secondary btn-sm" style={{ flex: 1 }}>Metrics</button>
                <button className="btn btn-ghost btn-sm" style={{ flex: 1 }}>Connect</button>
              </div>
            </div>
          )
        })}
      </div>

      {/* Table view */}
      <div className="section" style={{ marginTop: 24 }}>
        <div className="section-header">
          <span className="section-title">
            <span className="section-title-icon" style={{'--icon-bg': 'rgba(99,102,241,0.15)', '--icon-color': 'var(--accent)'} as any}>◈</span>
            All Clusters
          </span>
          <button className="btn btn-secondary btn-sm">↻ Refresh</button>
        </div>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Cluster</th>
                <th>Region</th>
                <th>Status</th>
                <th>Nodes</th>
                <th>Pods</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {clusters.map(c => {
                const s = STATUS_STYLES[c.status]
                return (
                  <tr key={c.id}>
                    <td style={{ fontWeight: 600, color: 'var(--text)' }}>{c.name}</td>
                    <td>{c.region}</td>
                    <td><span className={`badge ${s.badge}`} style={{ fontSize: '0.65rem' }}>{s.icon} {c.status}</span></td>
                    <td>{c.node_count}</td>
                    <td>{c.pod_count}</td>
                    <td>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button className="btn btn-secondary btn-sm">View</button>
                        <button className="btn btn-ghost btn-sm">Edit</button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
