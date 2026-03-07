import { useMemo } from 'react';
import { renderMarkdown } from '../lib/markdown';

interface PreviewProps {
  markdown: string;
}

export default function Preview({ markdown }: PreviewProps) {
  const html = useMemo(() => renderMarkdown(markdown), [markdown]);

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-2 border-b border-profound-border">
        <span className="text-sm font-medium text-profound-muted">Preview</span>
      </div>
      <div
        className="flex-1 p-4 prose prose-sm max-w-none overflow-auto
          prose-headings:text-gray-900 prose-a:text-profound-blue prose-blockquote:border-profound-blue"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}
