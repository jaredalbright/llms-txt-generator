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
        className="flex-1 bg-profound-card border border-profound-border rounded-lg px-4 py-3 text-white placeholder:text-profound-muted focus:border-profound-yellow focus:ring-1 focus:ring-profound-yellow outline-none transition-colors disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={disabled || !instruction.trim()}
        className="bg-profound-yellow text-black font-semibold rounded-lg px-6 py-2.5 hover:bg-yellow-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Reprompt
      </button>
    </form>
  );
}
