import { useState, useEffect } from 'react';
import { fetchRecentGenerations, fetchGeneration } from '../lib/generations';
import { extractDomain, timeAgo } from '../lib/timeago';
import type { GenerationSummary } from '../types';

interface RecentCarouselProps {
  onSelect: (id: string, markdown: string) => void;
}

export default function RecentCarousel({ onSelect }: RecentCarouselProps) {
  const [items, setItems] = useState<GenerationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingId, setLoadingId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const data = await fetchRecentGenerations(10);
        if (!cancelled) setItems(data);
      } catch {
        // Silently ignore — carousel is non-critical
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    const interval = setInterval(load, 60_000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const handleClick = async (id: string) => {
    setLoadingId(id);
    try {
      const gen = await fetchGeneration(id);
      if (gen?.markdown) {
        onSelect(gen.id, gen.markdown);
      }
    } finally {
      setLoadingId(null);
    }
  };

  if (!loading && items.length === 0) return null;

  // Duplicate items for seamless loop
  const track = [...items, ...items];

  return (
    <div>
      <h3 className="text-sm font-medium text-gray-900 mb-2">Recent generations</h3>
      <div className="overflow-hidden">
        {loading ? (
          <div className="flex gap-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="flex items-center gap-2.5 px-3 py-2 border border-profound-border rounded-lg bg-white shrink-0"
              >
                <div className="w-4 h-4 rounded bg-gray-200 animate-pulse shrink-0" />
                <div className="h-3.5 rounded bg-gray-200 animate-pulse" style={{ width: `${60 + (i % 3) * 20}px` }} />
                <div className="h-3 rounded bg-gray-100 animate-pulse" style={{ width: '32px' }} />
              </div>
            ))}
          </div>
        ) : (
          <div className="carousel-track flex gap-3 w-max">
            {track.map((item, i) => {
              const domain = extractDomain(item.url);
              const isLoading = loadingId === item.id;
              return (
                <button
                  key={`${item.id}-${i}`}
                  type="button"
                  disabled={isLoading}
                  onClick={() => handleClick(item.id)}
                  className="flex items-center gap-2.5 px-3 py-2 border border-profound-border rounded-lg bg-white hover:bg-gray-50 transition-colors cursor-pointer shrink-0 disabled:opacity-50"
                >
                  <span className="text-sm text-gray-900 whitespace-nowrap">{domain}</span>
                  <span className="text-xs text-profound-muted whitespace-nowrap">{timeAgo(item.created_at)}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
      <style>{`
        .carousel-track {
          animation: carousel-scroll 30s linear infinite;
        }
        .carousel-track:hover {
          animation-play-state: paused;
        }
        @keyframes carousel-scroll {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
      `}</style>
    </div>
  );
}
