import { useState } from 'react';
import Layout from './components/Layout';
import URLInput from './components/URLInput';
import ProfoundImport from './components/ProfoundImport';
import PipelineProgress from './components/PipelineProgress';
import EditorPreview from './components/EditorPreview';
import PostDownloadModal from './components/PostDownloadModal';
import { useJob } from './hooks/useJob';
import { useSessionState } from './hooks/useSessionState';
import { downloadZip as downloadZipApi } from './lib/api';

type InputMode = 'url' | 'profound';

export default function App() {
  const [mode, setMode] = useSessionState<InputMode>('app_input_mode', 'url');
  const {
    submitJob,
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

  const isLoading = status === 'crawling' || status === 'processing' || status === 'pending' || status === 'extracting_content' || status === 'summarizing';
  const isComplete = status === 'completed' && markdown;
  const exportDisabled = isValidating || !isValid;

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
          <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
            <button
              type="button"
              onClick={() => setMode('url')}
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
              onClick={() => setMode('profound')}
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

        {/* Error display */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4">
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
              <p className="text-sm text-profound-muted">Validating...</p>
            )}
            {!isValidating && !isValid && validationIssues.length > 0 && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-4 space-y-1">
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
