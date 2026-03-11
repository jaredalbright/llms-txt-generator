import { useState, useEffect, useCallback } from 'react';
import Layout from './components/Layout';
import URLInput from './components/URLInput';
import ProfoundImport from './components/ProfoundImport';
import PipelineProgress from './components/PipelineProgress';
import EditorPreview from './components/EditorPreview';
import PostDownloadModal from './components/PostDownloadModal';
import RecentCarousel from './components/RecentCarousel';
import { useJob } from './hooks/useJob';
import { useSessionState } from './hooks/useSessionState';
import { downloadZip as downloadZipApi } from './lib/api';

type InputMode = 'url' | 'profound';

export default function App() {
  const [mode, setMode] = useSessionState<InputMode>('app_input_mode', 'url');
  const {
    submitJob,
    reset,
    loadCached,
    loadPrevious,
    generateNew,
    cacheHit,
    markdown,
    setMarkdown,
    status,
    error,
    steps,
    isValidating,
    isValid,
    validationIssues,
    jobId,
  } = useJob();

  const [showModal, setShowModal] = useState(false);

  // Close cache hit modal on Escape
  const handleEscape = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape' && cacheHit) generateNew();
  }, [cacheHit, generateNew]);

  useEffect(() => {
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [handleEscape]);

  const isLoading = status === 'crawling' || status === 'processing' || status === 'pending' || status === 'extracting_content' || status === 'summarizing';
  const isComplete = status === 'completed' && markdown;
  const exportDisabled = isValidating || !isValid;

  const handleModeSwitch = (newMode: InputMode) => {
    if (newMode === mode) return;
    reset();
    setMode(newMode);
  };

  const handleCopy = async () => {
    await navigator.clipboard.writeText(markdown);
  };

  const handleDownloadTxt = () => {
    const blob = new Blob([markdown], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'llms.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadZip = async () => {
    if (!jobId) return;
    await downloadZipApi(jobId, markdown);
    setShowModal(true);
  };

  return (
    <Layout>
      <div className="space-y-6">
        {/* Mode Toggle */}
        {!isLoading && (
          <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit" role="tablist" aria-label="Input mode">
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'url'}
              onClick={() => handleModeSwitch('url')}
              className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors cursor-pointer ${
                mode === 'url'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-profound-muted hover:text-gray-900'
              }`}
            >
              Generate from URL
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'profound'}
              onClick={() => handleModeSwitch('profound')}
              className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors cursor-pointer ${
                mode === 'profound'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-profound-muted hover:text-gray-900'
              }`}
            >
              Import from Profound
            </button>
          </div>
        )}

        {/* Input */}
        {mode === 'url' ? (
          <URLInput onSubmit={(url, clientInfo) => submitJob(url, clientInfo)} disabled={isLoading} />
        ) : (
          <ProfoundImport
            onGenerate={(url, promptsContext) => submitJob(url, undefined, promptsContext)}
            disabled={isLoading}
          />
        )}

        {/* Recent generations carousel */}
        {!isLoading && !isComplete && !error && steps.length === 0 && mode === 'url' && (
          <RecentCarousel onSelect={(id, md) => loadPrevious(id, md)} />
        )}

        {/* Cache hit modal */}
        {cacheHit && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={generateNew} role="dialog" aria-label="Previous result found">
            <div className="absolute inset-0 bg-black/40" />
            <div
              className="relative bg-white rounded-2xl shadow-xl max-w-md w-full p-8"
              onClick={e => e.stopPropagation()}
            >
              <div className="space-y-5">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">Previous result found</h2>
                  <p className="text-sm text-profound-muted mt-1">
                    A cached result exists for this URL. Would you like to load it or generate a fresh one?
                  </p>
                </div>
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={loadCached}
                    className="flex-1 bg-profound-blue text-white font-medium text-sm rounded-lg px-5 py-2.5 hover:bg-profound-blue/90 transition-colors cursor-pointer"
                  >
                    Load previous result
                  </button>
                  <button
                    type="button"
                    onClick={generateNew}
                    className="flex-1 bg-white text-gray-900 font-medium text-sm rounded-lg px-5 py-2.5 border border-profound-border hover:bg-gray-50 transition-colors cursor-pointer"
                  >
                    Generate new
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Error display */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4" role="alert">
            <p className="text-red-600 text-sm">{error}</p>
          </div>
        )}

        {/* Progress */}
        {steps.length > 0 && (
          <PipelineProgress steps={steps} />
        )}

        {/* Editor + Preview */}
        {isComplete && (
          <>
            <EditorPreview
              markdown={markdown}
              onChange={setMarkdown}
              onCopy={handleCopy}
              onDownloadTxt={handleDownloadTxt}
              onDownloadZip={jobId ? handleDownloadZip : undefined}
              exportDisabled={exportDisabled}
            />

            {/* Validation status */}
            {isValidating && (
              <p className="text-sm text-profound-muted" aria-live="polite">Validating...</p>
            )}
            {!isValidating && !isValid && validationIssues.length > 0 && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-4 space-y-1" role="alert">
                <p className="text-red-600 text-sm font-medium">Validation issues found:</p>
                {validationIssues.map((issue, i) => (
                  <p key={i} className="text-sm text-red-600">
                    Line {issue.line}: {issue.message}
                  </p>
                ))}
              </div>
            )}

            {showModal && <PostDownloadModal onClose={() => setShowModal(false)} isProfoundUser={mode === 'profound'} />}
          </>
        )}
      </div>
    </Layout>
  );
}
