import { useState, useCallback, useRef, useEffect } from 'react';
import { startGeneration, validate } from '../lib/api';
import { useSSE } from './useSSE';
import { useSessionState } from './useSessionState';
import type { JobStatus, ValidationIssue } from '../types';

export function useJob() {
  const [jobId, setJobId] = useSessionState<string | null>('job_id', null);
  const [url, setUrl] = useSessionState<string>('job_url', '');
  const [markdown, setMarkdown] = useSessionState<string>('job_markdown', '');
  const [savedStatus, setSavedStatus] = useSessionState<JobStatus | null>('job_status', null);
  const [isValidating, setIsValidating] = useState(false);
  const [isValid, setIsValid] = useState(true);
  const [validationIssues, setValidationIssues] = useState<ValidationIssue[]>([]);
  const appliedResultRef = useRef<string | null>(null);
  const validatedMarkdownRef = useRef<string | null>(null);

  const { status: liveStatus, result, error, steps } = useSSE(jobId);

  // Use live status when a job is active, otherwise fall back to saved status
  const status = liveStatus ?? savedStatus;

  // When SSE completes, apply result markdown only once and persist status
  if (result && result.markdown && liveStatus === 'completed' && appliedResultRef.current !== result.markdown) {
    appliedResultRef.current = result.markdown;
    setMarkdown(result.markdown);
    setSavedStatus('completed');
  }

  // Debounced validation when markdown changes
  useEffect(() => {
    if (!markdown || status !== 'completed') return;
    // Skip if this markdown was already validated
    if (validatedMarkdownRef.current === markdown) return;

    setIsValidating(true);
    setIsValid(false);

    const timer = setTimeout(async () => {
      // Re-check in case markdown changed during the delay
      if (validatedMarkdownRef.current === markdown) {
        setIsValidating(false);
        return;
      }
      try {
        const res = await validate({ markdown });
        // Only apply if markdown hasn't changed during the request
        validatedMarkdownRef.current = markdown;
        setIsValid(res.valid);
        setValidationIssues(res.issues);
      } catch {
        // On error, allow download anyway
        setIsValid(true);
        setValidationIssues([]);
      } finally {
        setIsValidating(false);
      }
    }, 2000);

    return () => clearTimeout(timer);
  }, [markdown, status]);

  const [clientInfo, setClientInfo] = useSessionState<string | undefined>('job_client_info', undefined);
  const [promptsContext, setPromptsContext] = useSessionState<string[] | undefined>('job_prompts_context', undefined);

  const submitJob = useCallback(async (inputUrl: string, inputClientInfo?: string, inputPromptsContext?: string[]) => {
    setUrl(inputUrl);
    setClientInfo(inputClientInfo);
    setPromptsContext(inputPromptsContext);
    setMarkdown('');
    setSavedStatus(null);
    appliedResultRef.current = null;
    setJobId(null);

    const response = await startGeneration({ url: inputUrl, client_info: inputClientInfo, prompts_context: inputPromptsContext });
    setJobId(response.job_id);
  }, []);

  const regenerate = useCallback(async () => {
    if (!url) return;
    setMarkdown('');
    setSavedStatus(null);
    appliedResultRef.current = null;
    setJobId(null);

    const response = await startGeneration({ url, client_info: clientInfo, prompts_context: promptsContext });
    setJobId(response.job_id);
  }, [url, clientInfo, promptsContext]);

  return {
    submitJob,
    regenerate,
    markdown,
    setMarkdown,
    status,
    error,
    isValidating,
    isValid,
    validationIssues,
    jobId,
    steps,
  };
}
