export type JobStatus = 'pending' | 'crawling' | 'processing' | 'extracting_content' | 'summarizing' | 'completed' | 'error';

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
  prompts_context?: string[];
  force?: boolean;
}

// Profound API types
export interface ProfoundAsset {
  id: string;
  name: string;
  website: string;
  logo_url: string;
  category: {
    id: string;
    name: string;
  };
}

export interface ProfoundPrompt {
  id: string;
  prompt_type: string;
  prompt: string;
  topic: {
    id: string;
    name: string;
  };
  tags: { id: string; name: string }[];
  platforms: { id: string; name: string }[];
}

export interface GenerateResponse {
  job_id: string;
  cached?: boolean;
  markdown?: string;
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

export type PipelineStep = 'crawl' | 'metadata' | 'fetch_homepage' | 'ai_categorize' | 'fetch_content' | 'summarize' | 'assemble';
export type StepState = 'pending' | 'active' | 'completed';

export interface StepInfo {
  step: PipelineStep;
  state: StepState;
  message: string;
  summary?: string;
  details: string[];
}
