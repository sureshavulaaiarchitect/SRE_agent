import { Playbook } from '../types'

interface PlaybooksProps {
  playbooks: Playbook[]
  onExecute: (name: string, namespace: string, podName: string) => void
}

const TRIGGER_BADGE: Record<string, string> = {
  pod_crashloop: 'badge-danger',
  image_pull_error: 'badge-warning',
  oom_killed: 'badge-danger',
  pending_pod: 'badge-warning',
  config_error: 'badge-warning',
  deployment_failure: 'badge-info',
}

export const PlaybooksPage = ({ playbooks, onExecute }: PlaybooksProps) => {
  return (
    <div>
      <div className="page-header" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
        <div>
          <h1 className="page-title gradient-text">Playbooks</h1>
          <p className="page-subtitle">Deterministic runbooks for automated incident remediation</p>
        </div>
        <button className="btn btn-accent" style={{ marginTop: 4 }}>
          + New Playbook
        </button>
      </div>

      {/* Summary row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
        {[
          { label: 'Total Playbooks', val: playbooks.length, icon: '▶', color: '#6366f1' },
          { label: 'Active Triggers', val: playbooks.filter(p => !!p.trigger).length, icon: 'TRG', color: '#10b981' },
          { label: 'Executions Today', val: 0, icon: '◉', color: '#f59e0b' },
        ].map(item => (
          <div key={item.label} className="glass-card" style={{ padding: 18, display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{
              width: 40, height: 40, borderRadius: 10,
              background: `${item.color}20`, color: item.color,
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.1rem',
              flexShrink: 0
            }}>{item.icon}</div>
            <div>
              <div style={{ fontSize: '1.5rem', fontWeight: 800, color: item.color }}>{item.val}</div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{item.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Playbook Cards */}
      <div className="cluster-grid">
        {playbooks.map((pb) => (
          <div key={pb.name} className="playbook-card animate-in">
            <div className="playbook-icon">▶</div>
            <div className="playbook-name">{pb.name}</div>
            <div className="playbook-desc">{pb.description}</div>

            {/* Steps */}
            <div style={{ marginBottom: 14 }}>
              {pb.steps.map((step, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'flex-start', gap: 8,
                  padding: '4px 0',
borderBottom: i < pb.steps.length - 1 ? '1px dashed var(--border)' : 'none'
                }}>
                  <div style={{
                    width: 18, height: 18, borderRadius: '50%',
                    background: 'rgba(99,102,241,0.15)', color: 'var(--accent)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: '0.6rem', fontWeight: 700, flexShrink: 0, marginTop: 2
                  }}>{i + 1}</div>
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)', lineHeight: 1.4 }}>{step}</span>
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 'auto' }}>
              <div className="playbook-trigger">
                <span style={{ color: 'var(--text-muted)' }}>Trigger:</span>
                <span className={`badge ${TRIGGER_BADGE[pb.trigger] || 'badge-neutral'}`} style={{ fontSize: '0.62rem' }}>
                  {(pb.trigger || '').replace(/_/g, ' ')}
                </span>
              </div>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => onExecute(pb.name, 'default', 'manual-trigger')}
              >
                ▶ Run
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
