import type { JobStatus } from '../types';

interface StatusBadgeProps {
  status: JobStatus;
}

const statusConfig: Record<JobStatus, { label: string; className: string }> = {
  pending: { label: 'Pending', className: 'bg-yellow-500/10 text-yellow-400' },
  crawling: { label: 'Crawling', className: 'bg-yellow-500/10 text-yellow-400' },
  processing: { label: 'Processing', className: 'bg-blue-500/10 text-blue-400' },
  completed: { label: 'Complete', className: 'bg-green-500/10 text-green-400' },
  error: { label: 'Error', className: 'bg-red-500/10 text-red-400' },
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const config = statusConfig[status];

  return (
    <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${config.className}`}>
      {config.label}
    </span>
  );
}
