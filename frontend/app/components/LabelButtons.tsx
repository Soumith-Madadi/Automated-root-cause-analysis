'use client'

import { useState, MouseEvent, useEffect, useRef } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Module-level log to verify file is loaded
console.log('[DEBUG] LabelButtons.tsx file LOADED', { API_URL });

interface LabelButtonsProps {
  incidentId: string
  suspectId: string
  initialMessage?: string | null
  onLabeled?: (message: string | null) => void
}

export default function LabelButtons({ incidentId, suspectId, initialMessage, onLabeled }: LabelButtonsProps) {
  console.log('[DEBUG] LabelButtons component RENDERING', { incidentId, suspectId, initialMessage, hasOnLabeled: !!onLabeled });
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(initialMessage || null)
  
  // Update message when initialMessage prop changes (from parent state)
  useEffect(() => {
    if (initialMessage !== undefined) {
      setMessage(initialMessage)
    }
  }, [initialMessage])
  const componentIdRef = useRef(Math.random().toString(36).substring(7))
  const prevMessageRef = useRef<string | null>(null)
  
  // Track message state changes
  useEffect(() => {
    if (prevMessageRef.current !== message) {
      console.log('[DEBUG-HYP-D] Message state changed', { componentId: componentIdRef.current, oldMessage: prevMessageRef.current, newMessage: message, suspectId });
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/b534d4f6-ddc4-49d2-8b5a-e065c6c5b744', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ location: 'LabelButtons.tsx:messageStateChange', message: 'Message state changed', data: { componentId: componentIdRef.current, oldMessage: prevMessageRef.current, newMessage: message, suspectId }, timestamp: Date.now(), sessionId: 'debug-session', runId: 'run1', hypothesisId: 'D' }) }).catch(() => {});
      // #endregion
      prevMessageRef.current = message
    }
  }, [message, suspectId])
  
  // #region agent log
  useEffect(() => {
    console.log('[DEBUG-HYP-B] LabelButtons MOUNTED', { componentId: componentIdRef.current, suspectId, incidentId });
    fetch('http://127.0.0.1:7242/ingest/b534d4f6-ddc4-49d2-8b5a-e065c6c5b744', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ location: 'LabelButtons.tsx:mount', message: 'Component mounted', data: { componentId: componentIdRef.current, suspectId, incidentId }, timestamp: Date.now(), sessionId: 'debug-session', runId: 'run1', hypothesisId: 'B' }) }).catch(() => {});
    return () => {
      console.log('[DEBUG-HYP-B] LabelButtons UNMOUNTED', { componentId: componentIdRef.current, suspectId });
      fetch('http://127.0.0.1:7242/ingest/b534d4f6-ddc4-49d2-8b5a-e065c6c5b744', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ location: 'LabelButtons.tsx:unmount', message: 'Component unmounted', data: { componentId: componentIdRef.current, suspectId }, timestamp: Date.now(), sessionId: 'debug-session', runId: 'run1', hypothesisId: 'B' }) }).catch(() => {});
    };
  }, []);
  // #endregion

  const submitLabel = async (label: number, e?: MouseEvent<HTMLButtonElement>) => {
    try {
      console.log('[DEBUG] submitLabel ENTRY', { componentId: componentIdRef.current, label, suspectId, incidentId, hasEvent: !!e });
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/b534d4f6-ddc4-49d2-8b5a-e065c6c5b744', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ location: 'LabelButtons.tsx:submitLabel:entry', message: 'submitLabel called', data: { componentId: componentIdRef.current, label, suspectId, hasEvent: !!e, eventType: e?.type, defaultPrevented: e?.defaultPrevented }, timestamp: Date.now(), sessionId: 'debug-session', runId: 'run1', hypothesisId: 'C' }) }).catch((err) => console.error('[DEBUG] Log fetch failed:', err));
      // #endregion
    if (e) {
      e.preventDefault()
      e.stopPropagation()
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/b534d4f6-ddc4-49d2-8b5a-e065c6c5b744', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ location: 'LabelButtons.tsx:submitLabel:preventDefault', message: 'Event preventDefault/stopPropagation called', data: { componentId: componentIdRef.current, defaultPrevented: e.defaultPrevented }, timestamp: Date.now(), sessionId: 'debug-session', runId: 'run1', hypothesisId: 'C' }) }).catch(() => {});
      // #endregion
    }
      console.log('[DEBUG] Setting loading=true, message=null');
      setLoading(true)
      setMessage(null)
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/b534d4f6-ddc4-49d2-8b5a-e065c6c5b744', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ location: 'LabelButtons.tsx:submitLabel:beforeFetch', message: 'Before fetch - state set', data: { componentId: componentIdRef.current, loading: true, message: null }, timestamp: Date.now(), sessionId: 'debug-session', runId: 'run1', hypothesisId: 'D' }) }).catch((err) => console.error('[DEBUG] Log fetch failed:', err));
      // #endregion
      const url = `${API_URL}/incidents/${incidentId}/label?suspect_id=${suspectId}&label=${label}`
      console.log('[DEBUG] Making fetch request to:', url)
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })
      console.log('[DEBUG] Response received', { status: response.status, statusText: response.statusText })
      if (response.ok) {
        const data = await response.json().catch(() => ({}))
        console.log('[DEBUG] Label submitted successfully:', data)
        const successMsg = label === 1 ? 'Marked as cause ✓' : 'Marked as not cause ✓'
        console.log('[DEBUG] Setting message:', successMsg)
        setMessage(successMsg)
        console.log('[DEBUG] Message state set, current message:', successMsg)
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/b534d4f6-ddc4-49d2-8b5a-e065c6c5b744', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ location: 'LabelButtons.tsx:submitLabel:success', message: 'Message set after success', data: { componentId: componentIdRef.current, message: successMsg }, timestamp: Date.now(), sessionId: 'debug-session', runId: 'run1', hypothesisId: 'D' }) }).catch((err) => console.error('[DEBUG] Log fetch failed:', err));
        // #endregion
        // Notify parent immediately so it can preserve the message state
        console.log('[DEBUG] Calling onLabeled callback with message:', successMsg)
        if (onLabeled) {
          onLabeled(successMsg)
        } else {
          console.warn('[DEBUG] onLabeled callback is not defined!')
        }
      } else {
        const data = await response.json().catch(() => ({ detail: 'Failed to submit label' }))
        console.error('Label submission failed:', data)
        setMessage(data.detail || 'Failed to submit label')
      }
    } catch (error) {
      console.error('[DEBUG] submitLabel CATCH BLOCK - Error:', error)
      setMessage('Error submitting label')
    } finally {
      console.log('[DEBUG] submitLabel FINALLY - Setting loading=false')
      setLoading(false)
    }
  }

  return (
    <div 
      style={{ display: 'flex', gap: '8px', alignItems: 'center', minWidth: '200px' }}
      onClick={(e) => {
        e.stopPropagation()
      }}
    >
      <button
        type="button"
        className="btn btn-success"
        onClick={(e) => {
          try {
            console.log('[DEBUG] Cause button clicked - START', { componentId: componentIdRef.current, suspectId });
            // #region agent log
            fetch('http://127.0.0.1:7242/ingest/b534d4f6-ddc4-49d2-8b5a-e065c6c5b744', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ location: 'LabelButtons.tsx:button:onClick', message: 'Cause button onClick handler', data: { componentId: componentIdRef.current, target: e.target?.tagName, currentTarget: e.currentTarget?.tagName, bubbles: e.bubbles, cancelable: e.cancelable }, timestamp: Date.now(), sessionId: 'debug-session', runId: 'run1', hypothesisId: 'A' }) }).catch((err) => console.error('[DEBUG] Log fetch failed:', err));
            // #endregion
            e.preventDefault()
            e.stopPropagation()
            e.nativeEvent.stopImmediatePropagation()
            console.log('[DEBUG] After preventDefault', { defaultPrevented: e.defaultPrevented });
            // #region agent log
            fetch('http://127.0.0.1:7242/ingest/b534d4f6-ddc4-49d2-8b5a-e065c6c5b744', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ location: 'LabelButtons.tsx:button:afterPrevent', message: 'After preventDefault on Cause button', data: { componentId: componentIdRef.current, defaultPrevented: e.defaultPrevented }, timestamp: Date.now(), sessionId: 'debug-session', runId: 'run1', hypothesisId: 'A' }) }).catch((err) => console.error('[DEBUG] Log fetch failed:', err));
            // #endregion
            console.log('[DEBUG] Calling submitLabel(1)');
            submitLabel(1, e).catch((err) => {
              console.error('[DEBUG] submitLabel error:', err);
            });
            return false
          } catch (error) {
            console.error('[DEBUG] onClick handler error:', error);
            throw error;
          }
        }}
        disabled={loading}
        style={{ 
          fontSize: '12px', 
          padding: '4px 8px', 
          cursor: loading ? 'not-allowed' : 'pointer',
          opacity: loading ? 0.6 : 1
        }}
      >
        {loading ? '...' : '✓'} Cause
      </button>
      <button
        type="button"
        className="btn btn-danger"
        onClick={(e) => {
          try {
            console.log('[DEBUG] Not Cause button clicked - START', { componentId: componentIdRef.current, suspectId });
            e.preventDefault()
            e.stopPropagation()
            e.nativeEvent.stopImmediatePropagation()
            console.log('[DEBUG] Calling submitLabel(0)');
            submitLabel(0, e).catch((err) => {
              console.error('[DEBUG] submitLabel error:', err);
            });
            return false
          } catch (error) {
            console.error('[DEBUG] onClick handler error:', error);
            throw error;
          }
        }}
        disabled={loading}
        style={{ 
          fontSize: '12px', 
          padding: '4px 8px', 
          cursor: loading ? 'not-allowed' : 'pointer',
          opacity: loading ? 0.6 : 1
        }}
      >
        {loading ? '...' : '✗'} Not Cause
      </button>
      {loading && (
        <span style={{ fontSize: '12px', color: '#666' }}>Submitting...</span>
      )}
      {message && !loading && (
        <span 
          style={{ 
            fontSize: '12px', 
            color: '#28a745', 
            fontWeight: 'bold',
            whiteSpace: 'nowrap',
            padding: '2px 4px',
            backgroundColor: '#d4edda',
            borderRadius: '3px'
          }}
        >
          {message}
        </span>
      )}
    </div>
  )
}


