'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import SuspectsTable from '@/app/components/SuspectsTable'
import LabelButtons from '@/app/components/LabelButtons'
import ActivityLog from '@/app/components/ActivityLog'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Incident {
  id: string
  start_ts: string
  end_ts: string | null
  title: string
  status: string
  summary: string | null
}

interface Anomaly {
  id: string
  start_ts: string
  end_ts: string
  service: string
  metric: string
  score: number
  detector: string
  details: any
}

interface IncidentStatus {
  incident_id: string
  rca_status: 'not_started' | 'in_progress' | 'completed'
  suspects_count: number
  last_updated: string
}

export default function IncidentDetail() {
  const params = useParams()
  const incidentId = params.id as string

  const [incident, setIncident] = useState<Incident | null>(null)
  const [anomalies, setAnomalies] = useState<Anomaly[]>([])
  const [incidentStatus, setIncidentStatus] = useState<IncidentStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isPolling, setIsPolling] = useState(false)

  const fetchIncident = async (silent = false) => {
    try {
      if (!silent) {
        setError(null)
      }
      const response = await fetch(`${API_URL}/incidents/${incidentId}`)
      
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('Incident not found')
        }
        throw new Error(`Failed to fetch incident: ${response.status}`)
      }
      
      const data = await response.json()
      setIncident(data)
    } catch (error) {
      console.error('Failed to fetch incident:', error)
      if (!silent) {
        setError(error instanceof Error ? error.message : 'Failed to load incident')
      }
    } finally {
      if (!silent) {
        setLoading(false)
      }
      setIsPolling(false)
    }
  }

  const fetchAnomalies = async (silent = false) => {
    try {
      const response = await fetch(`${API_URL}/incidents/${incidentId}/anomalies`)
      
      if (!response.ok) {
        if (!silent) {
          console.warn('Failed to fetch anomalies:', response.status)
        }
        return
      }
      
      const data = await response.json()
      setAnomalies(data.anomalies || [])
    } catch (error) {
      if (!silent) {
        console.error('Failed to fetch anomalies:', error)
      }
      // Don't set error state for anomalies - it's not critical
    }
  }

  const fetchIncidentStatus = async (silent = false) => {
    try {
      const response = await fetch(`${API_URL}/incidents/${incidentId}/status`)
      
      if (!response.ok) {
        if (!silent) {
          console.warn('Failed to fetch incident status:', response.status)
        }
        return
      }
      
      const data = await response.json()
      setIncidentStatus(data)
    } catch (error) {
      if (!silent) {
        console.error('Failed to fetch incident status:', error)
      }
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  const getRCAStatusLabel = (status: string | null) => {
    if (!status) return 'Unknown'
    switch (status) {
      case 'not_started':
        return 'Monitoring'
      case 'in_progress':
        return 'Analyzing Changes'
      case 'completed':
        return 'Suspects Ranked'
      default:
        return status
    }
  }

  const getRCAStatusColor = (status: string | null) => {
    if (!status) return '#666'
    switch (status) {
      case 'not_started':
        return '#2196F3' // Blue
      case 'in_progress':
        return '#FF9800' // Orange
      case 'completed':
        return '#4CAF50' // Green
      default:
        return '#666'
    }
  }

  useEffect(() => {
    fetchIncident()
    fetchAnomalies()
    fetchIncidentStatus()
    
    // Set up polling every 3 seconds
    const interval = setInterval(() => {
      setIsPolling(true)
      fetchIncident(true) // Silent fetch
      fetchAnomalies(true) // Silent fetch
      fetchIncidentStatus(true) // Silent fetch
    }, 3000)
    
    return () => clearInterval(interval)
  }, [incidentId])

  if (loading) {
    return (
      <div className="container">
        <div style={{ padding: '20px', textAlign: 'center' }}>Loading incident details...</div>
      </div>
    )
  }

  if (error || !incident) {
    return (
      <div className="container">
        <div style={{ marginBottom: '20px' }}>
          <Link href="/" className="link">
            ← Back to Incidents
          </Link>
        </div>
        <div className="card" style={{ padding: '20px', color: '#d32f2f', background: '#ffebee', borderRadius: '4px', border: '1px solid #ffcdd2' }}>
          <strong>Error:</strong> {error || 'Incident not found'}
          <br />
          <button 
            onClick={fetchIncident}
            style={{ marginTop: '10px', padding: '8px 16px', background: '#1976d2', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="container">
      <div style={{ marginBottom: '20px' }}>
        <Link href="/" className="link">
          ← Back to Incidents
        </Link>
      </div>

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <h1 style={{ marginBottom: '0' }}>{incident.title}</h1>
          {isPolling && (
            <span style={{ 
              fontSize: '12px', 
              color: '#666',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '5px'
            }}>
              <span style={{
                display: 'inline-block',
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#4caf50',
                animation: 'pulse 1.5s ease-in-out infinite'
              }}></span>
              Updating...
            </span>
          )}
        </div>
        <div style={{ marginBottom: '10px', display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          <span className={`badge badge-${incident.status.toLowerCase()}`}>
            {incident.status}
          </span>
          {incidentStatus && (
            <span style={{
              padding: '4px 12px',
              borderRadius: '12px',
              fontSize: '12px',
              fontWeight: 500,
              background: getRCAStatusColor(incidentStatus.rca_status),
              color: 'white'
            }}>
              {getRCAStatusLabel(incidentStatus.rca_status)}
              {incidentStatus.rca_status === 'completed' && incidentStatus.suspects_count > 0 && (
                <span style={{ marginLeft: '6px' }}>
                  ({incidentStatus.suspects_count} suspects)
                </span>
              )}
            </span>
          )}
        </div>
        <div style={{ color: '#666', marginBottom: '20px' }}>
          <div>Start: {formatDate(incident.start_ts)}</div>
          <div>End: {incident.end_ts ? formatDate(incident.end_ts) : 'Ongoing'}</div>
        </div>
        {incident.summary && (
          <div style={{ marginTop: '20px', padding: '15px', background: '#f9f9f9', borderRadius: '4px' }}>
            <strong>Summary:</strong> {incident.summary}
          </div>
        )}
      </div>

      <div className="card">
        <h2 style={{ marginBottom: '15px' }}>Anomalies</h2>
        {anomalies.length === 0 ? (
          <div>No anomalies found.</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Service</th>
                <th>Metric</th>
                <th>Start Time</th>
                <th>End Time</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {anomalies.map((anomaly) => (
                <tr key={anomaly.id}>
                  <td>{anomaly.service}</td>
                  <td>{anomaly.metric}</td>
                  <td>{formatDate(anomaly.start_ts)}</td>
                  <td>{formatDate(anomaly.end_ts)}</td>
                  <td>{anomaly.score.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h2 style={{ marginBottom: '15px' }}>
          Ranked Suspects
          {isPolling && (
            <span style={{ 
              fontSize: '14px', 
              color: '#666', 
              marginLeft: '10px',
              fontWeight: 'normal'
            }}>
              (updating...)
            </span>
          )}
        </h2>
        {incidentStatus && incidentStatus.rca_status === 'not_started' && (
          <div style={{ 
            padding: '20px', 
            textAlign: 'center', 
            color: '#666',
            background: '#f5f5f5',
            borderRadius: '4px',
            marginBottom: '15px'
          }}>
            <div>RCA analysis has not started yet.</div>
            <div style={{ marginTop: '10px', fontSize: '14px' }}>
              The system is monitoring for anomalies. Suspects will appear here once RCA analysis begins.
            </div>
          </div>
        )}
        {incidentStatus && incidentStatus.rca_status === 'in_progress' && (
          <div style={{ 
            padding: '20px', 
            textAlign: 'center', 
            color: '#666',
            background: '#fff3e0',
            borderRadius: '4px',
            marginBottom: '15px'
          }}>
            <div>RCA analysis in progress...</div>
            <div style={{ marginTop: '10px', fontSize: '14px' }}>
              Analyzing changes and generating suspects. Results will appear here shortly.
            </div>
          </div>
        )}
        <SuspectsTable incidentId={incidentId} />
      </div>

      <div className="card" style={{ marginTop: '20px' }}>
        <h2 style={{ marginBottom: '15px' }}>Activity Log</h2>
        <ActivityLog incidentId={incidentId} limit={30} />
      </div>
    </div>
  )
}


