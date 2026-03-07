export type JobStatus = 'pending' | 'crawling' | 'processing' | 'completed' | 'error';

export interface Job {
  id: string;
  url: string;
  status: JobStatus;
  created_at: string;
  markdown?: string;
  pages_found?: number;
  error_message?: string;
}

export interface GenerateRequest {
  url: string;
  client_info?: string;
}

export interface GenerateResponse {
  job_id: string;
}

export interface RepromptRequest {
  job_id: string;
  instruction: string;
  current_markdown: string;
}

export interface RepromptResponse {
  markdown: string;
}

export interface ValidateRequest {
  markdown: string;
}

export interface ValidationIssue {
  line: number;
  severity: 'error' | 'warning';
  message: string;
}

export interface ValidateResponse {
  valid: boolean;
  issues: ValidationIssue[];
}

export interface PageMeta {
  url: string;
  title: string;
  description: string;
  h1: string;
}
