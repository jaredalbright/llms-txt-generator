import StatusBadge from './StatusBadge';
import type { JobStatus } from '../types';

interface ProgressViewProps {
  status: JobStatus;
  pagesFound?: number;
  message?: string;
}

export default function ProgressView({ status, pagesFound, message }: ProgressViewProps) {
  return (
    <div className="bg-profound-card border border-profound-border rounded-xl p-6">
      <div className="flex items-center gap-4">
        <div className="relative">
          <div className="w-4 h-4 bg-profound-yellow rounded-full animate-pulse" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-1">
            <StatusBadge status={status} />
            {pagesFound !== undefined && pagesFound > 0 && (
              <span className="text-sm text-profound-muted">
                {pagesFound} pages found
              </span>
            )}
          </div>
          {message && (
            <p className="text-sm text-profound-muted">{message}</p>
          )}
        </div>
      </div>
    </div>
  );
}
