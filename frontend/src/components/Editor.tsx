interface EditorProps {
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
}

export default function Editor({ value, onChange, readOnly }: EditorProps) {
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center px-4 h-10 border-b border-profound-border">
        <span className="text-sm font-medium text-profound-muted">Markdown</span>
      </div>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        readOnly={readOnly}
        className={`flex-1 w-full bg-white p-4 font-mono text-sm text-gray-900 resize-none outline-none ${readOnly ? 'cursor-default' : ''}`}
        spellCheck={false}
      />
    </div>
  );
}
