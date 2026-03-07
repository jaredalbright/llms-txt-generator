import type { ReactNode } from 'react';

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen bg-profound-surface">
      <header className="border-b border-profound-border bg-white">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center gap-3">
          <img src="/wordmark-dark.png" alt="Profound" className="h-9" />
          <span className="text-profound-border">|</span>
          <span className="text-sm font-medium text-profound-muted">llms.txt generator</span>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-6 py-8">
        {children}
      </main>
    </div>
  );
}
