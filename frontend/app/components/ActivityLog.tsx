'use client'

import { useEffect, useState, useRef } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface ActivityEvent {
  ts: string
  type: string
  service: string | null
  message: string
  metadata: any
}

interface ActivityLogProps {
  incidentId?: string
  service?: string
  limit?: number
}

const EVENT_TYPE_COLORS: Record<string, string> = {
  metrics_ingested: '#2196F3',
  anomaly_detected: '#FF9800',
  incident_created: '#F44336',
  rca_started: '#9C27B0',
  suspects_generated: '#4CAF50',
  suspect_score_updated: '#00BCD4',
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  metrics_ingested: 'Metrics',
  anomaly_detected: 'Anomaly',
  incident_created: 'Incident',
  rca_started: 'RCA',
  suspects_generated: 'Suspects',
  suspect_score_updated: 'Update',
}

export default function ActivityLog({ incidentId, service, limit = 50 }: ActivityLogProps) {
  const [events, setEvents] = useState<ActivityEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const lastEventTsRef = useRef<string | null>(null)

  useEffect(() => {
    fetchEvents()
    
    // Set up polling every 2 seconds
    const interval = setInterval(() => {
      fetchEvents(true) // Silent fetch
    }, 2000)
    
    return () => clearInterval(interval)
  }, [incidentId, service])

  const fetchEvents = async (silent = false) => {
    try {
      if (!silent) {
        setError(null)
      }
      
      // Build query params
      const params = new URLSearchParams()
      if (lastEventTsRef.current) {
        params.append('since', lastEventTsRef.current)
      }
      params.append('limit', limit.toString())
      if (service) {
        params.append('service', service)
      }
      
      const response = await fetch(`${API_URL}/activity/events?${params.toString()}`)
      
      if (!response.ok) {
        throw new Error(`Failed to fetch events: ${response.status}`)
      }
      
      const data = await response.json()
      const newEvents = data.events || []
      
      if (newEvents.length > 0) {
        // Filter events by incident if specified
        let filteredEvents = newEvents
        if (incidentId) {
          filteredEvents = newEvents.filter((e: ActivityEvent) => 
            e.metadata?.incident_id === incidentId
          )
        }
        
        // Merge with existing events, avoiding duplicates
        setEvents(prev => {
          const existingIds = new Set(prev.map(e => `${e.ts}-${e.type}-${e.service}`))
          const uniqueNew = filteredEvents.filter((e: ActivityEvent) => 
            !existingIds.has(`${e.ts}-${e.type}-${e.service}`)
          )
          
          const merged = [...prev, ...uniqueNew]
            .sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime())
            .slice(0, limit)
          
          // Update last event timestamp
          if (merged.length > 0) {
            lastEventTsRef.current = merged[0].ts
          }
          
          return merged
        })
        
        // Auto-scroll to top (newest events)
        if (scrollContainerRef.current && !silent) {
          scrollContainerRef.current.scrollTop = 0
        }
      }
    } catch (error) {
      console.error('Failed to fetch events:', error)
      if (!silent) {
        setError(error instanceof Error ? error.message : 'Failed to load events')
      }
    } finally {
      if (!silent) {
        setLoading(false)
      }
    }
  }

  const formatTime = (ts: string) => {
    const date = new Date(ts)
    return date.toLocaleTimeString()
  }

  const getEventColor = (type: string) => {
    return EVENT_TYPE_COLORS[type] || '#666'
  }

  const getEventLabel = (type: string) => {
    return EVENT_TYPE_LABELS[type] || type
  }

  if (loading && events.length === 0) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>Loading activity log...</div>
    )
  }

  if (error && events.length === 0) {
    return (
      <div style={{ padding: '20px', color: '#d32f2f', background: '#ffebee', borderRadius: '4px', border: '1px solid #ffcdd2' }}>
        <strong>Error:</strong> {error}
        <br />
        <button 
          onClick={() => fetchEvents()}
          style={{ marginTop: '10px', padding: '8px 16px', background: '#1976d2', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
        >
          Retry
        </button>
      </div>
    )
  }

  return (
    <div style={{ border: '1px solid #ddd', borderRadius: '4px', overflow: 'hidden' }}>
      <div style={{ 
        padding: '10px 15px', 
        background: '#f5f5f5', 
        borderBottom: '1px solid #ddd',
        fontWeight: 500
      }}>
        Activity Log {events.length > 0 && `(${events.length})`}
      </div>
      <div
        ref={scrollContainerRef}
        style={{
          maxHeight: '400px',
          overflowY: 'auto',
          padding: '10px'
        }}
      >
        {events.length === 0 ? (
          <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
            No events yet. Events will appear here as the system processes data.
          </div>
        ) : (
          events.map((event, index) => (
            <div
              key={`${event.ts}-${event.type}-${index}`}
              style={{
                padding: '8px 12px',
                marginBottom: '8px',
                borderLeft: `3px solid ${getEventColor(event.type)}`,
                background: '#fafafa',
                borderRadius: '2px',
                fontSize: '13px'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '4px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span
                    style={{
                      display: 'inline-block',
                      padding: '2px 6px',
                      borderRadius: '3px',
                      background: getEventColor(event.type),
                      color: 'white',
                      fontSize: '11px',
                      fontWeight: 500
                    }}
                  >
                    {getEventLabel(event.type)}
                  </span>
                  {event.service && (
                    <span style={{ color: '#666', fontSize: '12px' }}>
                      {event.service}
                    </span>
                  )}
                </div>
                <span style={{ color: '#999', fontSize: '11px' }}>
                  {formatTime(event.ts)}
                </span>
              </div>
              <div style={{ color: '#333', marginTop: '4px' }}>
                {event.message}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
