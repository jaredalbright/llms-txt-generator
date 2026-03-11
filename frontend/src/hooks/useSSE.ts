import { useState, useEffect, useRef } from 'react';
import type { JobStatus, PipelineStep, StepInfo } from '../types';

interface SSEProgress {
  status: JobStatus;
  pages_found?: number;
  message?: string;
  step?: PipelineStep;
  step_state?: 'started' | 'progress' | 'completed';
  summary?: string;
  detail?: string;
}

interface SSEResult {
  markdown: string;
  job_id: string;
}

const STEP_ORDER: PipelineStep[] = ['crawl', 'metadata', 'fetch_homepage', 'ai_categorize', 'fetch_content', 'summarize', 'assemble'];
const MAX_VISIBLE_RECONNECTS = 3;

export function useSSE(jobId: string | null) {
  const [status, setStatus] = useState<SSEProgress['status'] | null>(null);
  const [result, setResult] = useState<SSEResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [steps, setSteps] = useState<StepInfo[]>([]);
  const closedIntentionallyRef = useRef(false);
  const visibleFailCountRef = useRef(0);
  const esRef = useRef<EventSource | null>(null);
  const connectRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (!jobId) return;

    setSteps([]);
    setError(null);
    closedIntentionallyRef.current = false;
    visibleFailCountRef.current = 0;

    const apiUrl = import.meta.env.VITE_API_URL || '';
    const url = `${apiUrl}/api/generate/${jobId}/stream`;

    function connect() {
      if (closedIntentionallyRef.current) return;

      // Close stale connection before opening a new one
      esRef.current?.close();

      const es = new EventSource(url);
      esRef.current = es;

      es.addEventListener('progress', (e) => {
        const data: SSEProgress = JSON.parse(e.data);
        setStatus(data.status);
        setError(null);
        visibleFailCountRef.current = 0;

        if (data.step && data.step_state) {
          setSteps(prev => {
            const updated = [...prev];
            const existingIdx = updated.findIndex(s => s.step === data.step);

            if (data.step_state === 'started') {
              if (existingIdx >= 0) {
                updated[existingIdx] = { step: data.step!, state: 'active', message: data.message || '', details: [] };
              } else {
                const stepIdx = STEP_ORDER.indexOf(data.step!);
                for (let i = 0; i < stepIdx; i++) {
                  if (!updated.find(s => s.step === STEP_ORDER[i])) {
                    updated.push({ step: STEP_ORDER[i]!, state: 'completed', message: '', summary: '', details: [] });
                  }
                }
                updated.push({ step: data.step!, state: 'active', message: data.message || '', details: [] });
              }
            } else if (data.step_state === 'progress') {
              if (existingIdx >= 0) {
                const existing = updated[existingIdx]!;
                const newDetails = data.detail ? [...existing.details, data.detail] : existing.details;
                updated[existingIdx] = { ...existing, message: data.message || existing.message, details: newDetails };
              } else {
                updated.push({ step: data.step!, state: 'active', message: data.message || '', details: data.detail ? [data.detail] : [] });
              }
            } else if (data.step_state === 'completed') {
              if (existingIdx >= 0) {
                const existing = updated[existingIdx]!;
                updated[existingIdx] = { ...existing, state: 'completed', message: data.message || existing.message, summary: data.summary };
              } else {
                updated.push({ step: data.step!, state: 'completed', message: data.message || '', summary: data.summary, details: [] });
              }
            }

            updated.sort((a, b) => STEP_ORDER.indexOf(a.step) - STEP_ORDER.indexOf(b.step));
            return updated;
          });
        }
      });

      es.addEventListener('complete', (e) => {
        const data: SSEResult = JSON.parse(e.data);
        setStatus('completed');
        setResult(data);
        closedIntentionallyRef.current = true;
        es.close();
      });

      es.addEventListener('error', (e) => {
        if (closedIntentionallyRef.current) return;

        // Server-sent error events include data; native connection errors don't
        const messageEvent = e as MessageEvent;
        if (messageEvent.data) {
          try {
            const data = JSON.parse(messageEvent.data);
            setError(data.message);
            setStatus('error');
            closedIntentionallyRef.current = true;
            es.close();
            return;
          } catch {
            // Failed to parse — treat as connection error below
          }
        }

        // Native connection error — only act if truly CLOSED
        // If tab is hidden, silently close; we reconnect on visibility change.
        // If tab is visible, count failures and show error after MAX retries.
        if (es.readyState === EventSource.CLOSED) {
          es.close();
          if (document.hidden) {
            // Tab not visible — don't count, don't show error.
            // visibilitychange handler will reconnect when user returns.
            return;
          }
          visibleFailCountRef.current++;
          if (visibleFailCountRef.current < MAX_VISIBLE_RECONNECTS) {
            connect();
          } else {
            setError('Connection lost.');
          }
        }
      });
    }

    connectRef.current = connect;

    // Reconnect when tab becomes visible again
    function onVisibilityChange() {
      if (document.hidden || closedIntentionallyRef.current) return;
      const es = esRef.current;
      if (!es || es.readyState === EventSource.CLOSED) {
        visibleFailCountRef.current = 0;
        setError(null);
        connect();
      }
    }

    document.addEventListener('visibilitychange', onVisibilityChange);
    connect();

    return () => {
      closedIntentionallyRef.current = true;
      connectRef.current = null;
      document.removeEventListener('visibilitychange', onVisibilityChange);
      esRef.current?.close();
    };
  }, [jobId]);

  return { status, result, error, steps };
}
