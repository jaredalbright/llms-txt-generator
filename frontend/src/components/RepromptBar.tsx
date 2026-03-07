import { useState, type FormEvent } from 'react';

interface RepromptBarProps {
  onSubmit: (instruction: string) => void;
  disabled?: boolean;
}

export default function RepromptBar({ onSubmit, disabled }: RepromptBarProps) {
  const [instruction, setInstruction] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!instruction.trim()) return;
    onSubmit(instruction);
    setInstruction('');
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-3">
      <input
        type="text"
        value={instruction}
        onChange={(e) => setInstruction(e.target.value)}
        placeholder="e.g., Move blog posts to Optional section"
        disabled={disabled}
        className="flex-1 bg-white border border-profound-border rounded-lg px-4 py-3 text-gray-900 placeholder:text-profound-muted focus:border-profound-blue focus:ring-1 focus:ring-profound-blue outline-none transition-colors disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={disabled || !instruction.trim()}
        className="bg-white text-black font-semibold rounded-lg px-6 py-2.5 border border-profound-border hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Reprompt
      </button>
    </form>
  );
}
