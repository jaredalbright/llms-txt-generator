import { useState, useRef, type FormEvent } from 'react';
import { useUrlSuggestions } from '../hooks/useUrlSuggestions';
import { extractDomain, timeAgo } from '../lib/timeago';

interface URLInputProps {
  onSubmit: (url: string, clientInfo?: string) => void;
  disabled?: boolean;
}

export default function URLInput({ onSubmit, disabled }: URLInputProps) {
  const [url, setUrl] = useState('');
  const [clientInfo, setClientInfo] = useState('');
  const [showClientInfo, setShowClientInfo] = useState(false);
  const [validationError, setValidationError] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(true);

  const { suggestions, clearSuggestions } = useUrlSuggestions(url);
  const blurTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const normalizeUrl = (input: string): string => {
    const trimmed = input.trim();
    if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) return trimmed;
    return `https://${trimmed}`;
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();

    const normalized = normalizeUrl(url);
    setUrl(normalized);
    setValidationError('');
    clearSuggestions();
    setShowSuggestions(false);
    onSubmit(normalized, clientInfo.trim() || undefined);
  };

  const handleLoadSuggestion = (suggestionUrl: string) => {
    setUrl(suggestionUrl);
    clearSuggestions();
    setShowSuggestions(false);
    onSubmit(suggestionUrl, clientInfo.trim() || undefined);
  };

  const handleInputBlur = () => {
    // Delay so click on suggestion registers before dropdown hides
    blurTimeoutRef.current = setTimeout(() => {
      setShowSuggestions(false);
    }, 200);
  };

  const handleInputFocus = () => {
    if (blurTimeoutRef.current) {
      clearTimeout(blurTimeoutRef.current);
      blurTimeoutRef.current = null;
    }
    setShowSuggestions(true);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  };

  const visibleSuggestions = showSuggestions ? suggestions : [];

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
       <h3 className="text-sm font-medium text-gray-900">Enter a URL</h3>
      <div className="flex gap-3">
        <div className="relative flex-1">
          <input
            type="text"
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              setValidationError('');
              setShowSuggestions(true);
            }}
            onBlur={handleInputBlur}
            onFocus={handleInputFocus}
            onKeyDown={handleKeyDown}
            placeholder="example.com"
            aria-label="Website URL"
            disabled={disabled}
            className="w-full bg-white border border-profound-border rounded-lg px-4 py-3 text-gray-900 placeholder:text-profound-muted focus:border-profound-blue focus:ring-1 focus:ring-profound-blue outline-none transition-colors disabled:opacity-50"
          />
          {validationError && (
            <p className="mt-1 text-sm text-red-500">{validationError}</p>
          )}

          {/* Suggestions dropdown */}
          {visibleSuggestions.length > 0 && !disabled && (
            <ul className="absolute left-0 right-0 top-full mt-1 bg-white border border-profound-border rounded-lg shadow-lg z-10 overflow-hidden">
              {visibleSuggestions.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => handleLoadSuggestion(s.url)}
                    className="w-full flex items-center justify-between gap-3 px-4 py-2.5 text-left hover:bg-gray-50 transition-colors cursor-pointer"
                  >
                    <span className="flex items-center gap-2 min-w-0">
                      <img
                        src={`https://www.google.com/s2/favicons?domain=${extractDomain(s.url)}&sz=16`}
                        alt=""
                        width={16}
                        height={16}
                        referrerPolicy="no-referrer"
                        className="shrink-0"
                      />
                      <span className="text-sm text-gray-900 truncate">{extractDomain(s.url)}</span>
                    </span>
                    <span className="text-xs text-profound-muted whitespace-nowrap">{timeAgo(s.created_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <button
          type="submit"
          disabled={disabled || !url}
          className="bg-white text-black font-semibold rounded-lg px-6 py-2.5 border border-profound-border hover:bg-gray-50 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Generate
        </button>
      </div>

      {!showClientInfo ? (
        <button
          type="button"
          onClick={() => setShowClientInfo(true)}
          disabled={disabled}
          className="text-sm text-profound-muted hover:text-profound-light transition-colors cursor-pointer disabled:opacity-50"
        >
          + Add client context
        </button>
      ) : (
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-sm text-profound-muted">Client context (optional)</label>
            <button
              type="button"
              onClick={() => {
                setShowClientInfo(false);
                setClientInfo('');
              }}
              className="text-xs text-profound-muted hover:text-profound-light transition-colors cursor-pointer"
            >
              Remove
            </button>
          </div>
          <textarea
            value={clientInfo}
            onChange={(e) => setClientInfo(e.target.value)}
            placeholder="e.g., This is a B2B SaaS company focused on developer tools. Prioritize API docs and integration guides."
            disabled={disabled}
            rows={3}
            className="w-full bg-white border border-profound-border rounded-lg px-4 py-3 text-gray-900 text-sm placeholder:text-profound-muted focus:border-profound-blue focus:ring-1 focus:ring-profound-blue outline-none transition-colors disabled:opacity-50 resize-none"
          />
        </div>
      )}
    </form>
  );
}
