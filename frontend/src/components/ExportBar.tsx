import { useState, useEffect } from 'react';
import { downloadZip as downloadZipApi } from '../lib/api';

function PostDownloadModal({ onClose }: { onClose: () => void }) {
  // Close on Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40" />

      {/* Modal */}
      <div
        className="relative bg-white rounded-2xl shadow-xl max-w-lg w-full p-8 animate-in fade-in zoom-in duration-200"
        onClick={e => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* Content */}
        <div className="space-y-5">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Your llms.txt files are downloading</h2>
            <p className="text-sm text-profound-muted mt-1">Here's how to use them on your site.</p>
          </div>

          <ol className="space-y-3 text-sm text-gray-700">
            <li className="flex gap-3">
              <span>Upload <code className="text-xs bg-gray-100 rounded px-1.5 py-0.5 font-mono">base/llms.txt</code> to your site root so it's accessible at <code className="text-xs bg-gray-100 rounded px-1.5 py-0.5 font-mono">yoursite.com/llms.txt</code></span>
            </li>
            {/* OR divider */}
          <div className="flex items-center gap-3">
            <div className="flex-1 h-px bg-profound-border" />
            <span className="text-xs font-medium text-profound-muted uppercase tracking-wider">or to maximize results</span>
            <div className="flex-1 h-px bg-profound-border" />
          </div>
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-profound-blue/10 text-profound-blue text-xs font-semibold flex items-center justify-center">1</span>
              <span>Upload each of the files in the <code className="text-xs bg-gray-100 rounded px-1.5 py-0.5 font-mono">md/</code> folder to their corresponding paths to serve individual <code className="text-xs bg-gray-100 rounded px-1.5 py-0.5 font-mono">.md</code> files for each page</span>
            </li>
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-profound-blue/10 text-profound-blue text-xs font-semibold flex items-center justify-center">2</span>
              <span>Use the <code className="text-xs bg-gray-100 rounded px-1.5 py-0.5 font-mono">llms.txt</code> file found under <code className="text-xs bg-gray-100 rounded px-1.5 py-0.5 font-mono">md/</code> to serve your site's llms.txt file</span>
            </li>
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-profound-blue/10 text-profound-blue text-xs font-semibold flex items-center justify-center">2</span>
              <span>Optionally upload <code className="text-xs bg-gray-100 rounded px-1.5 py-0.5 font-mono">llms-ctx.txt</code> for expanded context that AI models can use to deeply understand your site</span>
            </li>
          </ol>

          <div>
            <p className="text-sm text-profound-muted mb-4">
              Ready to step up your AEO game?
            </p>
            <a
              href="https://platform.tryprofound.com/welcome"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center w-full bg-profound-blue text-white font-medium text-sm rounded-lg px-6 py-2.5 hover:bg-profound-blue/90 transition-colors"
            >
              Sign up for Profound
              <svg className="w-4 h-4 ml-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

interface ExportBarProps {
  markdown: string;
  jobId?: string;
  exportDisabled?: boolean;
}

export default function ExportBar({ markdown, jobId, exportDisabled }: ExportBarProps) {
  const [copied, setCopied] = useState(false);
  const [showModal, setShowModal] = useState(false);

  const downloadFile = (filename: string) => {
    const blob = new Blob([markdown], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadZip = async () => {
    if (!jobId) return;
    await downloadZipApi(jobId, markdown);
    setShowModal(true);
  };

  const copyToClipboard = async () => {
    await navigator.clipboard.writeText(markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const buttonClassName = "border border-profound-border text-gray-700 rounded-lg px-6 py-2.5 hover:bg-gray-50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent";

  return (
    <>
      <div className="flex flex-wrap gap-3">
        <button
          onClick={() => downloadFile('llms.txt')}
          disabled={exportDisabled}
          className={buttonClassName}
        >
          Download llms.txt
        </button>
        {jobId && (
          <button
            onClick={downloadZip}
            disabled={exportDisabled}
            className={buttonClassName}
          >
            Download .zip
          </button>
        )}
        <button
          onClick={copyToClipboard}
          disabled={exportDisabled}
          className={buttonClassName}
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>

      {showModal && <PostDownloadModal onClose={() => setShowModal(false)} />}
    </>
  );
}
