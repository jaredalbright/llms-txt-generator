import { useState } from 'react';
import Editor from './Editor';
import Preview from './Preview';

interface EditorPreviewProps {
  markdown: string;
  onChange: (value: string) => void;
}

export default function EditorPreview({ markdown, onChange }: EditorPreviewProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="relative bg-white border border-profound-border rounded-xl overflow-hidden">
      <div
        className={`grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-profound-border transition-[max-height] duration-300 ${
          expanded ? 'max-h-none' : 'max-h-[300px] overflow-hidden'
        }`}
      >
        <Editor value={markdown} onChange={onChange} readOnly={!expanded} />
        <Preview markdown={markdown} />
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
