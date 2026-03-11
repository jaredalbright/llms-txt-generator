import type {
  GenerateRequest,
  GenerateResponse,
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

export function validate(data: ValidateRequest): Promise<ValidateResponse> {
  return request('/api/validate', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function faviconUrl(domain: string, size: number = 32): string {
  return `${API_URL}/api/favicon?domain=${encodeURIComponent(domain)}&sz=${size}`;
}

export async function downloadZip(jobId: string, markdown: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/generate/${jobId}/download.zip`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ markdown }),
  });

  if (!res.ok) {
    const error = await res.text();
    throw new Error(error || `Download failed: ${res.status}`);
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'llms-txt.zip';
  a.click();
  URL.revokeObjectURL(url);
}
