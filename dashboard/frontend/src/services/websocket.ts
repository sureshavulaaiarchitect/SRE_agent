import { useEffect, useRef, useState, useCallback } from 'react'
import type { WsStatus } from '../types'
import type { Incident, ActivityEvent } from '../types'

class WebSocketService {
  private ws: WebSocket | null = null
  private reconnectTimeout: any = null
  private heartbeatTimeout: any = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 10
  private listeners: Array<(data: any) => void> = []
  private status: WsStatus = 'disconnected'
  private wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8080/ws/incidents'
  private clientId = Math.random().toString(36).substring(2, 15)
  private authToken = import.meta.env.VITE_WS_TOKEN || 'demo-token'

  private notifyListeners(data: any) {
    this.listeners.forEach(listener => listener(data))
  }

  connect(url?: string) {
    if (url) this.wsUrl = url
    
    // Ensure only ONE connection exists
    if (this.ws) {
        if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
            console.log('WS already connected or connecting, skipping')
            return
        }
        this.disconnect()
    }

    const finalUrl = new URL(this.wsUrl)
    finalUrl.searchParams.set('client_id', this.clientId)
    finalUrl.searchParams.set('token', this.authToken)

    try {
        this.ws = new WebSocket(finalUrl.toString())
        this.status = 'connecting'
        this.notifyListeners({ type: 'status', status: 'connecting' })

        this.ws.onopen = () => {
          this.status = 'connected'
          this.reconnectAttempts = 0
          this.notifyListeners({ type: 'status', status: 'connected' })
          this.resetHeartbeat()
          console.log('WS connected', { clientId: this.clientId })
        }

        this.ws.onclose = (event) => {
          console.log('WS closed:', event.code, event.reason)
          this.status = 'disconnected'
          this.notifyListeners({ type: 'status', status: 'disconnected' })
          
          if (event.code !== 1000 && event.code !== 1001) {
              this.scheduleReconnect()
          }
        }

        this.ws.onerror = (error) => {
          console.error('WS error:', error)
          this.status = 'error'
          this.notifyListeners({ type: 'status', status: 'error' })
        }

        this.ws.onmessage = (event) => {
          const data = JSON.parse(event.data)
          if (data.type === 'ping') {
            this.ws?.send(JSON.stringify({ type: 'pong' }))
            this.resetHeartbeat()
            return
          }
          this.notifyListeners(data)
        }
    } catch (e) {
        console.error('Failed to create WebSocket:', e)
        this.scheduleReconnect()
    }
  }

  private resetHeartbeat() {
    if (this.heartbeatTimeout) clearTimeout(this.heartbeatTimeout)
    this.heartbeatTimeout = setTimeout(() => {
      console.warn('Heartbeat timeout - closing connection')
      this.ws?.close(4000, 'Heartbeat timeout')
    }, 70000) // Slightly longer than server timeout
  }

  private scheduleReconnect() {
    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout)
    
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        console.error('Max reconnect attempts reached. Stopping.')
        this.status = 'error'
        this.notifyListeners({ type: 'status', status: 'error' })
        return
    }
    
    // Exponential backoff with jitter
    const baseDelay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000)
    const jitter = Math.random() * 1000
    const delay = baseDelay + jitter
    
    console.log(`Scheduling reconnect in ${Math.round(delay)}ms (attempt ${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`)
    
    this.reconnectTimeout = setTimeout(() => {
      this.reconnectAttempts++
      this.connect()
    }, delay)
  }

  subscribe(listener: (data: any) => void) {
    this.listeners.push(listener)
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener)
    }
  }

  getStatus(): WsStatus {
    return this.status
  }

  disconnect() {
    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout)
    if (this.heartbeatTimeout) clearTimeout(this.heartbeatTimeout)
    if (this.ws) {
        this.ws.onclose = null // Prevent reconnect loop
        this.ws.close()
        this.ws = null
    }
    this.status = 'disconnected'
  }
}

// Singleton instance
export const wsService = new WebSocketService()

export const useWebSocket = () => {
  const [status, setStatus] = useState<WsStatus>('disconnected')

  useEffect(() => {
    const unsubscribe = wsService.subscribe((data) => {
      if (data.type === 'status') setStatus(data.status)
    })
    return unsubscribe
  }, [])

  return {
    status,
    connect: (url?: string) => wsService.connect(url)
  }
}

