import type { JobStatus } from '../types';

interface StatusBadgeProps {
  status: JobStatus;
}

const statusConfig: Record<JobStatus, { label: string; className: string }> = {
  pending: { label: 'Pending', className: 'bg-blue-50 text-blue-600' },
  crawling: { label: 'Crawling', className: 'bg-blue-50 text-blue-600' },
  processing: { label: 'Processing', className: 'bg-indigo-50 text-indigo-600' },
  extracting_content: { label: 'Extracting Content', className: 'bg-purple-50 text-purple-600' },
  summarizing: { label: 'Summarizing', className: 'bg-amber-50 text-amber-600' },
  completed: { label: 'Complete', className: 'bg-green-50 text-green-700' },
  error: { label: 'Error', className: 'bg-red-50 text-red-600' },
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const config = statusConfig[status];

  return (
    <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${config.className}`}>
      {config.label}
    </span>
  );
}
