import { useState, useEffect, useRef } from 'react';
import type { PipelineStep, StepInfo } from '../types';

interface SSEProgress {
  status: 'crawling' | 'processing' | 'extracting_content' | 'summarizing' | 'completed' | 'error';
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

const STEP_ORDER: PipelineStep[] = ['crawl', 'metadata', 'ai_categorize', 'fetch_content', 'assemble'];

export function useSSE(jobId: string | null) {
  const [status, setStatus] = useState<SSEProgress['status'] | null>(null);
  const [progress, setProgress] = useState<SSEProgress | null>(null);
  const [result, setResult] = useState<SSEResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [steps, setSteps] = useState<StepInfo[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!jobId) return;

    setSteps([]);

    const apiUrl = import.meta.env.VITE_API_URL || '';
    const es = new EventSource(`${apiUrl}/api/generate/${jobId}/stream`);
    eventSourceRef.current = es;

    es.addEventListener('progress', (e) => {
      const data: SSEProgress = JSON.parse(e.data);
      setStatus(data.status);
      setProgress(data);

      if (data.step && data.step_state) {
        setSteps(prev => {
          const updated = [...prev];
          const existingIdx = updated.findIndex(s => s.step === data.step);

          if (data.step_state === 'started') {
            if (existingIdx >= 0) {
              updated[existingIdx] = { step: data.step!, state: 'active', message: data.message || '', details: [] };
            } else {
              // Add any skipped pending steps
              const stepIdx = STEP_ORDER.indexOf(data.step!);
              for (let i = 0; i < stepIdx; i++) {
                if (!updated.find(s => s.step === STEP_ORDER[i])) {
                  updated.push({ step: STEP_ORDER[i], state: 'completed', message: '', summary: '', details: [] });
                }
              }
              updated.push({ step: data.step!, state: 'active', message: data.message || '', details: [] });
            }
          } else if (data.step_state === 'progress') {
            if (existingIdx >= 0) {
              const existing = updated[existingIdx];
              const newDetails = data.detail ? [...existing.details, data.detail] : existing.details;
              updated[existingIdx] = { ...existing, message: data.message || existing.message, details: newDetails };
            } else {
              updated.push({ step: data.step!, state: 'active', message: data.message || '', details: data.detail ? [data.detail] : [] });
            }
          } else if (data.step_state === 'completed') {
            if (existingIdx >= 0) {
              updated[existingIdx] = { ...updated[existingIdx], state: 'completed', message: data.message || updated[existingIdx].message, summary: data.summary };
            } else {
              updated.push({ step: data.step!, state: 'completed', message: data.message || '', summary: data.summary, details: [] });
            }
          }

          // Sort by canonical order
          updated.sort((a, b) => STEP_ORDER.indexOf(a.step) - STEP_ORDER.indexOf(b.step));
          return updated;
        });
      }
    });

    es.addEventListener('complete', (e) => {
      const data: SSEResult = JSON.parse(e.data);
      setStatus('completed');
      setResult(data);
      es.close();
    });

    es.addEventListener('error', (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data);
        setError(data.message);
        setStatus('error');
      } catch {
        setError('Connection lost. Reconnecting...');
      }
    });

    return () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, [jobId]);

  return { status, progress, result, error, steps };
}
