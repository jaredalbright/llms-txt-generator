import type {
  GenerateRequest,
  GenerateResponse,
  RepromptRequest,
  RepromptResponse,
  ValidateRequest,
  ValidateResponse,
} from '../types';

const API_URL = import.meta.env.VITE_API_URL || '';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  if (!res.ok) {
    const error = await res.text();
    throw new Error(error || `Request failed: ${res.status}`);
  }

  return res.json();
}

export function startGeneration(data: GenerateRequest): Promise<GenerateResponse> {
  return request('/api/generate', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function reprompt(data: RepromptRequest): Promise<RepromptResponse> {
  return request('/api/reprompt', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function validate(data: ValidateRequest): Promise<ValidateResponse> {
  return request('/api/validate', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}
