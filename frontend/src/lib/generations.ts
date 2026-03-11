import type { GenerationSummary } from '../types';

const API_URL = import.meta.env.VITE_API_URL || '';

export async function fetchRecentGenerations(limit = 10): Promise<GenerationSummary[]> {
  const res = await fetch(`${API_URL}/api/generations/recent?limit=${limit}`);
  if (!res.ok) return [];
  return res.json();
}

export async function searchGenerationsByUrl(url: string, limit = 3): Promise<GenerationSummary[]> {
  const res = await fetch(`${API_URL}/api/generations/search?url=${encodeURIComponent(url)}&limit=${limit}`);
  if (!res.ok) return [];
  return res.json();
}

export async function fetchGeneration(id: string): Promise<{ id: string; url: string; markdown: string | null } | null> {
  const res = await fetch(`${API_URL}/api/generations/${id}`);
  if (!res.ok) return null;
  return res.json();
}
