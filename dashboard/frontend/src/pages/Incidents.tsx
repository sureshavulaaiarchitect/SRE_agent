import { useState } from 'react'
import { Incident } from '../types'
import { IncidentCard } from '../components/IncidentCard'

interface IncidentsProps {
  incidents: Incident[]
  isLoading: boolean
  searchTerm: string
  onSelectIncident: (inc: Incident) => void
  onExecute: (inc: Incident) => void
  onReview: (inc: Incident) => void
  onDismiss: (id: string) => void
  actionLoading: Record<string, boolean>
}

type FilterType = 'all' | 'active' | 'pending' | 'resolved'
type ViewMode = 'grid' | 'table'

function timeAgo(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

const TYPE_LABEL: Record<string, string> = {
  pod_crashloop: 'CrashLoop',
  image_pull_error: 'ImagePull',
  oom_killed: 'OOMKilled',
  pending_pod: 'Pending',
  config_error: 'ConfigErr',
}

const STATUS_COLORS: Record<string, string> = {
  investigating: 'var(--accent)',
  awaiting_approval: 'var(--warning)',
  executing: 'var(--secondary)',
  resolved: 'var(--success)',
  failed: 'var(--danger)',
  analyzed: 'var(--info)',
  detected: 'var(--neutral)'
}

export const IncidentsPage = ({
  incidents, isLoading, searchTerm,
  onSelectIncident, onExecute, onReview, onDismiss, actionLoading
}: IncidentsProps) => {
  const [filter, setFilter] = useState<FilterType>('all')
  const [view, setView] = useState<ViewMode>('table')
  const [sortBy, setSortBy] = useState<'time' | 'confidence'>('time')

  const filtered = incidents
    .filter(inc => {
      const matchSearch =
        inc.pod_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        inc.namespace.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (inc.root_cause || '').toLowerCase().includes(searchTerm.toLowerCase())
      const matchFilter = filter === 'all' || inc.status === filter
      return matchSearch && matchFilter
    })
    .sort((a, b) => {
      if (sortBy === 'confidence') {
        const order = { high: 0, medium: 1, low: 2 }
        return (order[a.confidence as keyof typeof order] ?? 3) - (order[b.confidence as keyof typeof order] ?? 3)
      }
      return new Date(b.created_at || b.timestamp).getTime() - new Date(a.created_at || a.timestamp).getTime()
    })

  const counts = {
    all: incidents.length,
    active: incidents.filter(i => ['investigating', 'awaiting_approval', 'executing', 'detected', 'analyzed'].includes(i.status)).length,
    pending: incidents.filter(i => i.status === 'awaiting_approval').length,
    resolved: incidents.filter(i => i.status === 'resolved').length,
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
        <div className="skeleton" style={{ flex: 1, height: 34 }} />
        <div className="skeleton" style={{ flex: 1, height: 34 }} />
      </div>
    </div>
  )

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <h1 className="page-title gradient-text">Incidents</h1>
        <p className="page-subtitle">{filtered.length} incident{filtered.length !== 1 ? 's' : ''} found — AI-powered root cause &amp; remediation</p>
      </div>

      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
        {/* Filters */}
        <div style={{ display: 'flex', gap: 6, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 4 }}>
          {(['all', 'active', 'pending', 'resolved'] as FilterType[]).map(f => (
            <button
              key={f}
              className={`btn btn-sm ${filter === f ? 'btn-accent' : 'btn-ghost'}`}
              style={{ textTransform: 'capitalize' }}
              onClick={() => setFilter(f)}
            >
              {f} {counts[f] > 0 && <span style={{ fontSize: '0.65rem', opacity: 0.8 }}>({counts[f]})</span>}
            </button>
          ))}
        </div>

        {/* Sort */}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <select
            className="form-input"
            style={{ width: 'auto', fontSize: '0.8rem', padding: '6px 12px' }}
            value={sortBy}
            onChange={e => setSortBy(e.target.value as 'time' | 'confidence')}
          >
            <option value="time">Sort: Newest</option>
            <option value="confidence">Sort: Confidence</option>
          </select>

          {/* View toggle */}
          <div style={{ display: 'flex', gap: 4, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: 3 }}>
            <button
              className={`btn btn-sm ${view === 'grid' ? 'btn-accent' : 'btn-ghost'}`}
              onClick={() => setView('grid')}
              title="Grid view"
            >⊞</button>
            <button
              className={`btn btn-sm ${view === 'table' ? 'btn-accent' : 'btn-ghost'}`}
              onClick={() => setView('table')}
              title="Table view"
            >≡</button>
          </div>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="incidents-grid">
          {Array(6).fill(0).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="section">
          <div className="empty-state">
            <div className="empty-state-icon">OK</div>
            <div className="empty-state-title">No incidents found</div>
            <div className="empty-state-text">
              {searchTerm ? `No results for "${searchTerm}"` : 'All systems are healthy. Great job!'}
            </div>
          </div>
        </div>
      ) : view === 'grid' ? (
        <div className="incidents-grid">
          {filtered.map(inc => (
            <IncidentCard
              key={inc.id || inc.incident_id}
              incident={inc}
              onSelectIncident={() => onSelectIncident(inc)}
              onExecute={() => onExecute(inc)}
              onReview={() => onReview(inc)}
              isLoading={actionLoading[inc.id || inc.incident_id]}
            />
          ))}
        </div>
      ) : (
        /* Table view */
        <div className="section">
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Pod</th>
                  <th>Namespace</th>
                  <th>Status</th>
                  <th>Confidence</th>
                  <th>Action</th>
                  <th>Time</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(inc => (
                  <tr
                    key={inc.id || inc.incident_id}
                    onClick={() => onSelectIncident(inc)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td>
                      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.8rem', color: 'var(--text)' }}>
                        {inc.pod_name}
                      </span>
                    </td>
                    <td><span className="badge badge-neutral" style={{ fontSize: '0.65rem' }}>{inc.namespace}</span></td>
                    <td>
                      <span 
                        className="badge" 
                        style={{ 
                          fontSize: '0.65rem',
                          backgroundColor: STATUS_COLORS[inc.status] || 'var(--neutral)',
                          color: 'white',
                          textTransform: 'uppercase',
                          fontWeight: 'bold'
                        }}
                      >
                        {inc.status?.replace('_', ' ') || 'detected'}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${inc.confidence === 'high' ? 'badge-danger' : inc.confidence === 'medium' ? 'badge-warning' : 'badge-neutral'}`} style={{ fontSize: '0.65rem' }}>
                        {inc.confidence}
                      </span>
                    </td>
                    <td style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>
                      {inc.recommended_action || 'Pending'}
                    </td>
                    <td style={{ color: 'var(--text-muted)', fontSize: '0.78rem', whiteSpace: 'nowrap' }}>
                      {timeAgo(inc.created_at || inc.timestamp || new Date().toISOString())}
                    </td>
                    <td onClick={e => e.stopPropagation()}>
                      <div style={{ display: 'flex', gap: 6 }}>
                        {inc.status === 'awaiting_approval' && (
                          <button 
                            className="btn btn-primary btn-sm" 
                            onClick={() => onExecute(inc)}
                            disabled={actionLoading[inc.id || inc.incident_id]}
                          >
                            {actionLoading[inc.id || inc.incident_id] ? <span className="spinner-sm" /> : 'Approve'}
                          </button>
                        )}
                        <button 
                          className="btn btn-secondary btn-sm" 
                          onClick={() => onReview(inc)}
                          disabled={actionLoading[inc.id || inc.incident_id]}
                        >
                          {actionLoading[inc.id || inc.incident_id] ? <span className="spinner-sm" /> : 'Review'}
                        </button>
                        <button className="btn btn-ghost btn-sm" onClick={() => onDismiss(inc.id || inc.incident_id)}>✕</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
