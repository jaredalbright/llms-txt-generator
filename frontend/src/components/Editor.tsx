interface EditorProps {
  value: string;
  onChange: (value: string) => void;
}

export default function Editor({ value, onChange }: EditorProps) {
  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-2 border-b border-profound-border">
        <span className="text-sm font-medium text-profound-muted">Markdown</span>
      </div>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="flex-1 w-full bg-profound-card p-4 font-mono text-sm text-white resize-none outline-none"
        spellCheck={false}
      />
    </div>
  );
}
