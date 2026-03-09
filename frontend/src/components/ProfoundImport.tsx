import { useState, type FormEvent } from 'react';
import { getAssets, getCategoryPrompts } from '../lib/profound';
import { useSessionState } from '../hooks/useSessionState';
import type { ProfoundAsset, ProfoundPrompt } from '../types';

const MAX_PROMPTS = 10;
type Step = 'token' | 'assets' | 'prompts';

interface ProfoundImportProps {
  onGenerate: (url: string, promptsContext: string[]) => void;
  disabled?: boolean;
}

export default function ProfoundImport({ onGenerate, disabled }: ProfoundImportProps) {
  const [step, setStep] = useSessionState<Step>('profound_step', 'token');
  const [apiKey, setApiKey] = useSessionState('profound_api_key', '');
  const [assets, setAssets] = useSessionState<ProfoundAsset[]>('profound_assets', []);
  const [selectedAsset, setSelectedAsset] = useSessionState<ProfoundAsset | null>('profound_selected_asset', null);
  const [prompts, setPrompts] = useSessionState<ProfoundPrompt[]>('profound_prompts', []);
  const [selectedPromptIdsArr, setSelectedPromptIdsArr] = useSessionState<string[]>('profound_selected_prompt_ids', []);
  const [collapsed, setCollapsed] = useSessionState('profound_collapsed', false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Derive Set from persisted array for easy lookups
  const selectedPromptIds = new Set(selectedPromptIdsArr);
  const setSelectedPromptIds = (value: Set<string> | ((prev: Set<string>) => Set<string>)) => {
    if (typeof value === 'function') {
      setSelectedPromptIdsArr((prev) => [...value(new Set(prev))]);
    } else {
      setSelectedPromptIdsArr([...value]);
    }
  };

  const handleFetchAssets = async (e: FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim()) return;
    setLoading(true);
    setError('');
    try {
      const data = await getAssets(apiKey.trim());
      setAssets(data);
      setStep('assets');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch assets');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectAsset = async (asset: ProfoundAsset) => {
    setSelectedAsset(asset);
    setLoading(true);
    setError('');
    try {
      const data = await getCategoryPrompts(apiKey, asset.category.id);
      setPrompts(data);
      setSelectedPromptIds(new Set(data.slice(0, MAX_PROMPTS).map((p) => p.id)));
      setStep('prompts');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch prompts');
    } finally {
      setLoading(false);
    }
  };

  const togglePrompt = (id: string) => {
    setSelectedPromptIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else if (next.size < MAX_PROMPTS) {
        next.add(id);
      }
      return next;
    });
  };

  const atLimit = selectedPromptIds.size >= MAX_PROMPTS;

  const handleGenerate = () => {
    if (!selectedAsset) return;
    const selected = prompts
      .filter((p) => selectedPromptIds.has(p.id))
      .map((p) => p.prompt);
    let url = selectedAsset.website;
    if (url && !url.startsWith('http://') && !url.startsWith('https://')) {
      url = 'https://' + url;
    }
    setCollapsed(true);
    onGenerate(url, selected);
  };

  const handleBack = () => {
    if (step === 'prompts') {
      setStep('assets');
      setSelectedAsset(null);
      setPrompts([]);
      setSelectedPromptIds(new Set());
    } else if (step === 'assets') {
      setStep('token');
      setAssets([]);
    }
  };

  return (
    <div className="space-y-4">
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3">
          <p className="text-red-600 text-sm">{error}</p>
        </div>
      )}

      {/* Step 1: API Token */}
      {step === 'token' && (
        <form onSubmit={handleFetchAssets} className="space-y-3">
          <label className="block text-sm text-profound-muted">Profound API Key</label>
          <div className="flex gap-3">
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              disabled={disabled || loading}
              className="flex-1 bg-white border border-profound-border rounded-lg px-4 py-3 text-gray-900 focus:border-profound-blue focus:ring-1 focus:ring-profound-blue outline-none transition-colors disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={disabled || loading || !apiKey.trim()}
              className="bg-white text-black font-semibold rounded-lg px-6 py-2.5 border border-profound-border hover:bg-gray-50 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Loading...' : 'Import'}
            </button>
          </div>
        </form>
      )}

      {/* Step 2: Asset Selection */}
      {step === 'assets' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-900">Select an asset</h3>
            <button
              type="button"
              onClick={handleBack}
              className="text-sm text-profound-muted hover:text-profound-light transition-colors cursor-pointer"
            >
              Back
            </button>
          </div>
          <div className="grid gap-2">
            {assets.map((asset) => (
              <button
                key={asset.id}
                type="button"
                onClick={() => handleSelectAsset(asset)}
                disabled={loading}
                className="flex items-center gap-3 w-full bg-white border border-profound-border rounded-lg px-4 py-3 text-left hover:border-profound-blue transition-colors cursor-pointer disabled:opacity-50"
              >
                {asset.logo_url && (
                  <img src={asset.logo_url} alt="" className="w-6 h-6 rounded" />
                )}
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-gray-900 truncate">{asset.name}</p>
                  <p className="text-xs text-profound-muted truncate">{asset.website}</p>
                </div>
                <span className="text-xs text-profound-muted shrink-0">{asset.category.name}</span>
              </button>
            ))}
          </div>
          {loading && <p className="text-sm text-profound-muted">Loading prompts...</p>}
        </div>
      )}

      {/* Step 3: Prompt Selection */}
      {step === 'prompts' && selectedAsset && (
        <div className="space-y-3">
          {collapsed ? (
            /* Collapsed summary */
            <button
              type="button"
              onClick={() => setCollapsed(false)}
              className="flex items-center justify-between w-full bg-gray-50 border border-profound-border rounded-lg px-4 py-3 text-left hover:bg-gray-100 transition-colors cursor-pointer"
            >
              <span className="text-sm text-gray-900">
                {selectedAsset.name} — {selectedPromptIds.size} prompt{selectedPromptIds.size !== 1 ? 's' : ''} selected
              </span>
              <span className="text-xs text-profound-muted">Expand</span>
            </button>
          ) : (
            /* Expanded prompt picker */
            <>
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-gray-900">
                    Select up to {MAX_PROMPTS} prompts to optimize for
                  </h3>
                  <p className="text-xs text-profound-muted mt-0.5">
                    {selectedPromptIds.size}/{MAX_PROMPTS} selected{atLimit ? ' (limit reached)' : ''}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleBack}
                  className="text-sm text-profound-muted hover:text-profound-light transition-colors cursor-pointer"
                >
                  Back
                </button>
              </div>

              <div className="flex gap-2 mb-2">
                <button
                  type="button"
                  onClick={() => setSelectedPromptIds(new Set(prompts.slice(0, MAX_PROMPTS).map((p) => p.id)))}
                  className="text-xs text-profound-blue hover:underline cursor-pointer"
                >
                  Select first {MAX_PROMPTS}
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedPromptIds(new Set())}
                  className="text-xs text-profound-muted hover:underline cursor-pointer"
                >
                  Deselect all
                </button>
              </div>

              <div className="max-h-80 overflow-y-auto space-y-1 border border-profound-border rounded-lg p-2">
                {prompts.map((prompt) => {
                  const isSelected = selectedPromptIds.has(prompt.id);
                  const isDisabled = !isSelected && atLimit;
                  return (
                    <label
                      key={prompt.id}
                      className={`flex items-start gap-3 px-3 py-2 rounded-md transition-colors ${
                        isDisabled
                          ? 'opacity-40 cursor-not-allowed'
                          : 'hover:bg-gray-50 cursor-pointer'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => togglePrompt(prompt.id)}
                        disabled={isDisabled}
                        className="mt-0.5 shrink-0 accent-profound-blue"
                      />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-gray-900">{prompt.prompt}</p>
                        <p className="text-xs text-profound-muted mt-0.5">
                          {prompt.topic.name}
                        </p>
                      </div>
                    </label>
                  );
                })}
              </div>

              <button
                type="button"
                onClick={handleGenerate}
                disabled={disabled || selectedPromptIds.size === 0}
                className="w-full bg-white text-black font-semibold rounded-lg px-6 py-2.5 border border-profound-border hover:bg-gray-50 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Generate ({selectedPromptIds.size} prompt{selectedPromptIds.size !== 1 ? 's' : ''} selected)
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
