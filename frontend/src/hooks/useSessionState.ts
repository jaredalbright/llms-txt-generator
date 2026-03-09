import { useState, useCallback } from 'react';

/**
 * useState that persists to sessionStorage.
 * Falls back to defaultValue if nothing stored or parse fails.
 */
export function useSessionState<T>(key: string, defaultValue: T): [T, (value: T | ((prev: T) => T)) => void] {
  const [state, setStateInner] = useState<T>(() => {
    try {
      const stored = sessionStorage.getItem(key);
      if (stored !== null) return JSON.parse(stored);
    } catch { /* ignore */ }
    return defaultValue;
  });

  const setState = useCallback((value: T | ((prev: T) => T)) => {
    setStateInner((prev) => {
      const next = typeof value === 'function' ? (value as (prev: T) => T)(prev) : value;
      try {
        sessionStorage.setItem(key, JSON.stringify(next));
      } catch { /* quota exceeded, ignore */ }
      return next;
    });
  }, [key]);

  return [state, setState];
}
