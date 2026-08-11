import { ActivityEvent } from '../types'

interface ActivityPageProps {
  activity: ActivityEvent[]
}

function timeAgo(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

const TYPE_META: Record<string, { icon: string; color: string; label: string }> = {
  incident: { icon: 'INC', color: '#ef4444', label: 'Incident' },
  remediation: { icon: 'FIX', color: '#10b981', label: 'Remediation' },
  approval: { icon: 'APR', color: '#6366f1', label: 'Approval' },
  alert: { icon: 'ALT', color: '#f59e0b', label: 'Alert' },
}

const SEV_BADGE: Record<string, string> = {
  critical: 'badge-danger',
  high: 'badge-warning',
  medium: 'badge-info',
  low: 'badge-neutral',
}

export const ActivityPage = ({ activity }: ActivityPageProps) => {
  return (
    <div>
      <div className="page-header">
        <h1 className="page-title gradient-text">Activity Feed</h1>
        <p className="page-subtitle">Full audit log of all agent actions, remediations, and alerts</p>
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 24 }}>
        {Object.entries(TYPE_META).map(([type, meta]) => {
          const count = activity.filter(a => a.type === type).length
          return (
            <div key={type} className="glass-card" style={{ padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                <div style={{
                  width: 32, height: 32, borderRadius: 8,
                  background: `${meta.color}20`, color: meta.color,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '1rem'
                }}>{meta.icon}</div>
                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600 }}>{meta.label}</span>
              </div>
              <div style={{ fontSize: '1.75rem', fontWeight: 800, color: meta.color }}>{count}</div>
            </div>
          )
        })}
      </div>

      {/* Timeline */}
      <div className="section">
        <div className="section-header">
          <span className="section-title">
            <span className="section-title-icon" style={{'--icon-bg': 'rgba(99,102,241,0.15)', '--icon-color': 'var(--accent)'} as any}>◉</span>
            Event Timeline
          </span>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            {activity.length} events
          </span>
        </div>

        <div style={{ padding: '8px 0', position: 'relative' }}>
          {/* Timeline line */}
          <div style={{
            position: 'absolute',
            left: 36,
            top: 0,
            bottom: 0,
            width: 1,
            background: 'var(--border)',
            pointerEvents: 'none'
          }} />

          {activity.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">-</div>
              <div className="empty-state-title">No activity yet</div>
              <div className="empty-state-text">Events will appear here as the agent acts.</div>
            </div>
          ) : (
            activity.map((ev, idx) => {
              const meta = TYPE_META[ev.type] || { icon: '•', color: 'var(--text-muted)', label: ev.type }
              return (
                <div key={ev.id} className="activity-item" style={{ gap: 16, padding: '14px 20px' }}>
                  {/* Icon */}
                  <div style={{
                    width: 32, height: 32,
                    borderRadius: 8,
                    background: `${meta.color}20`,
                    color: meta.color,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: '0.85rem',
                    flexShrink: 0,
                    zIndex: 1,
                    border: `1px solid ${meta.color}40`,
                  }}>{meta.icon}</div>

                  {/* Body */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: '0.72rem', color: meta.color, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                        {meta.label}
                      </span>
                      <span className={`badge ${SEV_BADGE[ev.severity] || 'badge-neutral'}`} style={{ fontSize: '0.6rem' }}>
                        {ev.severity}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.86rem', color: 'var(--text-dim)', lineHeight: 1.5 }}>{ev.message}</div>
                  </div>

                  {/* Time */}
                  <div style={{ textAlign: 'right', flexShrink: 0 }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{timeAgo(ev.timestamp)}</div>
                    <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', opacity: 0.7 }}>
                      {new Date(ev.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}
