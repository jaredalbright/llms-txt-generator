import { useState, type FormEvent } from 'react';

interface URLInputProps {
  onSubmit: (url: string, clientInfo?: string) => void;
  disabled?: boolean;
}

export default function URLInput({ onSubmit, disabled }: URLInputProps) {
  const [url, setUrl] = useState('');
  const [clientInfo, setClientInfo] = useState('');
  const [showClientInfo, setShowClientInfo] = useState(false);
  const [validationError, setValidationError] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();

    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      setValidationError('URL must start with http:// or https://');
      return;
    }

    setValidationError('');
    onSubmit(url, clientInfo.trim() || undefined);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="flex gap-3">
        <div className="flex-1">
          <input
            type="text"
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              setValidationError('');
            }}
            placeholder="https://example.com"
            disabled={disabled}
            className="w-full bg-profound-card border border-profound-border rounded-lg px-4 py-3 text-white placeholder:text-profound-muted focus:border-profound-yellow focus:ring-1 focus:ring-profound-yellow outline-none transition-colors disabled:opacity-50"
          />
          {validationError && (
            <p className="mt-1 text-sm text-red-500">{validationError}</p>
          )}
        </div>
        <button
          type="submit"
          disabled={disabled || !url}
          className="bg-profound-yellow text-black font-semibold rounded-lg px-6 py-2.5 hover:bg-yellow-300 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
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
            className="w-full bg-profound-card border border-profound-border rounded-lg px-4 py-3 text-white text-sm placeholder:text-profound-muted focus:border-profound-yellow focus:ring-1 focus:ring-profound-yellow outline-none transition-colors disabled:opacity-50 resize-none"
          />
        </div>
      )}
    </form>
  );
}
