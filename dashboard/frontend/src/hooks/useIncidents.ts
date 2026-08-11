import { useState, useEffect, useCallback } from 'react'
import { Incident, Toast, ClusterStats, ActivityEvent, Playbook, Cluster, WsStatus } from '../types'
import { wsService } from '../services/websocket'

export const useIncidents = () => {
  const [apiUrl, setApiUrl] = useState(() => localStorage.getItem('autosre_api_url') || 'http://localhost:8080')
  const [wsUrl, setWsUrl] = useState(() => localStorage.getItem('autosre_ws_url') || 'ws://localhost:8080/ws/incidents')
  
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [stats, setStats] = useState<ClusterStats>({
    healthy_pods: 0,
    failing_pods: 0,
    active_incidents: 0,
    total_pods: 0,
    total_nodes: 0,
    total_namespaces: 0,
    cpu_usage: 0,
    memory_usage: 0,
    uptime: '100%'
  })
  const [activity, setActivity] = useState<ActivityEvent[]>([])
  const [playbooks, setPlaybooks] = useState<Playbook[]>([])
  const [clusters, setClusters] = useState<Cluster[]>([])
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({})

  const addToast = useCallback((message: string, type: Toast['type'] = 'success') => {
    const id = Math.random().toString(36).slice(2)
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000)
  }, [])

  const fetchData = useCallback(async () => {
    try {
      const authHeader = { 'Authorization': 'Bearer demo-token' }
      
      // Fetch incidents
      const incRes = await fetch(`${apiUrl}/incident/history`, { headers: authHeader })
      if (!incRes.ok) throw new Error('Failed to fetch incidents')
      const incData = await incRes.json()
      const formatted = incData.map((i: any) => ({
        id: i.id,
        incident_id: i.id,
        pod_name: i.pod_name,
        namespace: i.namespace,
        incident_type: i.incident_type,
        root_cause: i.root_cause || 'Analyzing...',
        confidence: i.confidence || 'low',
        recommended_action: i.recommended_action || 'kubectl describe pod ' + i.pod_name,
        explanation: i.explanation || 'Root cause investigation in progress.',
        source: i.ai_used ? 'AI Engine' : 'Pattern DB',
        timestamp: i.timestamp,
        created_at: i.timestamp,
        status: i.status === 'open' ? 'active' : 
                i.status === 'awaiting_approval' ? 'awaiting_approval' : 
                i.status === 'investigating' ? 'investigating' :
                ['resolved', 'closed_no_action'].includes(i.status) ? 'resolved' :
                i.status === 'executing' ? 'executing' : (i.status as any),
        ai_used: !!i.ai_used
      }))
      setIncidents(formatted)

      // Fetch cluster stats
      const statsRes = await fetch(`${apiUrl}/cluster/status`, { headers: authHeader })
      if (statsRes.ok) {
        const statsData = await statsRes.json()
        setStats({
          healthy_pods: statsData.healthy_pods,
          failing_pods: statsData.failing_pods,
          active_incidents: statsData.active_incidents,
          total_pods: statsData.healthy_pods + statsData.failing_pods,
          total_nodes: statsData.total_nodes,
          total_namespaces: statsData.total_namespaces,
          cpu_usage: statsData.cpu_usage_pct,
          memory_usage: statsData.memory_usage_pct,
          uptime: '99.9%'
        })
      }

      // Fetch real activity
      const activityRes = await fetch(`${apiUrl}/incident/activity`, { headers: authHeader })
      if (activityRes.ok) {
        const activityData = await activityRes.json()
        setActivity(activityData.map((a: any) => ({
          id: a.id,
          type: a.type,
          message: a.message,
          timestamp: a.timestamp,
          severity: a.severity
        })))
      }

      // Fetch playbooks
      const pbRes = await fetch(`${apiUrl}/playbooks`, { headers: authHeader })
      if (pbRes.ok) {
        const pbData = await pbRes.json()
        setPlaybooks(pbData.map((p: any) => p.details || {
          name: p.name,
          description: 'No description available',
          trigger: 'manual',
          steps: []
        }))
      }

      // Fetch clusters
      const clRes = await fetch(`${apiUrl}/cluster/status`, { headers: authHeader })
      if (clRes.ok) {
        const clData = await clRes.json()
        setClusters([{
          id: clData.cluster_id,
          name: 'Local Cluster',
          region: 'internal',
          status: clData.failing_pods > 0 ? 'degraded' : 'healthy',
          node_count: clData.total_nodes,
          pod_count: clData.healthy_pods + clData.failing_pods
        }])
      }

      setIsLoading(false)
    } catch (err) {
      console.error('Failed to fetch data:', err)
      setIsLoading(false)
    }
  }, [apiUrl, addToast])

  // Consolidated effect for WebSocket lifecycle
  useEffect(() => {
    const handleMessage = (data: any) => {
      if (data.type === 'status') return
      if (data.type === 'activity') {
        setActivity(prev => [{
          id: Math.random().toString(),
          type: data.activity_type,
          message: data.message,
          timestamp: data.timestamp || new Date().toISOString(),
          severity: data.severity
        }, ...prev.slice(0, 99)])
        return
      }
      if (data.incident_id) {
        const mapped: Incident = {
          id: data.incident_id,
          incident_id: data.incident_id,
          pod_name: data.pod_name,
          namespace: data.namespace,
          incident_type: data.incident_type,
          root_cause: data.root_cause || 'Analyzing...',
          confidence: data.confidence || 'low',
          recommended_action: data.recommended_action || 'investigate',
          explanation: data.explanation || 'AI analysis in progress',
          source: data.source || 'agent',
          timestamp: data.created_at || new Date().toISOString(),
          created_at: data.created_at || new Date().toISOString(),
          status: 'analyzed',
          ai_used: !!data.ai_used
        }
        setIncidents(prev => {
          if (prev.find(i => i.incident_id === mapped.incident_id)) return prev
          addToast(`New incident: ${data.pod_name}`, 'warning')
          setStats(prev => ({ ...prev, active_incidents: prev.active_incidents + 1, failing_pods: prev.failing_pods + 1 }))
          return [mapped, ...prev.slice(0, 49)]
        })
      }
    }

    const unsubscribe = wsService.subscribe(handleMessage)
    wsService.connect(wsUrl)

    const handleStorage = () => {
      const newApiUrl = localStorage.getItem('autosre_api_url') || 'http://localhost:8080'
      const newWsUrl = localStorage.getItem('autosre_ws_url') || 'ws://localhost:8080/ws/incidents'
      
      if (newApiUrl !== apiUrl) setApiUrl(newApiUrl)
      if (newWsUrl !== wsUrl) {
        setWsUrl(newWsUrl)
        // Note: wsUrl dependency will trigger effect re-run
      }
    }
    
    window.addEventListener('storage', handleStorage)

    return () => {
      window.removeEventListener('storage', handleStorage)
      unsubscribe()
      // We don't necessarily want to disconnect the singleton if other parts of the app use it,
      // but for useIncidents, it's safer to leave it unless the whole page is gone.
    }
  }, [wsUrl, apiUrl, addToast]) 

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const handleAction = useCallback(async (incident: Incident, approved: boolean) => {
    const incId = incident.id || incident.incident_id;
    setActionLoading(prev => ({ ...prev, [incId]: true }))
    try {
      // New approval API path: /incident/{id}/approve
      const endpoint = approved ? `${apiUrl}/incident/${incId}/approve` : `${apiUrl}/incident/${incId}/dismiss`; // Assuming dismiss for reject
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer demo-token' },
      })

      if (res.ok) {
        if (approved) {
          addToast(`Remediation approved for ${incident.pod_name}`, 'success')
          setIncidents(prev => prev.map(i => 
            (i.id === incident.id || i.incident_id === incident.incident_id) ? { ...i, status: 'executing' } : i
          ))
        } else {
          addToast(`Action rejected`, 'info')
        }
        await fetchData();
      } else {
        const error = await res.json()
        addToast(`Action failed: ${error.detail || 'Server error'}`, 'error')
      }
    } catch (err) {
      addToast(`Network error connecting to backend`, 'error')
    } finally {
        setActionLoading(prev => ({ ...prev, [incId]: false }))
    }
  }, [apiUrl, addToast, fetchData])

  const dismissIncident = useCallback((incidentId: string) => {
    setIncidents(prev => prev.filter(i => i.incident_id !== incidentId))
    addToast('Incident dismissed', 'info')
  }, [addToast])

  const executePlaybook = useCallback(async (name: string, namespace: string, podName: string) => {
    try {
      const res = await fetch(`${apiUrl}/playbooks/${name}/execute?namespace=${namespace}&pod_name=${podName}`, {
        method: 'POST',
        headers: { 'Authorization': 'Bearer demo-token' }
      })
      if (res.ok) {
        addToast(`Playbook triggered: ${name}`, 'success')
      } else {
        addToast(`Playbook failed: ${name}`, 'error')
      }
    } catch (err) {
      addToast('Network error', 'error')
    }
  }, [apiUrl, addToast])

  const pollInterval = 5000; // 5 second auto-refresh

  useEffect(() => {
    fetchData(); // Initial fetch
    const intervalId = setInterval(fetchData, pollInterval);
    return () => clearInterval(intervalId);
  }, [fetchData]);

  return {
    incidents,
    wsStatus: wsService.getStatus() as WsStatus,
    isLoading,
    toasts,
    stats,
    activity,
    playbooks,
    clusters,
    activeIncidents: incidents.filter(i => ['investigating', 'awaiting_approval', 'executing', 'detected', 'analyzed'].includes(i.status)).length,
    apiUrl,
    handleAction,
    addToast,
    removeToast,
    dismissIncident,
    executePlaybook,
    actionLoading
  }
}

