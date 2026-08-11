import { useState } from 'react'
import { WsStatus } from '../types'

interface SettingsProps {
  wsStatus: WsStatus
}

export const SettingsPage = ({ wsStatus }: SettingsProps) => {
  const [apiUrl, setApiUrl] = useState(() => localStorage.getItem('autosre_api_url') || 'http://localhost:8080')
  const [wsUrl, setWsUrl] = useState(() => localStorage.getItem('autosre_ws_url') || 'ws://localhost:8080/ws/incidents')
  const [autoRemediate, setAutoRemediate] = useState(() => localStorage.getItem('autosre_auto_remediate') !== 'false')
  const [slackEnabled, setSlackEnabled] = useState(() => localStorage.getItem('autosre_slack_enabled') === 'true')
  const [pagerEnabled, setPagerEnabled] = useState(() => localStorage.getItem('autosre_pager_enabled') === 'true')
  const [emailEnabled, setEmailEnabled] = useState(() => localStorage.getItem('autosre_email_enabled') !== 'false')
  const [slackWebhook, setSlackWebhook] = useState(() => localStorage.getItem('autosre_slack_webhook') || '')
  const [threshold, setThreshold] = useState(() => localStorage.getItem('autosre_threshold') || 'high')
  const [pollInterval, setPollInterval] = useState(() => localStorage.getItem('autosre_poll_interval') || '30')
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    localStorage.setItem('autosre_api_url', apiUrl)
    localStorage.setItem('autosre_ws_url', wsUrl)
    localStorage.setItem('autosre_auto_remediate', String(autoRemediate))
    localStorage.setItem('autosre_slack_enabled', String(slackEnabled))
    localStorage.setItem('autosre_pager_enabled', String(pagerEnabled))
    localStorage.setItem('autosre_email_enabled', String(emailEnabled))
    localStorage.setItem('autosre_slack_webhook', slackWebhook)
    localStorage.setItem('autosre_threshold', threshold)
    localStorage.setItem('autosre_poll_interval', pollInterval)
    setSaved(true)
    setTimeout(() => setSaved(false), 2500)
  }

  const handleTestConnection = async () => {
    try {
      await fetch(`${apiUrl}/health`)
      alert('Connection successful.')
    } catch {
      alert('Connection failed. Check if the backend is running.')
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title gradient-text">Settings</h1>
        <p className="page-subtitle">Configure AutoSRE agent, integrations, and alert rules</p>
      </div>

      <div className="settings-grid">
        {/* API & Connection */}
        <div className="settings-section" style={{ gridColumn: '1 / -1' }}>
          <div className="settings-section-header">
            <div className="settings-section-icon" style={{ background: 'rgba(99,102,241,0.15)', color: 'var(--accent)' }}>CFG</div>
            <span className="settings-section-title">API &amp; Connection</span>
            <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
              <div className="status-dot" style={{
                width: 8, height: 8,
                background: wsStatus === 'connected' ? 'var(--success)' : 'var(--danger)',
                borderRadius: '50%',
                boxShadow: wsStatus === 'connected' ? '0 0 6px var(--success)' : 'none',
                animation: wsStatus === 'connected' ? 'pulse-dot 2s infinite' : 'none',
              }} />
              <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                {wsStatus === 'connected' ? 'Backend connected' : 'Backend offline'}
              </span>
            </div>
          </div>
          <div className="settings-body" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div className="form-group">
              <label className="form-label" htmlFor="api-url">Backend API URL</label>
              <input
                id="api-url"
                className="form-input code-input"
                value={apiUrl}
                onChange={e => setApiUrl(e.target.value)}
                placeholder="http://localhost:8080"
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="ws-url">WebSocket URL</label>
              <input
                id="ws-url"
                className="form-input code-input"
                value={wsUrl}
                onChange={e => setWsUrl(e.target.value)}
                placeholder="ws://localhost:8080/ws/incidents"
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="poll-interval">Polling Interval (seconds)</label>
              <input
                id="poll-interval"
                className="form-input"
                type="number"
                min="5"
                max="300"
                value={pollInterval}
                onChange={e => setPollInterval(e.target.value)}
              />
            </div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
              <button id="test-connection-btn" className="btn btn-secondary btn-full" onClick={handleTestConnection}>
                Test Connection
              </button>
            </div>
          </div>
        </div>

        {/* Agent Behavior */}
        <div className="settings-section">
          <div className="settings-section-header">
            <div className="settings-section-icon" style={{ background: 'rgba(16,185,129,0.15)', color: 'var(--success)' }}>AG</div>
            <span className="settings-section-title">Agent Behavior</span>
          </div>
          <div className="settings-body">
            <div className="toggle-row">
              <div className="toggle-info">
                <div className="toggle-label">Auto-Remediation</div>
                <div className="toggle-desc">Automatically execute approved fixes</div>
              </div>
              <label className="toggle">
                <input type="checkbox" checked={autoRemediate} onChange={e => setAutoRemediate(e.target.checked)} />
                <span className="toggle-slider" />
              </label>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="confidence-threshold">Confidence Threshold</label>
              <select
                id="confidence-threshold"
                className="form-input"
                value={threshold}
                onChange={e => setThreshold(e.target.value)}
              >
                <option value="high">High only (safest)</option>
                <option value="medium">Medium &amp; above</option>
                <option value="low">All (all detections)</option>
              </select>
            </div>

            <div style={{ background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', padding: 12, border: '1px solid var(--border)' }}>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>API Endpoint</div>
              <code style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.78rem', color: 'var(--info)' }}>
                {apiUrl}/api/v1
              </code>
            </div>
          </div>
        </div>

        {/* Notifications */}
        <div className="settings-section">
          <div className="settings-section-header">
            <div className="settings-section-icon" style={{ background: 'rgba(245,158,11,0.15)', color: 'var(--warning)' }}>NTF</div>
            <span className="settings-section-title">Notifications</span>
          </div>
          <div className="settings-body">
            <div className="toggle-row">
              <div className="toggle-info">
                <div className="toggle-label">Slack Integration</div>
                <div className="toggle-desc">Send alerts to Slack channels</div>
              </div>
              <label className="toggle">
                <input type="checkbox" checked={slackEnabled} onChange={e => setSlackEnabled(e.target.checked)} />
                <span className="toggle-slider" />
              </label>
            </div>

            {slackEnabled && (
              <div className="form-group">
                <label className="form-label" htmlFor="slack-webhook">Slack Webhook URL</label>
                <input
                  id="slack-webhook"
                  className="form-input code-input"
                  value={slackWebhook}
                  onChange={e => setSlackWebhook(e.target.value)}
                  placeholder="https://hooks.slack.com/services/..."
                />
              </div>
            )}

            <div className="toggle-row">
              <div className="toggle-info">
                <div className="toggle-label">PagerDuty</div>
                <div className="toggle-desc">Escalate critical incidents</div>
              </div>
              <label className="toggle">
                <input type="checkbox" checked={pagerEnabled} onChange={e => setPagerEnabled(e.target.checked)} />
                <span className="toggle-slider" />
              </label>
            </div>

            <div className="toggle-row">
              <div className="toggle-info">
                <div className="toggle-label">Email Alerts</div>
                <div className="toggle-desc">Receive incident summaries</div>
              </div>
              <label className="toggle">
                <input type="checkbox" checked={emailEnabled} onChange={e => setEmailEnabled(e.target.checked)} />
                <span className="toggle-slider" />
              </label>
            </div>
          </div>
        </div>

        {/* Security */}
        <div className="settings-section" style={{ gridColumn: '1 / -1' }}>
          <div className="settings-section-header">
            <div className="settings-section-icon" style={{ background: 'rgba(239,68,68,0.15)', color: 'var(--danger)' }}>SEC</div>
            <span className="settings-section-title">Security &amp; Access</span>
          </div>
          <div className="settings-body" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div className="form-group">
              <label className="form-label" htmlFor="api-token">API Token</label>
              <input
                id="api-token"
                className="form-input code-input"
                type="password"
                placeholder="Bearer token…"
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="kubeconfig">Kubeconfig Path</label>
              <input
                id="kubeconfig"
                className="form-input code-input"
                placeholder="~/.kube/config"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Save Bar */}
      <div style={{
        marginTop: 24,
        padding: '16px 20px',
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 16,
        flexWrap: 'wrap'
      }}>
        <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          Changes are applied immediately after saving.
        </span>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn btn-ghost" onClick={() => window.location.reload()}>Reset</button>
          <button
            id="save-settings-btn"
            className={`btn ${saved ? 'btn-primary' : 'btn-accent'}`}
            onClick={handleSave}
          >
            {saved ? 'Saved!' : 'Save Settings'}
          </button>
        </div>
      </div>
    </div>
  )
}
