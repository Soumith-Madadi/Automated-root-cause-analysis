'use client'

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import ActivityLog from '@/app/components/ActivityLog'

const MOCK_SERVICE_URL = process.env.NEXT_PUBLIC_MOCK_SERVICE_URL || 'http://localhost:8080'
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface DemoState {
  service: string
  current_p95_latency_ms: number
  feature_flags: Record<string, boolean>
  configs: Record<string, any>
  request_count: number
  status: string
}

export default function DemoPage() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [demoState, setDemoState] = useState<DemoState | null>(null)
  const [latency, setLatency] = useState<number | null>(null)

  useEffect(() => {
    fetchDemoState()
    fetchLatestLatency()
    // Poll demo state every 5 seconds
    const demoInterval = setInterval(fetchDemoState, 5000)
    // Poll latest latency from Grafana/ClickHouse every 5 seconds
    const latencyInterval = setInterval(fetchLatestLatency, 5000)
    return () => {
      clearInterval(demoInterval)
      clearInterval(latencyInterval)
    }
  }, [])

  const fetchLatestLatency = async () => {
    try {
      const response = await fetch(
        `${API_URL}/services/metrics/latest?service=mock-service&metric=p95_latency_ms`
      )
      if (response.ok) {
        const data = await response.json()
        if (data.value !== null && data.value !== undefined) {
          setLatency(data.value)
        }
      }
    } catch (error) {
      console.error('Failed to fetch latest latency:', error)
    }
  }

  const fetchDemoState = async () => {
    try {
      const response = await fetch(`${MOCK_SERVICE_URL}/api/demo`)
      if (response.ok) {
        const data = await response.json()
        setDemoState(data)
      }
    } catch (error) {
      console.error('Failed to fetch demo state:', error)
    }
  }

  const handleLoadUsers = async () => {
    setLoading(true)
    setError(null)

    try {
      // Enable the enable_extra_processing feature flag to trigger gradual latency increase
      const flagResponse = await fetch(
        `${MOCK_SERVICE_URL}/api/feature-flags/enable_extra_processing/toggle`,
        {
          method: 'POST'
        }
      )
      
      if (!flagResponse.ok) {
        throw new Error(`Failed to enable feature flag: ${flagResponse.status}`)
      }
      
      const flagData = await flagResponse.json()
      console.log('Feature flag toggled:', flagData)
      
      // Update demo state to reflect the change
      await fetchDemoState()
      // Fetch latest latency immediately
      await fetchLatestLatency()
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to trigger production change')
    } finally {
      setLoading(false)
    }
  }

  const getLatencyColor = (latencyMs: number | null) => {
    if (!latencyMs) return '#666'
    if (latencyMs < 100) return '#4CAF50' // Green
    if (latencyMs < 300) return '#FF9800' // Orange
    return '#F44336' // Red
  }

  const getLatencyStatus = (latencyMs: number | null) => {
    if (!latencyMs) return 'Unknown'
    if (latencyMs < 100) return 'Fast'
    if (latencyMs < 300) return 'Moderate'
    return 'Slow'
  }

  return (
    <div className="container">
      <div style={{ marginBottom: '20px' }}>
        <Link href="/" className="link">
          ← Back to RCA Dashboard
        </Link>
      </div>

      <div className="card">
        <h1 style={{ marginBottom: '10px' }}>Demo Service</h1>
        <p style={{ color: '#666', marginBottom: '20px' }}>
          This is a simulated service that responds to requests. 
          Watch how latency changes when operational changes are made.
        </p>

        <div style={{ 
          display: 'flex', 
          gap: '20px', 
          alignItems: 'center',
          marginBottom: '30px',
          padding: '15px',
          background: '#f5f5f5',
          borderRadius: '4px'
        }}>
          <button
            onClick={handleLoadUsers}
            disabled={loading}
            style={{
              padding: '12px 24px',
              fontSize: '16px',
              background: loading ? '#ccc' : '#1976d2',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontWeight: 500
            }}
          >
            {loading ? 'Loading...' : 'Production Change'}
          </button>

          {latency !== null && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                background: getLatencyColor(latency),
                boxShadow: `0 0 8px ${getLatencyColor(latency)}`
              }}></div>
              <span style={{ fontWeight: 500 }}>
                Current Latency: <span style={{ color: getLatencyColor(latency) }}>
                  {latency.toFixed(0)}ms ({getLatencyStatus(latency)})
                </span>
              </span>
            </div>
          )}
        </div>

        {loading && (
          <div style={{ 
            padding: '20px', 
            textAlign: 'center',
            background: '#f0f0f0',
            borderRadius: '4px',
            marginBottom: '20px'
          }}>
            <div style={{
              display: 'inline-block',
              width: '40px',
              height: '40px',
              border: '4px solid #f3f3f3',
              borderTop: '4px solid #1976d2',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite',
              marginBottom: '10px'
            }}></div>
            <div>Processing production change...</div>
          </div>
        )}

        {error && (
          <div style={{
            padding: '15px',
            background: '#ffebee',
            color: '#d32f2f',
            borderRadius: '4px',
            marginBottom: '20px',
            border: '1px solid #ffcdd2'
          }}>
            <strong>Error:</strong> {error}
          </div>
        )}

        {demoState && (
          <div style={{
            padding: '15px',
            background: '#f9f9f9',
            borderRadius: '4px',
            marginBottom: '20px',
            fontSize: '14px'
          }}>
            <h3 style={{ marginTop: 0, marginBottom: '10px' }}>Service State:</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
              <div>
                <strong>Feature Flags:</strong>
                <ul style={{ margin: '5px 0', paddingLeft: '20px' }}>
                  {Object.entries(demoState.feature_flags).map(([flag, enabled]) => (
                    <li key={flag}>
                      <code>{flag}</code>: {enabled ? '✓ Enabled' : '✗ Disabled'}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <strong>Configs:</strong>
                <ul style={{ margin: '5px 0', paddingLeft: '20px' }}>
                  {Object.entries(demoState.configs).map(([key, value]) => (
                    <li key={key}>
                      <code>{key}</code>: {String(value)}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            <div style={{ marginTop: '10px', color: '#666' }}>
              Total requests: {demoState.request_count}
            </div>
          </div>
        )}

        <div style={{ marginTop: '30px', display: 'flex', gap: '15px', flexWrap: 'wrap' }}>
          <Link 
            href="http://localhost:3000" 
            target="_blank"
            style={{
              padding: '10px 20px',
              background: '#1976d2',
              color: 'white',
              textDecoration: 'none',
              borderRadius: '4px',
              display: 'inline-block'
            }}
          >
            View Latency Chart (Grafana)
          </Link>
          <Link 
            href="/" 
            style={{
              padding: '10px 20px',
              background: '#4CAF50',
              color: 'white',
              textDecoration: 'none',
              borderRadius: '4px',
              display: 'inline-block'
            }}
          >
            View RCA Dashboard
          </Link>
        </div>
      </div>

      <div className="card" style={{ marginTop: '20px' }}>
        <h2 style={{ marginBottom: '15px' }}>System Activity</h2>
        <ActivityLog service="mock-service" limit={20} />
      </div>

      <style jsx>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}
