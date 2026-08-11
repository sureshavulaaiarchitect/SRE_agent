import { Incident } from '../types'
import { useState, useEffect } from 'react'
import { useIncidents } from '../hooks/useIncidents'

interface IncidentModalProps {
  incident: Incident | null
  onClose: () => void
  onApprove: (inc: Incident) => void
  onReject: (inc: Incident) => void
}

interface ActivityTimeline {
  event: string
  time: string
  message: string
  severity: string
}

function timeAgo(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

const CONFIDENCE_COLOR: Record<string, string> = {
  high: '#f87171',
  medium: '#fbbf24',
  low: '#64748b',
}

const TYPE_LABEL: Record<string, string> = {
  pod_crashloop: 'CrashLoopBackOff',
  image_pull_error: 'ImagePullError',
  oom_killed: 'OOMKilled',
  pending_pod: 'PodPending',
  config_error: 'ConfigError',
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

export const IncidentModal = ({ incident, onClose, onApprove, onReject }: IncidentModalProps) => {
  const [timeline, setTimeline] = useState<ActivityTimeline[]>([])
  const { apiUrl } = useIncidents()

  useEffect(() => {
    if (!incident) return
    const fetchTimeline = async () => {
      try {
        const res = await fetch(`${apiUrl}/incident/${incident.incident_id}/activity`, {
          headers: { 'Authorization': 'Bearer demo-token' }
        })
        if (res.ok) {
          const data = await res.json()
          setTimeline(data.timeline || [])
        }
      } catch (err) {
        console.error('Failed to fetch timeline', err)
      }
    }
    fetchTimeline()
  }, [incident, apiUrl])

  if (!incident) return null

  const cmds = incident.recommended_action.split('\n').filter(Boolean)

  return (
    <div
      className="modal-overlay animate-in"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div style={{ flex: 1 }}>
            <div className="modal-title" id="modal-title">{incident.pod_name}</div>
            <div className="modal-subtitle">
              namespace: <strong style={{ color: 'var(--text-dim)' }}>{incident.namespace}</strong>
              &nbsp;•&nbsp;{timeAgo(incident.created_at)}
              &nbsp;•&nbsp;<span style={{ opacity: 0.7 }}>{new Date(incident.created_at).toLocaleString()}</span>
            </div>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close modal">✕</button>
        </div>

        {/* Body */}
        <div className="modal-body">
          {/* Badges row */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 28 }}>
            <span className="badge badge-info" style={{ padding: '6px 14px' }}>
              {TYPE_LABEL[incident.incident_type] || incident.incident_type.replace(/_/g, ' ')}
            </span>
            <span
              className="badge"
              style={{
                background: `${CONFIDENCE_COLOR[incident.confidence]}15`,
                borderColor: `${CONFIDENCE_COLOR[incident.confidence]}35`,
                color: CONFIDENCE_COLOR[incident.confidence],
                padding: '6px 14px'
              }}
            >
              {incident.confidence?.toUpperCase()} CONFIDENCE
            </span>
            <span className="badge badge-purple" style={{ padding: '6px 14px' }}>{incident.source || 'hybrid'}</span>
            <span 
              className="badge"
              style={{ 
                padding: '6px 14px',
                backgroundColor: STATUS_COLORS[incident.status] || 'var(--neutral)',
                color: 'white'
              }}
            >
              {(incident.status || 'detected').toUpperCase().replace('_', ' ')}
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 24 }}>
            {/* Findings Section */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              {/* Rule Finding */}
              <section className="diagnostic-section" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 16 }}>
                <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase', marginBottom: 8 }}>
                  Rule Engine Result
                </div>
                <div style={{ fontSize: '0.9rem', color: 'var(--text-dim)' }}>
                  {incident.root_cause || 'Pattern analysis complete'}
                </div>
              </section>

              {/* AI Finding */}
              <section className="diagnostic-section" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 16 }}>
                <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--secondary)', textTransform: 'uppercase', marginBottom: 8 }}>
                  AI Engine Result
                </div>
                <div style={{ fontSize: '0.9rem', color: 'var(--text-dim)' }}>
                  {incident.explanation || 'Root cause analyzed by LLM'}
                </div>
              </section>
            </div>

            {/* Resolved Decision & Recommendation */}
            <section className="final-decision" style={{ background: 'var(--surface-alt)', padding: 20, borderRadius: 'var(--radius)', border: '1px solid var(--accent-light)' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 12 }}>
                Final Decision
              </div>
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>
                  {incident.recommended_action?.replace(/_/g, ' ') || 'Manual Investigation'}
                </div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                  Proposed Action based on {incident.confidence} confidence analysis
                </div>
              </div>
              
              <div className="code-block" style={{ border: '1px solid var(--border)', background: '#000', borderRadius: 'var(--radius-sm)' }}>
                <div className="code-header" style={{ padding: '8px 12px', background: '#111', borderBottom: '1px solid #222', display: 'flex', justifyContent: 'space-between' }}>
                  <span className="code-lang" style={{ fontSize: '0.7rem', color: '#555' }}>remediation command</span>
                </div>
                <div style={{ padding: '12px', fontFamily: 'JetBrains Mono, monospace', fontSize: '0.85rem', color: '#fff' }}>
                  <span style={{ color: 'var(--accent)', marginRight: 8 }}>$</span>
                  sentinelops execute --action {incident.recommended_action} --pod {incident.pod_name}
                </div>
              </div>
            </section>

            {/* Activity Timeline */}
            <section>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 10 }}>
                Timeline
              </div>
              <div style={{ maxHeight: '200px', overflow: 'auto', background: 'var(--bg-secondary)', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                {timeline.length === 0 ? (
                  <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '24px' }}>Loading timeline...</p>
                ) : (
                  <div>
                    {timeline.map((activity, index) => (
                      <div key={index} style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '10px 16px', borderBottom: index < timeline.length - 1 ? '1px solid var(--border)' : 'none' }}>
                        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', minWidth: '60px' }}>{new Date(activity.time).toLocaleTimeString()}</span>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: 'var(--text)' }}>{activity.event}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{activity.message}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>
          </div>
        </div>

        {/* Footer */}
        <div className="modal-footer" style={{ gap: 12 }}>
          {incident.status === 'awaiting_approval' ? (
            <>
              <button
                className="btn btn-primary btn-lg"
                style={{ flex: 2 }}
                onClick={() => onApprove(incident)}
              >
                Approve Remediation
              </button>
              <button
                className="btn btn-secondary btn-lg"
                style={{ flex: 1 }}
                onClick={() => onReject(incident)}
              >
                Reject
              </button>
            </>
          ) : (
            <button className="btn btn-ghost btn-lg" style={{ width: '100%' }} onClick={onClose}>Close</button>
          )}
        </div>
      </div>
    </div>
  )
}
