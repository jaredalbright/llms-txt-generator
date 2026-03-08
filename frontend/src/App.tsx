import Layout from './components/Layout';
import URLInput from './components/URLInput';
import PipelineProgress from './components/PipelineProgress';
import EditorPreview from './components/EditorPreview';
import RepromptBar from './components/RepromptBar';
import ExportBar from './components/ExportBar';
import { useJob } from './hooks/useJob';

export default function App() {
  const {
    submitJob,
    regenerate,
    reprompt,
    markdown,
    setMarkdown,
    status,
    progress,
    error,
    steps,
    isReprompting,
    isValidating,
    isValid,
    validationIssues,
    jobId,
  } = useJob();

  const isLoading = status === 'crawling' || status === 'processing' || status === 'pending' || status === 'extracting_content' || status === 'summarizing';
  const isComplete = status === 'completed' && markdown;

  return (
    <Layout>
      <div className="space-y-6">
        {/* URL Input */}
        <URLInput onSubmit={(url, clientInfo) => submitJob(url, clientInfo)} disabled={isLoading} />

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
            <EditorPreview markdown={markdown} onChange={setMarkdown} />

            {/* Reprompt */}
            <RepromptBar onSubmit={reprompt} disabled={isReprompting} />

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

            {/* Export */}
            <ExportBar
              markdown={markdown}
              jobId={jobId || undefined}
              onRegenerate={regenerate}
              exportDisabled={isValidating || !isValid}
            />
          </>
        )}
      </div>
    </Layout>
  );
}
