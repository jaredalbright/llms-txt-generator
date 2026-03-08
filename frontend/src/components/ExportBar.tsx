import { useState } from 'react';

interface ExportBarProps {
  markdown: string;
  jobId?: string;
  onRegenerate: () => void;
  exportDisabled?: boolean;
}

export default function ExportBar({ markdown, jobId, onRegenerate, exportDisabled }: ExportBarProps) {
  const [copied, setCopied] = useState(false);

  const downloadFile = (filename: string) => {
    const blob = new Blob([markdown], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadZip = () => {
    if (!jobId) return;
    const apiUrl = import.meta.env.VITE_API_URL || '';
    window.open(`${apiUrl}/api/generate/${jobId}/download.zip`, '_blank');
  };

  const copyToClipboard = async () => {
    await navigator.clipboard.writeText(markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const buttonClassName = "border border-profound-border text-gray-700 rounded-lg px-6 py-2.5 hover:bg-gray-50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent";

  return (
    <div className="flex flex-wrap gap-3">
      <button
        onClick={() => downloadFile('llms.txt')}
        disabled={exportDisabled}
        className={buttonClassName}
      >
        Download .txt
      </button>
      <button
        onClick={() => downloadFile('llms.md')}
        disabled={exportDisabled}
        className={buttonClassName}
      >
        Download .md
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
      <button
        onClick={onRegenerate}
        className="border border-profound-border text-gray-700 rounded-lg px-6 py-2.5 hover:bg-gray-50 transition-colors"
      >
        Regenerate
      </button>
    </div>
  );
}
