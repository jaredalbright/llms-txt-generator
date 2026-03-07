import type { ReactNode } from 'react';

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen bg-black">
      <header className="border-b border-profound-border">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center gap-3">
          <div className="w-8 h-8 bg-profound-yellow rounded-md flex items-center justify-center">
            <span className="text-black font-bold text-sm">T</span>
          </div>
          <h1 className="text-lg font-semibold text-white">llms.txt Generator</h1>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-6 py-8">
        {children}
      </main>
    </div>
  );
}
