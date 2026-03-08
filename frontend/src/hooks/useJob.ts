import { useState, useCallback, useRef, useEffect } from 'react';
import { startGeneration, reprompt as repromptApi, validate } from '../lib/api';
import { useSSE } from './useSSE';
import type { JobStatus, ValidationIssue } from '../types';

export function useJob() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [url, setUrl] = useState<string>('');
  const [markdown, setMarkdown] = useState<string>('');
  const [isReprompting, setIsReprompting] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [isValid, setIsValid] = useState(true);
  const [validationIssues, setValidationIssues] = useState<ValidationIssue[]>([]);
  const appliedResultRef = useRef<string | null>(null);
  const validatedMarkdownRef = useRef<string | null>(null);

  const { status, progress, result, error, steps } = useSSE(jobId);

  // When SSE completes, apply result markdown only once
  if (result && result.markdown && status === 'completed' && appliedResultRef.current !== result.markdown) {
    appliedResultRef.current = result.markdown;
    setMarkdown(result.markdown);
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

  const [clientInfo, setClientInfo] = useState<string | undefined>(undefined);

  const submitJob = useCallback(async (inputUrl: string, inputClientInfo?: string) => {
    setUrl(inputUrl);
    setClientInfo(inputClientInfo);
    setMarkdown('');
    appliedResultRef.current = null;
    setJobId(null);

    const response = await startGeneration({ url: inputUrl, client_info: inputClientInfo });
    setJobId(response.job_id);
  }, []);

  const regenerate = useCallback(async () => {
    if (!url) return;
    setMarkdown('');
    appliedResultRef.current = null;
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
    isValidating,
    isValid,
    validationIssues,
    jobId,
    steps,
  };
}
