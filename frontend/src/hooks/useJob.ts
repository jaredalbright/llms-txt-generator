import { useState, useCallback, useRef, useEffect } from 'react';
import { startGeneration, validate } from '../lib/api';
import { useSSE } from './useSSE';
import { useSessionState } from './useSessionState';
import type { JobStatus, ValidationIssue } from '../types';

export interface CacheHit {
  jobId: string;
  markdown: string;
}

export function useJob() {
  const [jobId, setJobIdRaw] = useSessionState<string | null>('job_id', null);
  const [url, setUrl] = useSessionState<string>('job_url', '');
  const [markdown, setMarkdown] = useSessionState<string>('job_markdown', '');
  const [savedStatus, setSavedStatus] = useSessionState<JobStatus | null>('job_status', null);
  const [isValidating, setIsValidating] = useState(false);
  const [isValid, setIsValid] = useState(true);
  const [validationIssues, setValidationIssues] = useState<ValidationIssue[]>([]);
  const appliedResultRef = useRef<string | null>(null);
  const validatedMarkdownRef = useRef<string | null>(null);

  // Cache hit pending user decision
  const [cacheHit, setCacheHit] = useState<CacheHit | null>(null);

  // Pending request params for "Generate new" after cache hit
  const pendingRequestRef = useRef<{ url: string; clientInfo?: string; promptsContext?: string[] } | null>(null);

  // Keep URL path in sync with jobId
  const setJobId = useCallback((id: string | null) => {
    setJobIdRaw(id);
    const targetPath = id ? `/${id}` : '/';
    if (window.location.pathname !== targetPath) {
      window.history.pushState(null, '', targetPath);
    }
  }, [setJobIdRaw]);

  // On mount, sync URL to match session state
  useEffect(() => {
    const targetPath = jobId ? `/${jobId}` : '/';
    if (window.location.pathname !== targetPath) {
      window.history.replaceState(null, '', targetPath);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Only connect SSE for jobs that need streaming (not already-completed loads)
  const sseJobId = savedStatus === 'completed' ? null : jobId;
  const { status: liveStatus, result, error, steps } = useSSE(sseJobId);

  // Use live status when a job is active, otherwise fall back to saved status
  const status = liveStatus ?? savedStatus;

  // When SSE completes, apply result markdown only once and persist status
  if (result && result.markdown && liveStatus === 'completed' && appliedResultRef.current !== result.markdown) {
    appliedResultRef.current = result.markdown;
    setMarkdown(result.markdown);
    setSavedStatus('completed');
  }

  // Handle browser back/forward
  useEffect(() => {
    const handlePopState = () => {
      const match = window.location.pathname.match(/^\/([0-9a-f-]{36})$/);
      if (match) {
        setJobIdRaw(match[1] ?? null);
      } else {
        // Back to home
        setJobIdRaw(null);
        setUrl('');
        setMarkdown('');
        setSavedStatus(null);
        setCacheHit(null);
        appliedResultRef.current = null;
        validatedMarkdownRef.current = null;
        setIsValid(true);
        setValidationIssues([]);
      }
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [setJobIdRaw, setUrl, setMarkdown, setSavedStatus]);

  // Debounced validation when markdown changes
  useEffect(() => {
    if (!markdown || status !== 'completed') return;
    if (validatedMarkdownRef.current === markdown) return;

    setIsValidating(true);
    setIsValid(false);

    const timer = setTimeout(async () => {
      if (validatedMarkdownRef.current === markdown) {
        setIsValidating(false);
        return;
      }
      try {
        const res = await validate({ markdown });
        validatedMarkdownRef.current = markdown;
        setIsValid(res.valid);
        setValidationIssues(res.issues);
      } catch {
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
    setCacheHit(null);
    appliedResultRef.current = null;
    setJobIdRaw(null);

    const response = await startGeneration({ url: inputUrl, client_info: inputClientInfo, prompts_context: inputPromptsContext });

    if (response.cached && response.markdown) {
      // Don't auto-apply — let the user choose
      pendingRequestRef.current = { url: inputUrl, clientInfo: inputClientInfo, promptsContext: inputPromptsContext };
      setCacheHit({ jobId: response.job_id, markdown: response.markdown });
      return;
    }

    setJobId(response.job_id);
  }, [setJobId, setJobIdRaw, setUrl, setClientInfo, setPromptsContext, setMarkdown, setSavedStatus]);

  // User chose to load the cached result
  const loadCached = useCallback(() => {
    if (!cacheHit) return;
    setMarkdown(cacheHit.markdown);
    setSavedStatus('completed');
    setJobId(cacheHit.jobId);
    setCacheHit(null);
    pendingRequestRef.current = null;
  }, [cacheHit, setMarkdown, setSavedStatus, setJobId]);

  // User chose to generate fresh instead of using cache
  const generateNew = useCallback(async () => {
    const pending = pendingRequestRef.current;
    if (!pending) return;
    setCacheHit(null);
    pendingRequestRef.current = null;

    const response = await startGeneration({
      url: pending.url,
      client_info: pending.clientInfo,
      prompts_context: pending.promptsContext,
      force: true,
    });
    setJobId(response.job_id);
  }, [setJobId]);

  const loadPrevious = useCallback((id: string, markdownContent: string) => {
    setMarkdown(markdownContent);
    setSavedStatus('completed');
    setJobId(id);
    setCacheHit(null);
    pendingRequestRef.current = null;
  }, [setMarkdown, setSavedStatus, setJobId]);

  const regenerate = useCallback(async () => {
    if (!url) return;
    setMarkdown('');
    setSavedStatus(null);
    setCacheHit(null);
    appliedResultRef.current = null;
    setJobIdRaw(null);

    const response = await startGeneration({ url, client_info: clientInfo, prompts_context: promptsContext, force: true });
    setJobId(response.job_id);
  }, [url, clientInfo, promptsContext, setJobId, setJobIdRaw, setMarkdown, setSavedStatus]);

  const reset = useCallback(() => {
    setJobIdRaw(null);
    setUrl('');
    setMarkdown('');
    setSavedStatus(null);
    setCacheHit(null);
    pendingRequestRef.current = null;
    appliedResultRef.current = null;
    validatedMarkdownRef.current = null;
    setIsValid(true);
    setValidationIssues([]);
    if (window.location.pathname !== '/') {
      window.history.pushState(null, '', '/');
    }
  }, [setJobIdRaw, setUrl, setMarkdown, setSavedStatus]);

  return {
    submitJob,
    regenerate,
    reset,
    loadCached,
    generateNew,
    loadPrevious,
    cacheHit,
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
