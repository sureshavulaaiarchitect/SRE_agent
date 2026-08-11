import { useState } from 'react'
import { Page, Incident } from './types'
import { useWebSocket } from './services/websocket'
import { useIncidents } from './hooks/useIncidents'
import { Sidebar } from './components/Sidebar'
import { Topbar } from './components/Topbar'
import { ToastContainer } from './components/Toast'
import { Dashboard } from './pages/Dashboard'
import { IncidentsPage } from './pages/Incidents'
import { ActivityPage } from './pages/Activity'
import { PlaybooksPage } from './pages/Playbooks'
import { ClustersPage } from './pages/Clusters'
import { SettingsPage } from './pages/Settings'
import { IncidentModal } from './pages/IncidentModal'
import { ClusterHealth } from './pages/ClusterHealth'
import { RemediationQueue } from './pages/RemediationQueue'
import { PlaybookEditor } from './pages/PlaybookEditor'
import './index.css'

export default function App() {
  const [page, setPage] = useState<Page>('dashboard')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null)

  const {
    incidents,
    isLoading,
    toasts,
    stats,
    activity,
    playbooks,
    clusters,
    activeIncidents,
    handleAction,
    removeToast,
    dismissIncident,
    executePlaybook,
    actionLoading
  } = useIncidents()
  
  const { status: wsStatus } = useWebSocket()

  const handlePageChange = (p: Page) => {
    setPage(p)
    setSidebarOpen(false)
  }

  const handleExecute = (inc: Incident) => handleAction(inc, true)
  const handleReview = (inc: Incident) => handleAction(inc, false)

  const renderPage = () => {
    switch (page) {
      case 'dashboard':
        return (
          <Dashboard
            incidents={incidents}
            stats={stats}
            activity={activity}
            isLoading={isLoading}
            wsStatus={wsStatus}
            activeIncidents={activeIncidents}
            searchTerm={searchTerm}
            onSelectIncident={setSelectedIncident}
            onExecute={handleExecute}
            onReview={handleReview}
            actionLoading={actionLoading}
          />
        )
      case 'incidents':
        return (
          <IncidentsPage
            incidents={incidents}
            isLoading={isLoading}
            searchTerm={searchTerm}
            onSelectIncident={setSelectedIncident}
            onExecute={handleExecute}
            onReview={handleReview}
            onDismiss={dismissIncident}
            actionLoading={actionLoading}
          />
        )
      case 'activity':
        return <ActivityPage activity={activity} />
      case 'playbooks':
        return <PlaybooksPage playbooks={playbooks} onExecute={executePlaybook} />
      case 'clusters':
        return <ClustersPage clusters={clusters} />
      case 'cluster-health':
        return <ClusterHealth clusters={clusters} stats={stats} />
      case 'remediation-queue':
        return <RemediationQueue incidents={incidents.filter(i => ['pending', 'awaiting_approval'].includes(i.status || ''))} onApprove={handleExecute} onReject={handleReview} actionLoading={actionLoading} />

      case 'playbook-editor':
        return <PlaybookEditor />
      case 'settings':
        return <SettingsPage wsStatus={wsStatus} />
      default:
        return null
    }
  }

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <Sidebar
        page={page}
        isOpen={sidebarOpen}
        onPageChange={handlePageChange}
        onClose={() => setSidebarOpen(false)}
        wsStatus={wsStatus}
        activeIncidents={activeIncidents}
      />

      {/* Main wrapper */}
      <div className="main-wrapper">
        {/* Topbar */}
        <Topbar
          searchTerm={searchTerm}
          onSearchChange={setSearchTerm}
          activeIncidents={activeIncidents}
          wsStatus={wsStatus}
          onOpenSidebar={() => setSidebarOpen(true)}
        />

        {/* Page content */}
        <main className="page-content" id="main-content">
          {renderPage()}
        </main>
      </div>

      {/* Incident detail modal */}
      {selectedIncident && (
        <IncidentModal
          incident={selectedIncident}
          onClose={() => setSelectedIncident(null)}
          onApprove={handleExecute}
          onReject={handleReview}
        />
      )}

      {/* Toast notifications */}
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </div>
  )
}
