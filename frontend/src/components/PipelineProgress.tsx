import { useState, useEffect, useRef } from 'react';
import type { StepInfo, PipelineStep } from '../types';

const STEP_LABELS: Record<PipelineStep, string> = {
  crawl: 'Discovering Pages',
  metadata: 'Extracting Metadata',
  fetch_homepage: 'Fetching Homepage',
  ai_categorize: 'AI Analysis',
  fetch_content: 'Fetching Content',
  summarize: 'Refining Descriptions',
  assemble: 'Building Output',
};

/**
 * Hook that "types" toward a target string. When targetText grows
 * (new content appended), animation continues from where it left off.
 * Speed is dynamic: each new batch of content aims to finish in
 * ~targetDurationMs, clamped so short texts aren't instant and
 * long texts don't lag behind the actual data arriving.
 */
function useTypewriter(targetText: string, targetDurationMs = 400) {
  const [displayLen, setDisplayLen] = useState(0);
  const displayLenRef = useRef(0);
  const rafRef = useRef<number>();

  useEffect(() => {
    if (displayLenRef.current >= targetText.length) return;

    const remaining = targetText.length - displayLenRef.current;
    // Dynamic ms-per-char: finish the new batch in targetDurationMs,
    // but never slower than 40ms/char or faster than 1ms/char
    const msPerChar = Math.max(1, Math.min(40, targetDurationMs / remaining));
    let lastTime = performance.now();

    const animate = (now: number) => {
      const elapsed = now - lastTime;
      if (elapsed >= msPerChar) {
        const charsToAdd = Math.max(1, Math.floor(elapsed / msPerChar));
        displayLenRef.current = Math.min(displayLenRef.current + charsToAdd, targetText.length);
        setDisplayLen(displayLenRef.current);
        lastTime = now;
      }
      if (displayLenRef.current < targetText.length) {
        rafRef.current = requestAnimationFrame(animate);
      }
    };

    rafRef.current = requestAnimationFrame(animate);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [targetText, targetDurationMs]);

  const isTyping = displayLen < targetText.length;
  return { displayed: targetText.slice(0, displayLen), isTyping };
}

/** Animates a single line of text on mount. */
function TypewriterLine({ text }: { text: string }) {
  const { displayed, isTyping } = useTypewriter(text, 350);
  return (
    <div>
      {displayed}
      {isTyping && <span className="text-profound-blue animate-pulse">▌</span>}
    </div>
  );
}

/** Animates a growing block of concatenated text (AI streaming). */
function TypewriterBlock({ text }: { text: string }) {
  const { displayed, isTyping } = useTypewriter(text, 300);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [displayed]);

  return (
    <div
      ref={logRef}
      className="mt-2 max-h-48 overflow-y-auto text-xs text-profound-muted font-mono bg-gray-50 rounded-lg p-2 whitespace-pre-wrap break-words"
    >
      {displayed}
      {isTyping && <span className="text-profound-blue animate-pulse">▌</span>}
    </div>
  );
}

function DetailLog({ details, isAI, isActive }: { details: string[]; isAI: boolean; isActive: boolean }) {
  const logRef = useRef<HTMLDivElement>(null);
  // Track how many lines have been "seen" so only new lines get the typewriter
  const seenCountRef = useRef(0);

  // Auto-scroll for the list container (non-AI)
  useEffect(() => {
    if (!isAI && isActive && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [details.length, isActive, isAI]);

  if (details.length === 0) return null;

  if (isAI) {
    const fullText = details.join('');
    return <TypewriterBlock text={fullText} />;
  }

  // Split into already-seen (render instantly) and new (typewriter)
  const seenBefore = seenCountRef.current;
  // Update ref for next render
  seenCountRef.current = details.length;

  return (
    <div
      ref={logRef}
      className="mt-2 max-h-48 overflow-y-auto space-y-0.5 text-xs text-profound-muted font-mono bg-gray-50 rounded-lg p-2"
    >
      {details.map((line, i) =>
        i < seenBefore ? (
          <div key={i}>{line}</div>
        ) : (
          <TypewriterLine key={i} text={line} />
        )
      )}
    </div>
  );
}

function ThinkingDots() {
  return (
    <span className="inline-flex gap-1 ml-2">
      <span className="w-1.5 h-1.5 bg-profound-blue rounded-full animate-bounce [animation-delay:0ms]" />
      <span className="w-1.5 h-1.5 bg-profound-blue rounded-full animate-bounce [animation-delay:150ms]" />
      <span className="w-1.5 h-1.5 bg-profound-blue rounded-full animate-bounce [animation-delay:300ms]" />
    </span>
  );
}

function StepRow({ step }: { step: StepInfo }) {
  const [expanded, setExpanded] = useState(false);
  const [showBody, setShowBody] = useState(step.state === 'active');
  const prevStateRef = useRef(step.state);

  useEffect(() => {
    if (prevStateRef.current === 'active' && step.state === 'completed') {
      const timer = setTimeout(() => setShowBody(false), 400);
      return () => clearTimeout(timer);
    }
    if (step.state === 'active') {
      setShowBody(true);
    }
    prevStateRef.current = step.state;
  }, [step.state]);

  const isExpanded = step.state === 'active' || showBody || expanded;
  const hasDetails = step.details.length > 0;

  return (
    <div className="flex gap-3 items-start">
      {/* Icon */}
      <div className="mt-0.5 flex-shrink-0">
        {step.state === 'pending' && (
          <div className="w-5 h-5 rounded-full border-2 border-gray-300" />
        )}
        {step.state === 'active' && (
          <div className="w-5 h-5 rounded-full bg-profound-blue animate-pulse" />
        )}
        {step.state === 'completed' && (
          <div className="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center">
            <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <button
          type="button"
          className={`flex items-center gap-2 w-full text-left ${step.state === 'completed' && hasDetails ? 'cursor-pointer' : 'cursor-default'}`}
          onClick={() => step.state === 'completed' && hasDetails && setExpanded(e => !e)}
          disabled={step.state !== 'completed' || !hasDetails}
        >
          <span className={`text-sm font-medium ${
            step.state === 'active' ? 'text-profound-dark' :
            step.state === 'completed' ? 'text-profound-dark' :
            'text-gray-400'
          }`}>
            {STEP_LABELS[step.step]}
          </span>

          {step.state === 'active' && <ThinkingDots />}

          {step.state === 'completed' && step.summary && (
            <span className="text-xs text-profound-muted">&mdash; {step.summary}</span>
          )}

          {step.state === 'completed' && hasDetails && (
            <svg
              className={`w-3.5 h-3.5 text-gray-400 transition-transform duration-200 ml-auto flex-shrink-0 ${expanded ? 'rotate-180' : ''}`}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          )}
        </button>

        {/* Expandable body */}
        <div
          className="grid transition-[grid-template-rows] duration-300 ease-in-out"
          style={{ gridTemplateRows: isExpanded ? '1fr' : '0fr' }}
        >
          <div className="overflow-hidden">
            {step.state === 'active' && step.message && (
              <p className="text-xs text-profound-muted mt-1">{step.message}</p>
            )}
            <DetailLog
              details={step.details}
              isAI={step.step === 'ai_categorize' || step.step === 'summarize'}
              isActive={step.state === 'active'}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

interface PipelineProgressProps {
  steps: StepInfo[];
}

export default function PipelineProgress({ steps }: PipelineProgressProps) {
  return (
    <div className="bg-white border border-profound-border rounded-xl p-5 space-y-3">
      {steps.map(step => (
        <StepRow key={step.step} step={step} />
      ))}
    </div>
  );
}
