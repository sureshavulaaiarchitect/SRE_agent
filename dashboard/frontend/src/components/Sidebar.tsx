import { Page, WsStatus } from '../types'

interface SidebarProps {
  page: Page
  isOpen: boolean
  onPageChange: (page: Page) => void
  onClose: () => void
  wsStatus: WsStatus
  activeIncidents: number
}

const NAV_ITEMS = [
  { id: 'dashboard' as Page, icon: '⬡', label: 'Dashboard' },
  { id: 'incidents' as Page, icon: 'INC', label: 'Incidents', hasBadge: true },
  { id: 'activity' as Page, icon: '◉', label: 'Activity Feed' },
  { id: 'playbooks' as Page, icon: '▶', label: 'Playbooks' },
  { id: 'clusters' as Page, icon: '◈', label: 'Clusters' },
  { id: 'settings' as Page, icon: '◎', label: 'Settings' },
  { id: 'cluster-health' as Page, icon: 'CH', label: 'Cluster Health' },
  { id: 'remediation-queue' as Page, icon: 'RQ', label: 'Remediation Queue' },
  { id: 'playbook-editor' as Page, icon: 'PB', label: 'Playbook Editor' },
]

export const Sidebar = ({
  page,
  isOpen,
  onPageChange,
  onClose,
  wsStatus,
  activeIncidents
}: SidebarProps) => {
  return (
    <>
      {/* Overlay */}
      <div
        className={`sidebar-overlay ${isOpen ? 'open' : ''}`}
        onClick={onClose}
        aria-hidden="true"
      />

      <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
        {/* Header */}
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <div className="sidebar-brand-icon">AS</div>
            <div>
              <div className="sidebar-brand-name">AutoSRE</div>
              <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontWeight: 600, marginTop: -2 }}>
                K8S SENTINEL <span className="sidebar-brand-version">v2.1</span>
              </div>
            </div>
            <button className="sidebar-close-btn" onClick={onClose} aria-label="Close sidebar">
              ✕
            </button>
          </div>
        </div>

        {/* Navigation */}
        <nav className="sidebar-nav">
          <div className="nav-section-label">Main Monitor</div>
          {NAV_ITEMS.slice(0, 3).map(item => (
            <button
              key={item.id}
              className={`nav-item ${page === item.id ? 'active' : ''}`}
              onClick={() => { onPageChange(item.id); onClose(); }}
              aria-current={page === item.id ? 'page' : undefined}
            >
              <span className="nav-item-icon">{item.icon}</span>
              <span className="nav-item-label">{item.label}</span>
              {item.hasBadge && activeIncidents > 0 && (
                <span className="nav-item-badge">{activeIncidents}</span>
              )}
            </button>
          ))}

          <div className="nav-section-label">Infrastructure</div>
          {NAV_ITEMS.slice(3, 5).map(item => (
            <button
              key={item.id}
              className={`nav-item ${page === item.id ? 'active' : ''}`}
              onClick={() => { onPageChange(item.id); onClose(); }}
              aria-current={page === item.id ? 'page' : undefined}
            >
              <span className="nav-item-icon">{item.icon}</span>
              <span className="nav-item-label">{item.label}</span>
            </button>
          ))}
          {NAV_ITEMS.slice(6, 7).map(item => (
            <button
              key={item.id}
              className={`nav-item ${page === item.id ? 'active' : ''}`}
              onClick={() => { onPageChange(item.id); onClose(); }}
              aria-current={page === item.id ? 'page' : undefined}
            >
              <span className="nav-item-icon">{item.icon}</span>
              <span className="nav-item-label">{item.label}</span>
            </button>
          ))}

          <div className="nav-section-label">Automation</div>
          {NAV_ITEMS.slice(7, 9).map(item => (
            <button
              key={item.id}
              className={`nav-item ${page === item.id ? 'active' : ''}`}
              onClick={() => { onPageChange(item.id); onClose(); }}
              aria-current={page === item.id ? 'page' : undefined}
            >
              <span className="nav-item-icon">{item.icon}</span>
              <span className="nav-item-label">{item.label}</span>
            </button>
          ))}

          <div className="nav-section-label">System</div>
          {NAV_ITEMS.slice(5, 6).map(item => (
            <button
              key={item.id}
              className={`nav-item ${page === item.id ? 'active' : ''}`}
              onClick={() => { onPageChange(item.id); onClose(); }}
              aria-current={page === item.id ? 'page' : undefined}
            >
              <span className="nav-item-icon">{item.icon}</span>
              <span className="nav-item-label">{item.label}</span>
            </button>
          ))}
        </nav>

        {/* Footer */}
        <div className="sidebar-footer">
          <div className="sidebar-status">
            <div className={`status-dot ${wsStatus}`} />
            <div className="status-text">
              <strong>
                {wsStatus === 'connected' ? 'Agent Active' : wsStatus === 'connecting' ? 'Reconnecting' : 'Agent Offline'}
              </strong>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem', marginTop: 1 }}>
                {wsStatus === 'connected' ? 'Streaming live metrics' : 'Check connection status'}
              </div>
            </div>
          </div>
        </div>
      </aside>
    </>
  )
}
