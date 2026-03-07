import { useState, useCallback } from 'react';
import { startGeneration, reprompt as repromptApi } from '../lib/api';
import { useSSE } from './useSSE';
import type { JobStatus } from '../types';

export function useJob() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [url, setUrl] = useState<string>('');
  const [markdown, setMarkdown] = useState<string>('');
  const [isReprompting, setIsReprompting] = useState(false);

  const { status, progress, result, error } = useSSE(jobId);

  // When SSE completes, update markdown
  if (result && result.markdown && result.markdown !== markdown && status === 'completed') {
    setMarkdown(result.markdown);
  }

  const [clientInfo, setClientInfo] = useState<string | undefined>(undefined);

  const submitJob = useCallback(async (inputUrl: string, inputClientInfo?: string) => {
    setUrl(inputUrl);
    setClientInfo(inputClientInfo);
    setMarkdown('');
    setJobId(null);

    const response = await startGeneration({ url: inputUrl, client_info: inputClientInfo });
    setJobId(response.job_id);
  }, []);

  const regenerate = useCallback(async () => {
    if (!url) return;
    setMarkdown('');
    setJobId(null);

    const response = await startGeneration({ url, client_info: clientInfo });
    setJobId(response.job_id);
  }, [url, clientInfo]);

  const reprompt = useCallback(async (instruction: string) => {
    if (!jobId || !markdown) return;
    setIsReprompting(true);

    try {
      const response = await repromptApi({
        job_id: jobId,
        instruction,
        current_markdown: markdown,
      });
      setMarkdown(response.markdown);
    } finally {
      setIsReprompting(false);
    }
  }, [jobId, markdown]);

  const currentStatus: JobStatus | null = status;

  return {
    submitJob,
    regenerate,
    reprompt,
    markdown,
    setMarkdown,
    status: currentStatus,
    progress,
    error,
    isReprompting,
    jobId,
  };
}
