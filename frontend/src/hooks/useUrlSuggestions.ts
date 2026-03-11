import { useState, useEffect } from 'react';
import { searchGenerationsByUrl } from '../lib/generations';
import type { GenerationSummary } from '../types';

const DOMAIN_RE = /^[^/]+\.[^/]+/;

function normalizeForSearch(input: string): string | null {
  const trimmed = input.trim();
  if (!trimmed) return null;
  const url = trimmed.startsWith('http://') || trimmed.startsWith('https://')
    ? trimmed
    : `https://${trimmed}`;
  // Only search once we have a real domain (something.something)
  const domainPart = url.replace(/^https?:\/\//, '');
  if (!DOMAIN_RE.test(domainPart)) return null;
  return url;
}

export function useUrlSuggestions(url: string) {
  const [suggestions, setSuggestions] = useState<GenerationSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const searchUrl = normalizeForSearch(url);
    if (!searchUrl) {
      setSuggestions([]);
      return;
    }

    setIsLoading(true);
    const timer = setTimeout(async () => {
      try {
        const results = await searchGenerationsByUrl(searchUrl, 3);
        setSuggestions(results);
      } catch {
        setSuggestions([]);
      } finally {
        setIsLoading(false);
      }
    }, 250);

    return () => {
      clearTimeout(timer);
      setIsLoading(false);
    };
  }, [url]);

  const clearSuggestions = () => setSuggestions([]);

  return { suggestions, isLoading, clearSuggestions };
}
