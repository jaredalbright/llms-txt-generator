import type { ProfoundAsset, ProfoundPrompt } from '../types';

const BASE_URL = 'https://api.tryprofound.com';

async function profoundRequest<T>(path: string, apiKey: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'X-API-Key': apiKey },
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Profound API error: ${res.status}`);
  }

  return res.json();
}

export async function getAssets(apiKey: string): Promise<ProfoundAsset[]> {
  const res = await profoundRequest<{ data: ProfoundAsset[] }>('/v1/org/assets', apiKey);
  return res.data;
}

export async function getCategoryPrompts(apiKey: string, categoryId: string): Promise<ProfoundPrompt[]> {
  const res = await profoundRequest<{ data: ProfoundPrompt[] }>(
    `/v1/org/categories/${categoryId}/prompts`,
    apiKey,
  );
  return res.data;
}
