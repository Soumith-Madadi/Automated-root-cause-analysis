'use client'

import { useEffect, useState } from 'react'
import LabelButtons from './LabelButtons'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Suspect {
  id: string
  suspect_type: string
  suspect_key: string
  rank: number
  score: number
  evidence: {
    minutes_before_incident?: number
    is_before_incident?: number
    metric_delta_count?: number
    max_metric_delta?: number
    error_log_delta?: number
    new_error_signature?: number
    diff_keyword_hit?: number
    [key: string]: any
  }
}

interface SuspectsTableProps {
  incidentId: string
}

export default function SuspectsTable({ incidentId }: SuspectsTableProps) {
  console.log('[DEBUG] SuspectsTable component RENDERING', { incidentId });
  const [suspects, setSuspects] = useState<Suspect[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // Track which suspects have been labeled to preserve message state across re-renders
  const [labeledSuspects, setLabeledSuspects] = useState<Map<string, { message: string; timestamp: number }>>(new Map())

  useEffect(() => {
    fetchSuspects()
    
    // Set up polling every 3 seconds
    const interval = setInterval(() => {
      fetchSuspects(true) // Silent fetch
    }, 3000)
    
    return () => clearInterval(interval)
  }, [incidentId])

  const fetchSuspects = async (silent = false) => {
      // #region agent log
      console.log('[DEBUG-HYP-B/D] fetchSuspects called', { silent, incidentId, currentSuspectsCount: suspects.length });
      fetch('http://127.0.0.1:7242/ingest/b534d4f6-ddc4-49d2-8b5a-e065c6c5b744', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ location: 'SuspectsTable.tsx:fetchSuspects:entry', message: 'fetchSuspects called', data: { silent, incidentId, currentSuspectsCount: suspects.length }, timestamp: Date.now(), sessionId: 'debug-session', runId: 'run1', hypothesisId: 'B' }) }).catch(() => {});
      // #endregion
    try {
      if (!silent) {
        setLoading(true)
      }
      setError(null)
      const response = await fetch(`${API_URL}/incidents/${incidentId}/suspects`)
      
      if (!response.ok) {
        throw new Error(`Failed to fetch suspects: ${response.status}`)
      }
      
      const data = await response.json()
      // #region agent log
      console.log('[DEBUG-HYP-D] Before setSuspects', { silent, newSuspectsCount: data.suspects?.length || 0, oldSuspectsCount: suspects.length });
      fetch('http://127.0.0.1:7242/ingest/b534d4f6-ddc4-49d2-8b5a-e065c6c5b744', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ location: 'SuspectsTable.tsx:fetchSuspects:beforeSetSuspects', message: 'Before setSuspects call', data: { silent, newSuspectsCount: data.suspects?.length || 0, oldSuspectsCount: suspects.length }, timestamp: Date.now(), sessionId: 'debug-session', runId: 'run1', hypothesisId: 'D' }) }).catch(() => {});
      // #endregion
      setSuspects(data.suspects || [])
      // #region agent log
      console.log('[DEBUG-HYP-D] After setSuspects', { silent, suspectsCount: data.suspects?.length || 0 });
      fetch('http://127.0.0.1:7242/ingest/b534d4f6-ddc4-49d2-8b5a-e065c6c5b744', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ location: 'SuspectsTable.tsx:fetchSuspects:afterSetSuspects', message: 'After setSuspects call', data: { silent, suspectsCount: data.suspects?.length || 0 }, timestamp: Date.now(), sessionId: 'debug-session', runId: 'run1', hypothesisId: 'D' }) }).catch(() => {});
      // #endregion
    } catch (error) {
      console.error('Failed to fetch suspects:', error)
      setError(error instanceof Error ? error.message : 'Failed to load suspects')
    } finally {
      if (!silent) {
        setLoading(false)
      }
    }
  }

  const formatEvidence = (evidence: Suspect['evidence']) => {
    const items = []
    if (evidence.minutes_before_incident !== undefined) {
      items.push(`Time: ${evidence.minutes_before_incident.toFixed(1)} min before`)
    }
    if (evidence.max_metric_delta !== undefined && evidence.max_metric_delta > 0) {
      items.push(`Metric delta: ${(evidence.max_metric_delta * 100).toFixed(1)}%`)
    }
    if (evidence.error_log_delta !== undefined && evidence.error_log_delta > 0) {
      items.push(`Error log delta: ${evidence.error_log_delta.toFixed(1)}x`)
    }
    if (evidence.new_error_signature === 1) {
      items.push('New error signature detected')
    }
    if (evidence.diff_keyword_hit === 1) {
      items.push('Diff contains relevant keywords')
    }
    return items.length > 0 ? items.join(', ') : 'No evidence'
  }

  if (loading) {
    return <div style={{ padding: '20px', textAlign: 'center' }}>Loading suspects...</div>
  }

  if (error) {
    return (
      <div style={{ padding: '20px', color: '#d32f2f', background: '#ffebee', borderRadius: '4px', border: '1px solid #ffcdd2' }}>
        <strong>Error:</strong> {error}
        <br />
        <button 
          onClick={fetchSuspects}
          style={{ marginTop: '10px', padding: '8px 16px', background: '#1976d2', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
        >
          Retry
        </button>
      </div>
    )
  }

  if (suspects.length === 0) {
    return (
      <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
        <div>No suspects found. RCA may still be processing.</div>
        <div style={{ marginTop: '10px', fontSize: '14px' }}>
          This usually takes 10-30 seconds after incident creation.
        </div>
        <button 
          onClick={fetchSuspects}
          style={{ marginTop: '10px', padding: '8px 16px', background: '#1976d2', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
        >
          Refresh
        </button>
      </div>
    )
  }

  return (
    <div>
      <table className="table">
        <thead>
          <tr>
            <th>Rank</th>
            <th>Type</th>
            <th>Key</th>
            <th>Score</th>
            <th>Evidence</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {suspects.map((suspect) => (
            <tr 
              key={suspect.id}
              onClick={(e) => {
                // #region agent log
                fetch('http://127.0.0.1:7242/ingest/b534d4f6-ddc4-49d2-8b5a-e065c6c5b744', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ location: 'SuspectsTable.tsx:tr:onClick', message: 'Table row clicked', data: { suspectId: suspect.id, target: e.target?.tagName, currentTarget: e.currentTarget?.tagName }, timestamp: Date.now(), sessionId: 'debug-session', runId: 'run1', hypothesisId: 'A' }) }).catch(() => {});
                // #endregion
              }}
            >
              <td>
                <strong>#{suspect.rank}</strong>
              </td>
              <td>{suspect.suspect_type}</td>
              <td>
                <code style={{ fontSize: '12px' }}>{suspect.suspect_key.substring(0, 8)}...</code>
              </td>
              <td>{suspect.score.toFixed(2)}</td>
              <td style={{ fontSize: '12px', color: '#666' }}>
                {formatEvidence(suspect.evidence)}
              </td>
              <td>
                <LabelButtons
                  incidentId={incidentId}
                  suspectId={suspect.id}
                  initialMessage={labeledSuspects.get(suspect.id)?.message || null}
                  onLabeled={(message) => {
                    // Store the label message
                    if (message) {
                      setLabeledSuspects(prev => {
                        const newMap = new Map(prev)
                        newMap.set(suspect.id, { message, timestamp: Date.now() })
                        return newMap
                      })
                      // Don't clear the message automatically - keep it until suspect is removed or user changes it
                      // The message will persist across re-renders
                    } else {
                      // If message is null, remove it from the map
                      setLabeledSuspects(prev => {
                        const newMap = new Map(prev)
                        newMap.delete(suspect.id)
                        return newMap
                      })
                    }
                  }}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}


