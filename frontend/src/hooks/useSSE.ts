import { useState, useEffect, useRef } from 'react';

interface SSEProgress {
  status: 'crawling' | 'processing' | 'completed' | 'error';
  pages_found?: number;
  message?: string;
}

interface SSEResult {
  markdown: string;
  job_id: string;
}

export function useSSE(jobId: string | null) {
  const [status, setStatus] = useState<SSEProgress['status'] | null>(null);
  const [progress, setProgress] = useState<SSEProgress | null>(null);
  const [result, setResult] = useState<SSEResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const apiUrl = import.meta.env.VITE_API_URL || '';
    const es = new EventSource(`${apiUrl}/api/generate/${jobId}/stream`);
    eventSourceRef.current = es;

    es.addEventListener('progress', (e) => {
      const data: SSEProgress = JSON.parse(e.data);
      setStatus(data.status);
      setProgress(data);
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

  return { status, progress, result, error };
}
