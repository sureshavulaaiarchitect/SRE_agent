import { useState } from 'react'
import { Incident } from '../types'

interface RemediationQueueProps {
  incidents: Incident[]
  onApprove: (inc: Incident) => void
  onReject: (inc: Incident) => void
  actionLoading: Record<string, boolean>
}

export const RemediationQueue = ({ incidents, onApprove, onReject, actionLoading }: RemediationQueueProps) => {

  const approveAction = (incident: Incident) => {
    onApprove(incident)
  }

  const rejectAction = (incident: Incident) => {
    onReject(incident)
  }

  return (
    <div className="animate-in">
      <div className="page-header">
        <h1 className="page-title gradient-text">Remediation Queue</h1>
        <p className="page-subtitle">Manual approval required for high-impact or low-confidence autonomous actions.</p>
      </div>

      <div className="grid-xl">
        {/* Queue Stats */}
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon" style={{ color: 'var(--accent)' }}>Q</div>
            <div className="mt-4">
              <div className="stat-value">{incidents.length}</div>
              <div className="stat-label">Pending Approval</div>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon" style={{ color: 'var(--success)' }}>OK</div>
            <div className="mt-4">
              <div className="stat-value">0</div>
              <div className="stat-label">Auto-Resolved</div>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon" style={{ color: 'var(--warning)' }}>...</div>
            <div className="mt-4">
              <div className="stat-value">{incidents.length}</div>
              <div className="stat-label">Awaiting Review</div>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon" style={{ color: 'var(--danger)' }}>X</div>
            <div className="mt-4">
              <div className="stat-value">0</div>
              <div className="stat-label">Blocked Actions</div>
            </div>
          </div>
        </div>

        {/* Remediation Items */}
        <div className="section full-width">
          <div className="section-header">
            <div className="section-title">
              <span className="section-title-icon">CFG</span>
              Approval Required
            </div>
            <div className="section-actions" style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-secondary btn-sm">Bulk Approve</button>
              <button className="btn btn-ghost btn-sm">Queue Settings</button>
            </div>
          </div>

          <div className="remediation-list" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
            {incidents.map((item) => (
              <div key={item.incident_id} className="glass-card remediation-card-hover" style={{ padding: 24, borderLeft: '4px solid var(--warning)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 20, flexWrap: 'wrap' }}>
                  <div style={{ flex: 1, minWidth: 300 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                      <span className={`badge ${item.confidence === 'high' ? 'badge-danger' : 'badge-warning'}`}>
                        {item.confidence.toUpperCase()} CONFIDENCE
                      </span>
                      <span className="badge badge-info">{item.incident_type}</span>
                    </div>
                    <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text)', marginBottom: 4 }}>{item.root_cause}</h3>
                    <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', display: 'flex', gap: 12 }}>
                      <span>Namespace: <strong>{item.namespace}</strong></span>
                      <span>Pod: <strong>{item.pod_name}</strong></span>
                      <span>Time: <strong>{new Date(item.created_at).toLocaleString()}</strong></span>
                    </div>
                  </div>
                  
                  <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                    <div className="badge badge-warning" style={{ alignSelf: 'flex-end', marginBottom: 8 }}>Awaiting Approval</div>
                  </div>
                </div>

                <div style={{ marginTop: 20, padding: 16, background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', gap: 16 }}>
                    <div style={{ width: 40, height: 40, background: 'rgba(16,185,129,0.1)', color: 'var(--success)', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.8rem', flexShrink: 0 }}>FIX</div>
                    <div>
                      <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>Proposed Remediation</div>
                      <code style={{ fontSize: '0.9rem', color: 'var(--success)', fontFamily: 'JetBrains Mono, monospace' }}>{item.recommended_action}</code>
                      <p style={{ fontSize: '0.85rem', color: 'var(--text-dim)', marginTop: 8 }}>{item.explanation}</p>
                    </div>
                  </div>
                </div>

                <div style={{ marginTop: 20, display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
                  <button 
                    className="btn btn-ghost" 
                    onClick={() => rejectAction(item)}
                    disabled={actionLoading[item.incident_id || item.id]}
                  >
                    {actionLoading[item.incident_id || item.id] ? <span className="spinner-sm" /> : 'Reject Action'}
                  </button>
                  <button 
                    className="btn btn-primary"
                    onClick={() => approveAction(item)}
                    disabled={actionLoading[item.incident_id || item.id]}
                  >
                    {actionLoading[item.incident_id || item.id] ? <span className="spinner-sm" /> : 'Approve & Execute Fix'}
                  </button>
                </div>
              </div>
            ))}

            {incidents.length === 0 && (
              <div className="empty-state" style={{ padding: '60px 0' }}>
                <div style={{ fontSize: '2rem', marginBottom: 16 }}>OK</div>
                <h3 className="empty-state-title">No Pending Remediations</h3>
                <p className="empty-state-text">All incidents are currently healthy or have been auto-resolved.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
