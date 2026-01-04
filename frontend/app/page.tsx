'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Incident {
  id: string
  start_ts: string
  end_ts: string | null
  title: string
  status: string
  summary: string | null
}

export default function Home() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('OPEN')
  const [isPolling, setIsPolling] = useState(false)

  useEffect(() => {
    fetchIncidents()
    
    // Set up polling every 3 seconds
    const interval = setInterval(() => {
      setIsPolling(true)
      fetchIncidents(true) // Silent fetch
    }, 3000)
    
    return () => clearInterval(interval)
  }, [statusFilter])

  const fetchIncidents = async (silent = false) => {
    try {
      if (!silent) {
        setLoading(true)
      }
      setError(null)
      const url = statusFilter
        ? `${API_URL}/incidents?status=${statusFilter}`
        : `${API_URL}/incidents`
      const response = await fetch(url)
      
      if (!response.ok) {
        throw new Error(`Failed to fetch incidents: ${response.status} ${response.statusText}`)
      }
      
      const data = await response.json()
      setIncidents(data.incidents || [])
    } catch (error) {
      console.error('Failed to fetch incidents:', error)
      if (!silent) {
        setError(error instanceof Error ? error.message : 'Failed to load incidents. Please check if the API is running.')
      }
    } finally {
      if (!silent) {
        setLoading(false)
      }
      setIsPolling(false)
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  return (
    <div className="container">
      <div className="header">
        <h1>Root Cause Analysis System</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <Link 
            href="/demo"
            style={{
              padding: '8px 16px',
              background: '#1976d2',
              color: 'white',
              textDecoration: 'none',
              borderRadius: '4px',
              fontSize: '14px',
              fontWeight: 500
            }}
          >
            Demo Service
          </Link>
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
              Live
            </span>
          )}
        </div>
      </div>

      <div className="card">
        <div style={{ marginBottom: '20px', display: 'flex', gap: '10px', alignItems: 'center' }}>
          <label htmlFor="status-filter" style={{ fontWeight: 500 }}>
            Status:
          </label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{
              padding: '8px 12px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontSize: '14px'
            }}
          >
            <option value="">All</option>
            <option value="OPEN">Open</option>
            <option value="CLOSED">Closed</option>
          </select>
        </div>

        {loading ? (
          <div style={{ padding: '20px', textAlign: 'center' }}>Loading incidents...</div>
        ) : error ? (
          <div style={{ padding: '20px', color: '#d32f2f', background: '#ffebee', borderRadius: '4px', border: '1px solid #ffcdd2' }}>
            <strong>Error:</strong> {error}
            <br />
            <button 
              onClick={fetchIncidents}
              style={{ marginTop: '10px', padding: '8px 16px', background: '#1976d2', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
            >
              Retry
            </button>
          </div>
        ) : incidents.length === 0 ? (
          <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
            No incidents found.
            {statusFilter && (
              <div style={{ marginTop: '10px', fontSize: '14px' }}>
                Try selecting "All" to see all incidents.
              </div>
            )}
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Status</th>
                <th>Start Time</th>
                <th>End Time</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map((incident) => (
                <tr key={incident.id}>
                  <td>
                    <Link href={`/incidents/${incident.id}`} className="link">
                      {incident.title}
                    </Link>
                  </td>
                  <td>
                    <span className={`badge badge-${incident.status.toLowerCase()}`}>
                      {incident.status}
                    </span>
                  </td>
                  <td>{formatDate(incident.start_ts)}</td>
                  <td>{incident.end_ts ? formatDate(incident.end_ts) : '-'}</td>
                  <td>
                    <Link href={`/incidents/${incident.id}`} className="link">
                      View Details
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}


