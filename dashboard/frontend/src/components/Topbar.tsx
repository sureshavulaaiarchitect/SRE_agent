import { WsStatus } from '../types'

interface TopbarProps {
  searchTerm: string
  onSearchChange: (v: string) => void
  activeIncidents: number
  wsStatus: WsStatus
  onOpenSidebar: () => void
}

export const Topbar = ({
  searchTerm,
  onSearchChange,
  activeIncidents,
  wsStatus,
  onOpenSidebar,
}: TopbarProps) => {
  return (
    <header className="topbar">
      {/* Mobile hamburger */}
      <button
        className="topbar-hamburger"
        onClick={onOpenSidebar}
        aria-label="Open menu"
      >
        ☰
      </button>

      {/* Mobile brand */}
      <div className="topbar-brand-mobile">AutoSRE</div>

      {/* Search */}
      <div className="topbar-search">
        <span className="topbar-search-icon">?</span>
        <input
          id="global-search"
          className="search-input"
          type="text"
          placeholder="Search pods, namespaces, or incident patterns..."
          value={searchTerm}
          onChange={e => onSearchChange(e.target.value)}
          autoComplete="off"
        />
      </div>

      {/* Actions */}
      <div className="topbar-actions">
        {/* WS badge */}
        <div className="topbar-badge">
          <div
            className={`status-dot ${wsStatus}`}
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              margin: 0,
            }}
          />
          <span style={{ fontSize: '0.75rem', fontWeight: 600 }}>
            {wsStatus === 'connected' ? 'LIVE' : wsStatus === 'connecting' ? 'CONNECTING' : 'OFFLINE'}
          </span>
        </div>

        <div style={{ width: 1, height: 24, background: 'var(--border)', margin: '0 4px' }} />

        {/* Notifications */}
        <button className="topbar-icon-btn" aria-label="Notifications" title="Notifications">
          N
          {activeIncidents > 0 && (
            <span className="notification-badge">{activeIncidents > 9 ? '9+' : activeIncidents}</span>
          )}
        </button>

        {/* Docs */}
        <button className="topbar-icon-btn" aria-label="Documentation" title="Documentation">
          D
        </button>

        {/* Avatar */}
        <div className="topbar-avatar" title="SRE Admin">
          JD
        </div>
      </div>
    </header>
  )
}
