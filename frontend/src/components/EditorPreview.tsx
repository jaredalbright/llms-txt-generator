import { useState, useRef, useEffect } from 'react';
import Editor from './Editor';
import Preview from './Preview';

interface EditorPreviewProps {
  markdown: string;
  onChange: (value: string) => void;
  onCopy?: () => Promise<void>;
  onDownloadTxt?: () => void;
  onDownloadZip?: () => Promise<void>;
  exportDisabled?: boolean;
}

function ExportDropdown({
  onCopy,
  onDownloadTxt,
  onDownloadZip,
  disabled,
}: {
  onCopy?: () => Promise<void>;
  onDownloadTxt?: () => void;
  onDownloadZip?: () => Promise<void>;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleCopy = async () => {
    if (onCopy) {
      await onCopy();
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
    setOpen(false);
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        disabled={disabled}
        className="inline-flex items-center gap-1.5 border border-gray-200 rounded-md px-2.5 py-1 text-xs font-medium text-gray-700 bg-white hover:bg-gray-50 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {/* Download icon */}
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
        </svg>
        Export
        {/* Chevron */}
        <svg className={`w-3 h-3 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-20 py-1">
          {onDownloadTxt && (
            <button
              type="button"
              onClick={() => { onDownloadTxt(); setOpen(false); }}
              className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors cursor-pointer"
            >
              {/* File icon */}
              <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
              Download llms.txt
            </button>
          )}
          {onDownloadZip && (
            <button
              type="button"
              onClick={() => { onDownloadZip(); setOpen(false); }}
              className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors cursor-pointer"
            >
              {/* Archive icon */}
              <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
              </svg>
              Download .zip
            </button>
          )}
          {onCopy && (
            <button
              type="button"
              onClick={handleCopy}
              className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors cursor-pointer"
            >
              {/* Clipboard icon */}
              <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
              </svg>
              {copied ? 'Copied!' : 'Copy to clipboard'}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function EditorPreview({
  markdown,
  onChange,
  onCopy,
  onDownloadTxt,
  onDownloadZip,
  exportDisabled,
}: EditorPreviewProps) {
  const [expanded, setExpanded] = useState(false);
  const hasExport = onCopy || onDownloadTxt || onDownloadZip;

  const exportDropdown = hasExport ? (
    <ExportDropdown
      onCopy={onCopy}
      onDownloadTxt={onDownloadTxt}
      onDownloadZip={onDownloadZip}
      disabled={exportDisabled}
    />
  ) : undefined;

  return (
    <div className="relative bg-white border border-profound-border rounded-xl overflow-hidden">
      <div
        className={`grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-profound-border transition-[max-height] duration-300 ${
          expanded ? 'max-h-none' : 'max-h-[300px] overflow-hidden'
        }`}
      >
        <Editor value={markdown} onChange={onChange} readOnly={!expanded} />
        <Preview markdown={markdown} headerRight={exportDropdown} />
      </div>

      {!expanded && (
        <div
          className="absolute bottom-0 left-0 right-0 group cursor-pointer"
          onClick={() => setExpanded(true)}
        >
          {/* Gradient fade */}
          <div className="h-20 bg-gradient-to-t from-white to-transparent pointer-events-none" />
          {/* Expand button */}
          <div className="absolute bottom-0 left-0 right-0 flex justify-center pb-3 opacity-0 group-hover:opacity-100 transition-opacity">
            <span className="bg-gray-100 text-gray-700 text-xs font-medium px-4 py-1.5 rounded-full">
              Click to expand
            </span>
          </div>
        </div>
      )}

      {expanded && (
        <div
          className="flex justify-center py-2 border-t border-profound-border cursor-pointer hover:bg-gray-50 transition-colors"
          onClick={() => setExpanded(false)}
        >
          <span className="text-profound-muted text-xs font-medium">Collapse</span>
        </div>
      )}
    </div>
  );
}
