import { useMemo, type ReactNode } from 'react';
import { renderMarkdown } from '../lib/markdown';

interface PreviewProps {
  markdown: string;
  headerRight?: ReactNode;
}

export default function Preview({ markdown, headerRight }: PreviewProps) {
  const html = useMemo(() => renderMarkdown(markdown), [markdown]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 h-10 border-b border-profound-border">
        <span className="text-sm font-medium text-profound-muted">Preview</span>
        {headerRight}
      </div>
      <div
        className="flex-1 p-4 prose prose-sm max-w-none overflow-auto
          prose-headings:text-gray-900 prose-a:text-profound-blue prose-blockquote:border-profound-blue"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}
