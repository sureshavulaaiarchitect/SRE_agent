import { Incident } from '../types'

interface IncidentCardProps {
  incident: Incident
  onSelectIncident: () => void
  onExecute: () => void
  onReview: () => void
  isLoading?: boolean
}

const TYPE_LABEL: Record<string, string> = {
  pod_crashloop: 'CrashLoop',
  image_pull_error: 'ImagePull',
  oom_killed: 'OOMKilled',
  pending_pod: 'Pending',
  config_error: 'ConfigErr',
}

const CONFIDENCE_BADGE: Record<string, string> = {
  high: 'badge-danger',
  medium: 'badge-warning',
  low: 'badge-neutral',
}

const TYPE_BADGE: Record<string, string> = {
  pod_crashloop: 'badge-danger',
  image_pull_error: 'badge-warning',
  oom_killed: 'badge-danger',
  pending_pod: 'badge-warning',
  config_error: 'badge-warning',
}

const STATUS_BADGE: Record<string, string> = {
  active: 'badge-danger',
  pending: 'badge-warning',
  resolved: 'badge-success',
}

function timeAgo(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

export const IncidentCard = ({ incident, onSelectIncident, onExecute, onReview, isLoading }: IncidentCardProps) => {
  const typeBadge = TYPE_BADGE[incident.incident_type] || 'badge-neutral'
  const confBadge = CONFIDENCE_BADGE[incident.confidence] || 'badge-neutral'
  const statusBadge = STATUS_BADGE[incident.status || 'active'] || 'badge-neutral'

  return (
    <div
      className="incident-card animate-in"
      onClick={onSelectIncident}
      role="button"
      tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && onSelectIncident()}
      aria-label={`Incident: ${incident.pod_name}`}
    >
      {/* Header */}
      <div className="incident-card-header">
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="incident-pod-name">{incident.pod_name}</div>
          <div className="incident-namespace">ns: <strong>{incident.namespace}</strong></div>
        </div>
        <div className="incident-time">{timeAgo(incident.created_at)}</div>
      </div>

      {/* Badges */}
      <div className="incident-badges">
        <span className={`badge ${typeBadge}`}>
          {TYPE_LABEL[incident.incident_type] || incident.incident_type.replace(/_/g, ' ')}
        </span>
        <span className={`badge ${confBadge}`}>
          {incident.confidence}
        </span>
        <span className={`badge ${statusBadge}`}>
          {incident.status || 'active'}
        </span>
      </div>

      {/* Root cause */}
      <div className="incident-root-cause-wrapper" style={{ flex: 1 }}>
        <p className="incident-root-cause" style={{ fontSize: '0.85rem', color: 'var(--text-dim)', margin: 0 }}>
          {incident.root_cause}
        </p>
      </div>

      {/* Recommended action */}
      <div className="incident-cmd" title={incident.recommended_action}>
        <span style={{ opacity: 0.5, marginRight: 4 }}>$</span>
        {incident.recommended_action.split('\n')[0]}
      </div>

      {/* Action buttons */}
      <div className="incident-actions" onClick={e => e.stopPropagation()}>
        <button
          id={`execute-${incident.incident_id}`}
          className="btn btn-primary btn-sm"
          style={{ flex: 1, padding: '8px' }}
          onClick={e => { e.stopPropagation(); onExecute(); }}
          disabled={isLoading || ['executing', 'resolved'].includes(incident.status)}
          title="Execute auto-fix for this incident"
        >
          {isLoading ? <span className="spinner-sm" /> : (incident.status === 'executing' ? 'Fixing...' : 'Fix')}
        </button>
        <button
          id={`review-${incident.incident_id}`}
          className="btn btn-secondary btn-sm"
          style={{ flex: 1, padding: '8px' }}
          onClick={e => { e.stopPropagation(); onReview(); }}
          disabled={isLoading || ['executing', 'resolved'].includes(incident.status)}
          title="Queue for human review"
        >
          {isLoading ? <span className="spinner-sm" /> : 'Review'}
        </button>
      </div>
    </div>
  )
}
