import { useState, useEffect } from 'react'
import { useIncidents } from '../hooks/useIncidents'
import { ClusterStats, Cluster } from '../types'

interface ClusterHealthProps {
  clusters: Cluster[]
  stats: ClusterStats
}

export const ClusterHealth = ({ clusters, stats }: ClusterHealthProps) => {
  const [healthData, setHealthData] = useState<Cluster[]>(clusters)
  const { apiUrl } = useIncidents()

  useEffect(() => {
    setHealthData(clusters)
  }, [clusters])

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const authHeader = { 'Authorization': 'Bearer demo-token' }
        const res = await fetch(`${apiUrl}/cluster/status`, { headers: authHeader })
        if (res.ok) {
          const data = await res.json()
          setHealthData([{
            id: data.cluster_id,
            name: 'Local Cluster',
            region: 'internal',
            status: data.failing_pods > 0 ? 'degraded' : 'healthy',
            node_count: data.total_nodes,
            pod_count: data.healthy_pods + data.failing_pods
          }])
        }
      } catch (err) {
        console.error('Cluster status poll failed', err)
      }
    }, 30000)
    return () => clearInterval(interval)
  }, [apiUrl])

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return '#10b981'
      case 'degraded': return '#f59e0b'
      case 'critical': return '#ef4444'
      default: return '#6b7280'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy': return 'OK'
      case 'degraded': return 'WARN'
      case 'critical': return 'CRIT'
      default: return '?'
    }
  }

  return (
    <div className="animate-in">
      <div className="page-header">
        <h1 className="page-title gradient-text">Cluster Health Center</h1>
        <p className="page-subtitle">Real-time observability and deep-dive health status across all registered Kubernetes clusters.</p>
      </div>

      <div className="grid-2xl">
        {/* Health Overview Cards */}
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon" style={{ background: 'var(--accent-glow)', color: 'var(--accent)' }}>NET</div>
            <div className="mt-4">
              <div className="stat-value">{stats.total_pods}</div>
              <div className="stat-label">Total Workloads</div>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon" style={{ background: 'var(--success-glow)', color: 'var(--success)' }}>OK</div>
            <div className="mt-4">
              <div className="stat-value">{stats.healthy_pods}</div>
              <div className="stat-label">Healthy Pods</div>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon" style={{ background: 'var(--warning-glow)', color: 'var(--warning)' }}>WARN</div>
            <div className="mt-4">
              <div className="stat-value">{stats.failing_pods}</div>
              <div className="stat-label">Critical / Failing</div>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon" style={{ background: 'var(--info-glow)', color: 'var(--info)' }}>ALT</div>
            <div className="mt-4">
              <div className="stat-value">{stats.active_incidents}</div>
              <div className="stat-label">Active Alerts</div>
            </div>
          </div>
        </div>

        {/* Cluster Status Table */}
        <div className="section">
          <div className="section-header">
            <div className="section-title">
              <span className="section-title-icon">☸</span>
              Registered Clusters
            </div>
            <button className="btn btn-primary btn-sm">+ Add New Cluster</button>
          </div>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Cluster Name</th>
                  <th>Status</th>
                  <th>Nodes</th>
                  <th>Workloads</th>
                  <th>Region</th>
                  <th>Health Score</th>
                </tr>
              </thead>
              <tbody>
                {healthData.map(cluster => (
                  <tr key={cluster.id}>
                    <td>
                      <div>
                        <div style={{ fontWeight: 700, color: 'var(--text)' }}>{cluster.name}</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace' }}>{cluster.id}</div>
                      </div>
                    </td>
                    <td>
                      <span className={`badge ${cluster.status === 'healthy' ? 'badge-success' : 'badge-warning'}`}>
                        {getStatusIcon(cluster.status)} {cluster.status.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ fontWeight: 600 }}>{cluster.node_count}</td>
                    <td style={{ fontWeight: 600 }}>{cluster.pod_count}</td>
                    <td><span className="badge badge-neutral">{cluster.region}</span></td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div className="progress-bar" style={{ flex: 1, width: 60, height: 6 }}>
                          <div 
                            className="progress-fill" 
                            style={{ 
                              width: `${cluster.status === 'healthy' ? 100 : 75}%`, 
                              background: cluster.status === 'healthy' ? 'var(--success)' : 'var(--warning)',
                              height: '100%',
                              borderRadius: 4
                            }} 
                          />
                        </div>
                        <span style={{ fontSize: '0.75rem', fontWeight: 700 }}>{cluster.status === 'healthy' ? '100%' : '75%'}</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recent Alerts */}
        <div className="section" style={{ marginTop: 24 }}>
          <div className="section-header">
            <div className="section-title">
              <span className="section-title-icon">ALT</span>
              System-wide Alerts
            </div>
          </div>
          <div className="alerts-list" style={{ padding: '8px 0' }}>
            <div className="activity-item" style={{ borderBottom: '1px solid var(--border)' }}>
              <div className="activity-icon" style={{ background: 'var(--danger-glow)', color: 'var(--danger)' }}>CRIT</div>
              <div className="activity-body">
                <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>Production CPU Threshold Exceeded</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>production-cluster-us-east • 2 minutes ago</div>
              </div>
              <button className="btn btn-ghost btn-sm">Investigate</button>
            </div>
            <div className="activity-item">
              <div className="activity-icon" style={{ background: 'var(--warning-glow)', color: 'var(--warning)' }}>WARN</div>
              <div className="activity-body">
                <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>Staging Memory Pressure Detected</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>staging-cluster-internal • 5 minutes ago</div>
              </div>
              <button className="btn btn-ghost btn-sm">Dismiss</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

