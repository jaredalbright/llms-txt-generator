import { useState } from 'react';

interface ExportBarProps {
  markdown: string;
  onRegenerate: () => void;
}

export default function ExportBar({ markdown, onRegenerate }: ExportBarProps) {
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

  const copyToClipboard = async () => {
    await navigator.clipboard.writeText(markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex flex-wrap gap-3">
      <button
        onClick={() => downloadFile('llms.txt')}
        className="border border-profound-border text-white rounded-lg px-6 py-2.5 hover:bg-profound-card transition-colors"
      >
        Download .txt
      </button>
      <button
        onClick={() => downloadFile('llms.md')}
        className="border border-profound-border text-white rounded-lg px-6 py-2.5 hover:bg-profound-card transition-colors"
      >
        Download .md
      </button>
      <button
        onClick={copyToClipboard}
        className="border border-profound-border text-white rounded-lg px-6 py-2.5 hover:bg-profound-card transition-colors"
      >
        {copied ? 'Copied!' : 'Copy'}
      </button>
      <button
        onClick={onRegenerate}
        className="border border-profound-border text-white rounded-lg px-6 py-2.5 hover:bg-profound-card transition-colors"
      >
        Regenerate
      </button>
    </div>
  );
}
